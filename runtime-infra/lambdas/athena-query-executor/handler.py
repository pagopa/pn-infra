"""Main handler orchestrating Athena query execution with export and alerts"""
import json
import urllib.request
from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError

import os
from config import logger, setup_logger, CONFIG_GIT_URL, ATHENA_DATABASE, ATHENA_WORKGROUP
from services.athena_client import execute_athena_query
from services.s3_client import export_results_to_csv
from services.slack_client import send_slack_notification


def fetch_config_from_git():
    """Retrieve query configuration from Git repository"""
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


def calculate_t_minus_1():
    """Calculate T-1 date (yesterday) in YYYY-MM-DD format"""
    yesterday = datetime.now(timezone.utc) - timedelta(days=1)
    return yesterday.strftime('%Y-%m-%d')


def build_date_variables(execution_date_str):
    """Build date variables for query substitution"""
    date_obj = datetime.strptime(execution_date_str, '%Y-%m-%d')
    return {
        'YEAR': date_obj.strftime('%Y'),
        'MONTH': date_obj.strftime('%m'),
        'DAY': date_obj.strftime('%d'),
        'DATE': execution_date_str
    }


def substitute_query_variables(query_template, variables):
    """Replace placeholders in query with actual values"""
    query = query_template
    for key, value in variables.items():
        query = query.replace(f'{{{key}}}', str(value))
    return query


def handle_export_mode(query_id, query_config, results, execution_date, execution_timestamp, sns_topic_arn):
    """
    Export mode: always export CSV and send Slack notification
    """
    logger.info(f"Handling export mode for query: {query_id}")
    
    # Export CSV to S3
    csv_url = export_results_to_csv(
        query_id=query_id,
        config=query_config,
        results=results,
        execution_date=execution_date
    )
    
    logger.info(f"CSV exported to: {csv_url}")
    
    # Send Slack notification if enabled
    if query_config.get('slack', {}).get('enabled', False):
        slack_config = query_config['slack']
        message_vars = {
            'date': execution_date,
            'total_rows': len(results),
            's3_url': csv_url,
            'timestamp': execution_timestamp,
            'query_id': query_id,
            'description': query_config.get('description', 'N/A')
        }
        
        send_slack_notification(slack_config, message_vars, sns_topic_arn)
        logger.info(f"Slack notification sent for export: {query_id}")


def evaluate_threshold(record_count, operator, threshold_value):
    """
    Evaluate threshold condition
    Supported operators: >, <, >=, <=, ==, !=
    """
    operators_map = {
        '>': lambda x, y: x > y,
        '<': lambda x, y: x < y,
        '>=': lambda x, y: x >= y,
        '<=': lambda x, y: x <= y,
        '==': lambda x, y: x == y,
        '!=': lambda x, y: x != y
    }
    
    if operator not in operators_map:
        raise ValueError(f"Unsupported operator: {operator}")
    
    return operators_map[operator](record_count, threshold_value)


