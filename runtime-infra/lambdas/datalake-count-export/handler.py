import boto3
import json
import os
import re
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor
from urllib.error import HTTPError

from config import (
    logger, setup_logger, CONFIG_GIT_URL,
    OUTPUT_BUCKET, ATHENA_RESULTS_BUCKET, DATABASE, WORKGROUP, MAX_WORKERS
)

athena = boto3.client('athena')
s3 = boto3.client('s3')


def fetch_config_from_git():
    """Retrieve custom query configuration from Git repository."""
    if not CONFIG_GIT_URL:
        raise ValueError("CONFIG_GIT_URL is required")
    
    url = CONFIG_GIT_URL
    logger.info(f"Fetching config from Git: {url}")
    
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            content = response.read().decode('utf-8').strip()
            
            if not content:
                raise ValueError("Git config file is empty")
            
            return json.loads(content)
            
    except HTTPError as e:
        if e.code == 404:
            raise FileNotFoundError(f"Config file not found at {url}")
        raise RuntimeError(f"Failed to fetch config from Git (HTTP {e.code}): {url}")
    except Exception as e:
        raise RuntimeError(f"Failed to fetch config from Git: {e}")


def fetch_custom_queries():
    """Load custom queries from Git (required)."""
    if not CONFIG_GIT_URL:
        raise ValueError("CONFIG_GIT_URL is required")
    
    return fetch_config_from_git()


def execute_count_query(query, output_prefix):
    """Execute Athena count query and wait for completion."""
    logger.info(f"Executing query: {query}")
    
    response = athena.start_query_execution(
        QueryString=query,
        QueryExecutionContext={'Database': DATABASE},
        ResultConfiguration={'OutputLocation': f"s3://{ATHENA_RESULTS_BUCKET}/{output_prefix}"},
        WorkGroup=WORKGROUP
    )
    query_id = response['QueryExecutionId']
    
    while True:
        execution = athena.get_query_execution(QueryExecutionId=query_id)
        status = execution['QueryExecution']['Status']['State']
        
        if status in ['SUCCEEDED', 'FAILED', 'CANCELLED']:
            break
        
        time.sleep(2)
    
    if status != 'SUCCEEDED':
        reason = execution['QueryExecution']['Status'].get('StateChangeReason', 'Unknown')
        raise RuntimeError(f"Query {query_id} failed: {reason}")
    
    results = athena.get_query_results(QueryExecutionId=query_id)
    rows = results['ResultSet']['Rows']
    
    if len(rows) > 1:
        return int(rows[1]['Data'][0]['VarCharValue'])
    
    return 0


def process_table(report_name, config, date_params):
    """Process single table: format query and execute count."""
    query = config['query'].format(**date_params)
    count = execute_count_query(query, f"athena_results/{report_name}")
    
    return {
        'table_name': report_name,
        'send_count': count
    }


def save_report(report, date_path):
    """Save count report to S3 with date-partitioned path."""
    key = f"datalake_counts/{date_path}/counts.json"
    
    s3.put_object(
        Bucket=OUTPUT_BUCKET,
        Key=key,
        Body=json.dumps(report, indent=2)
    )
    
    logger.info(f"Report saved: s3://{OUTPUT_BUCKET}/{key}")


def process_daily_count(event, context):
    """Main handler: process T-1 counts for all configured tables."""
    setup_logger(context.aws_request_id)
    
    yesterday = datetime.now(timezone.utc) - timedelta(days=1)
    date_params = {
        'YEAR': yesterday.strftime('%Y'),
        'MONTH': yesterday.strftime('%m'),
        'DAY': yesterday.strftime('%d')
    }
    date_path = yesterday.strftime('%Y/%m/%d')
    execution_ts = datetime.now(timezone.utc).isoformat()
    
    logger.info(f"Processing counts for date: {yesterday.strftime('%Y-%m-%d')}")
    
    custom_configs = fetch_custom_queries()
    
    results = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(process_table, report_name, config, date_params): report_name
            for report_name, config in custom_configs.items()
        }
        
        for future in futures:
            report_name = futures[future]
            result = future.result()
            results.append(result)
            logger.info(f"Processed {report_name}: {result.get('send_count', 'N/A')}")
    
    report = {
        'tables': [
            {**result, 'execution_timestamp': execution_ts}
            for result in results
        ]
    }
    
    save_report(report, date_path)
    
    return {'statusCode': 200, 'message': 'Count completed successfully'}