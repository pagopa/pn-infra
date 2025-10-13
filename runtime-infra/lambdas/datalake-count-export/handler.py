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
    logger, setup_logger, CONFIG_SSM_PARAM, CONFIG_GIT_URL, CONFIG_GIT_REF,
    TABLE_LIST, OUTPUT_BUCKET, ATHENA_RESULTS_BUCKET, DATABASE, WORKGROUP, MAX_WORKERS
)

ssm = boto3.client('ssm')
glue = boto3.client('glue')
athena = boto3.client('athena')
s3 = boto3.client('s3')


def fetch_config_from_git():
    """Retrieve custom query configuration from Git repository."""
    if not CONFIG_GIT_URL:
        raise ValueError("CONFIG_GIT_URL is required when using Git source")
    
    url = CONFIG_GIT_URL.replace('/main/', f'/{CONFIG_GIT_REF}/').replace('/master/', f'/{CONFIG_GIT_REF}/')
    logger.info(f"Fetching config from Git: {url}")
    
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            content = response.read().decode('utf-8').strip()
            
            if not content:
                logger.info("Git config file is empty - using default queries")
                return {}
            
            return json.loads(content)
            
    except HTTPError as e:
        if e.code == 404:
            raise FileNotFoundError(f"Config file not found at {url}")
        raise RuntimeError(f"Failed to fetch config from Git (HTTP {e.code}): {url}")
    except Exception as e:
        raise RuntimeError(f"Failed to fetch config from Git: {e}")


def fetch_config_from_ssm():
    """Retrieve custom query configuration from SSM Parameter Store."""
    response = ssm.get_parameter(Name=CONFIG_SSM_PARAM, WithDecryption=True)
    value = response['Parameter']['Value'].strip()
    
    if not value:
        logger.info("SSM parameter is empty - using default queries")
        return {}
    
    return json.loads(value)


def fetch_custom_queries():
    """Load custom queries with cascading fallback: Git → SSM → default."""
    if CONFIG_GIT_URL:
        return fetch_config_from_git()
    
    logger.info("CONFIG_GIT_URL not set - using SSM Parameter Store")
    return fetch_config_from_ssm()


def check_table_exists(table_name):
    """Verify table existence in Glue Catalog and return table info."""
    try:
        response = glue.get_table(DatabaseName=DATABASE, Name=table_name)
        return True, response['Table']
    except glue.exceptions.EntityNotFoundException:
        return False, None


def extract_source_name(location):
    """Extract source data name from S3 location path."""
    match = re.search(r'TABLE_NAME_([^/]+)/', location)
    if match:
        return match.group(1)
    
    match = re.search(r'/([^/]+)/?$', location.rstrip('/'))
    return match.group(1) if match else None


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


def build_default_query(table_name, date_params):
    """Build standard count query for date-partitioned table."""
    return (
        f"SELECT COUNT(*) as total_count "
        f"FROM \"{DATABASE}\".\"{table_name}\" "
        f"WHERE p_year = '{date_params['YEAR']}' "
        f"AND p_month = '{date_params['MONTH']}' "
        f"AND p_day = '{date_params['DAY']}'"
    )


def build_custom_query(template, table_name, date_params):
    """Build query from custom template with parameter substitution."""
    return template.replace('{TABLE_NAME}', table_name).format(**date_params)


def process_table(table_name, custom_configs, date_params):
    """Process single table: verify existence, build query, execute count."""
    exists, table_info = check_table_exists(table_name)
    
    if not exists:
        logger.warning(f"Table '{table_name}' not found in Glue catalog - skipping")
        return {
            'table_name': table_name,
            'send_count': None,
            'status': 'NOT_FOUND'
        }
    
    location = table_info['StorageDescriptor']['Location']
    output_name = extract_source_name(location) or table_name
    
    if table_name in custom_configs:
        config = custom_configs[table_name]
        query = build_custom_query(config['query_template'], table_name, date_params)
    else:
        query = build_default_query(table_name, date_params)
    
    count = execute_count_query(query, f"athena_results/{table_name}")
    
    return {
        'table_name': output_name,
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
    tables = [t.strip() for t in TABLE_LIST.split(',')]
    
    results = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(process_table, table, custom_configs, date_params): table
            for table in tables
        }
        
        for future in futures:
            table = futures[future]
            result = future.result()
            results.append(result)
            logger.info(f"Processed {table}: {result.get('send_count', 'N/A')}")
    
    report = {
        'tables': [
            {**result, 'execution_timestamp': execution_ts}
            for result in results
        ]
    }
    
    save_report(report, date_path)
    
    return {'statusCode': 200, 'message': 'Count completed successfully'}