def handle_alerts_mode(query_id, query_config, results, execution_date, execution_timestamp, sns_topic_arn):
    """
    Alerts mode: evaluate threshold and conditionally notify
    Multiple alerts can be defined per query
    """
    logger.info(f"Handling alerts mode for query: {query_id}")
    
    record_count = len(results)
    alerts = query_config.get('alerts', [])
    
    if not alerts:
        logger.warning(f"No alerts defined for query: {query_id}")
        return
    
    for alert in alerts:
        alert_name = alert.get('name', 'unnamed-alert')
        threshold = alert.get('threshold', {})
        operator = threshold.get('operator', '>')
        value = threshold.get('value', 0)
        csv_export = alert.get('csv_export', False)
        
        logger.info(f"Evaluating alert '{alert_name}': {record_count} {operator} {value}")
        
        # Evaluate threshold condition
        condition_met = evaluate_threshold(record_count, operator, value)
        
        if condition_met:
            logger.info(f"Alert '{alert_name}' TRIGGERED: condition {record_count} {operator} {value} is TRUE")
            
            # Export CSV if requested for this alert
            csv_url = 'N/A'
            if csv_export:
                csv_url = export_results_to_csv(
                    query_id=query_id,
                    config=query_config,
                    results=results,
                    execution_date=execution_date,
                    alert_name=alert_name
                )
                logger.info(f"CSV exported for alert: {csv_url}")
            
            # Send Slack notification if enabled
            if query_config.get('slack', {}).get('enabled', False):
                slack_config = query_config['slack']
                message_vars = {
                    'date': execution_date,
                    'alert_name': alert_name,
                    'alert_count': record_count,
                    'threshold': value,
                    'operator': operator,
                    's3_url': csv_url,
                    'timestamp': execution_timestamp,
                    'query_id': query_id,
                    'description': query_config.get('description', 'N/A')
                }
                
                send_slack_notification(slack_config, message_vars, sns_topic_arn)
                logger.info(f"Slack notification sent for alert: {alert_name}")
        else:
            logger.info(f"Alert '{alert_name}' NOT triggered: condition {record_count} {operator} {value} is FALSE")


def lambda_handler(event, context):
    """
    Main Lambda handler for Athena Query Executor
    
    Event structure from EventBridge Scheduler:
    {
        "query_id": "daily-notifications-report",
        "execution_date": "2025-11-04"  # optional, default T-1
    }
    """
    setup_logger(context.aws_request_id)
    
    # Extract parameters from event
    query_id = event.get('query_id')
    if not query_id:
        raise ValueError("Missing required parameter: query_id")
    
    execution_date = event.get('execution_date') or calculate_t_minus_1()
    execution_timestamp = datetime.now(timezone.utc).isoformat()
    
    logger.info(f"Executing query '{query_id}' for date: {execution_date}")
    
    # Fetch configuration from Git
    config = fetch_config_from_git()
    
    if query_id not in config['queries']:
        raise ValueError(f"Query '{query_id}' not found in config")
    
    query_config = config['queries'][query_id]
    global_config = config.get('global_config', {})
    
    logger.info(f"Query type: {query_config.get('type', 'export')}")
    
    # Build date variables
    date_vars = build_date_variables(execution_date)
    
    # Add THRESHOLD variable if defined (for alerts mode)
    if 'alert_threshold' in query_config:
        date_vars['THRESHOLD'] = query_config['alert_threshold']
    
    # Substitute variables in query
    query_sql = substitute_query_variables(query_config['query'], date_vars)
    
    logger.info(f"Executing Athena query with {len(results) if 'results' in locals() else 'unknown'} variable substitutions")
    
    # Execute Athena query
    results = execute_athena_query(
        query=query_sql,
        database=global_config.get('athena_database', ATHENA_DATABASE),
        workgroup=global_config.get('athena_workgroup', ATHENA_WORKGROUP)
    )
    
    logger.info(f"Query returned {len(results)} records")
    
    # Get SNS Topic ARN from environment (single topic for all notifications)
    sns_topic_arn = os.environ.get('SNS_TOPIC_ARN', '')
    
    if not sns_topic_arn:
        logger.warning("SNS_TOPIC_ARN not configured in environment")
    
    # Process based on action type
    action = query_config.get('type', 'export')
    
    if action == 'export':
        handle_export_mode(query_id, query_config, results, execution_date, execution_timestamp, sns_topic_arn)
    elif action == 'alerts':
        handle_alerts_mode(query_id, query_config, results, execution_date, execution_timestamp, sns_topic_arn)
    else:
        raise ValueError(f"Unsupported action type: {action}")
    
    logger.info(f"Query '{query_id}' completed successfully")
    
    return {
        'statusCode': 200,
        'message': f'Query {query_id} executed successfully',
        'records': len(results),
        'execution_date': execution_date
    }