"""Schedule Manager - Reconciliation loop for EventBridge Schedules"""
import boto3
import json
import os
import sys
import logging
import urllib.request
from urllib.error import HTTPError

# Setup logging
logger = logging.getLogger()

def setup_logger(aws_request_id):
    """Configure custom log formatter for lambda-alarms metric filter"""
    root = logging.getLogger()
    for h in root.handlers[:]:
        root.removeHandler(h)
    
    fmt = "%(asctime)s %(aws_request_id)s %(levelname)s %(message)s"
    formatter = logging.Formatter(fmt=fmt, datefmt='%Y-%m-%dT%H:%M:%S')
    
    sh = logging.StreamHandler(sys.stdout)
    sh.setLevel(logging.INFO)
    sh.setFormatter(formatter)
    sh.addFilter(lambda record: setattr(record, 'aws_request_id', aws_request_id) or True)
    
    root.addHandler(sh)
    root.setLevel(logging.INFO)

# Environment variables
CONFIG_GIT_URL = os.environ['CONFIG_GIT_URL']
QUERY_EXECUTOR_ARN = os.environ['QUERY_EXECUTOR_ARN']
SCHEDULE_ROLE_ARN = os.environ['SCHEDULE_ROLE_ARN']
SCHEDULE_GROUP_NAME = os.environ.get('SCHEDULE_GROUP_NAME', 'pn-athena-queries')
PROJECT_NAME = os.environ.get('PROJECT_NAME', 'pn')

scheduler = boto3.client('scheduler')


def fetch_config_from_git():
    """Fetch query configuration from Git repository"""
    logger.info(f"Fetching config from Git: {CONFIG_GIT_URL}")
    
    try:
        with urllib.request.urlopen(CONFIG_GIT_URL, timeout=10) as response:
            content = response.read().decode('utf-8').strip()
            
            if not content:
                raise ValueError("Git config file is empty")
            
            config = json.loads(content)
            logger.info(f"Successfully fetched config with {len(config.get('queries', {}))} queries")
            return config
            
    except HTTPError as e:
        if e.code == 404:
            raise FileNotFoundError(f"Config file not found at {CONFIG_GIT_URL}")
        raise RuntimeError(f"Failed to fetch config from Git (HTTP {e.code}): {CONFIG_GIT_URL}")
    except Exception as e:
        raise RuntimeError(f"Failed to fetch config from Git: {e}")


def list_existing_schedules():
    """List all EventBridge Schedules in the group"""
    logger.info(f"Listing existing schedules in group: {SCHEDULE_GROUP_NAME}")
    
    schedules = {}
    next_token = None
    
    try:
        while True:
            if next_token:
                response = scheduler.list_schedules(
                    GroupName=SCHEDULE_GROUP_NAME,
                    NextToken=next_token
                )
            else:
                response = scheduler.list_schedules(
                    GroupName=SCHEDULE_GROUP_NAME
                )
            
            for schedule_summary in response.get('Schedules', []):
                schedule_name = schedule_summary['Name']
                # Get full schedule details
                schedule_detail = scheduler.get_schedule(
                    GroupName=SCHEDULE_GROUP_NAME,
                    Name=schedule_name
                )
                
                schedules[schedule_name] = {
                    'arn': schedule_summary['Arn'],
                    'cron': schedule_detail['ScheduleExpression'],
                    'state': schedule_detail['State'],
                    'target': schedule_detail['Target']
                }
            
            next_token = response.get('NextToken')
            if not next_token:
                break
        
        logger.info(f"Found {len(schedules)} existing schedules")
        return schedules
        
    except scheduler.exceptions.ResourceNotFoundException:
        logger.info(f"Schedule group '{SCHEDULE_GROUP_NAME}' not found, will create schedules in default group")
        return {}
    except Exception as e:
        logger.error(f"Failed to list schedules: {e}")
        raise


def build_schedule_name(query_id):
    """Build schedule name from query ID"""
    return f"{PROJECT_NAME}-{query_id}"


def calculate_diff(config_queries, existing_schedules):
    """
    Calculate diff between desired (config) and actual (schedules) state
    
    Returns:
        to_create: List of query_ids to create schedules for
        to_update: List of query_ids with changed cron
        to_delete: List of schedule names to delete
    """
    logger.info("Calculating reconciliation diff")
    
    to_create = []
    to_update = []
    to_delete = []
    
    # Build set of expected schedule names from config
    expected_schedules = {build_schedule_name(qid): qid for qid in config_queries.keys()}
    
    # Find schedules to create or update
    for query_id, query_config in config_queries.items():
        schedule_name = build_schedule_name(query_id)
        desired_cron = query_config.get('schedule', query_config.get('cron', 'cron(0 2 * * ? *)'))
        
        if schedule_name not in existing_schedules:
            # Schedule doesn't exist -> CREATE
            to_create.append(query_id)
            logger.info(f"  CREATE: {schedule_name} (cron: {desired_cron})")
        else:
            # Schedule exists -> check if cron changed
            existing_cron = existing_schedules[schedule_name]['cron']
            if existing_cron != desired_cron:
                # Cron changed -> UPDATE
                to_update.append(query_id)
                logger.info(f"  UPDATE: {schedule_name} (cron: {existing_cron} → {desired_cron})")
    
    # Find schedules to delete
    for schedule_name in existing_schedules.keys():
        if schedule_name not in expected_schedules:
            # Schedule exists but not in config -> DELETE
            to_delete.append(schedule_name)
            logger.info(f"  DELETE: {schedule_name} (removed from config)")
    
    logger.info(f"Diff: {len(to_create)} to create, {len(to_update)} to update, {len(to_delete)} to delete")
    
    return to_create, to_update, to_delete


def create_schedule(query_id, query_config):
    """Create new EventBridge Schedule"""
    schedule_name = build_schedule_name(query_id)
    cron_expression = query_config.get('schedule', query_config.get('cron', 'cron(0 2 * * ? *)'))
    description = query_config.get('description', f"Scheduled execution for {query_id}")
    
    logger.info(f"Creating schedule: {schedule_name}")
    
    try:
        scheduler.create_schedule(
            GroupName=SCHEDULE_GROUP_NAME,
            Name=schedule_name,
            Description=description,
            ScheduleExpression=cron_expression,
            FlexibleTimeWindow={'Mode': 'OFF'},
            State='ENABLED',
            Target={
                'Arn': QUERY_EXECUTOR_ARN,
                'RoleArn': SCHEDULE_ROLE_ARN,
                'Input': json.dumps({'query_id': query_id})
            }
        )
        logger.info(f"Successfully created schedule: {schedule_name}")
        return True
    except Exception as e:
        logger.error(f"Failed to create schedule {schedule_name}: {e}")
        return False


def update_schedule(query_id, query_config):
    """Update existing EventBridge Schedule"""
    schedule_name = build_schedule_name(query_id)
    cron_expression = query_config.get('schedule', query_config.get('cron', 'cron(0 2 * * ? *)'))
    description = query_config.get('description', f"Scheduled execution for {query_id}")
    
    logger.info(f"Updating schedule: {schedule_name}")
    
    try:
        scheduler.update_schedule(
            GroupName=SCHEDULE_GROUP_NAME,
            Name=schedule_name,
            Description=description,
            ScheduleExpression=cron_expression,
            FlexibleTimeWindow={'Mode': 'OFF'},
            State='ENABLED',
            Target={
                'Arn': QUERY_EXECUTOR_ARN,
                'RoleArn': SCHEDULE_ROLE_ARN,
                'Input': json.dumps({'query_id': query_id})
            }
        )
        logger.info(f"Successfully updated schedule: {schedule_name}")
        return True
    except Exception as e:
        logger.error(f"Failed to update schedule {schedule_name}: {e}")
        return False


def delete_schedule(schedule_name):
    """Delete EventBridge Schedule"""
    logger.info(f"Deleting schedule: {schedule_name}")
    
    try:
        scheduler.delete_schedule(
            GroupName=SCHEDULE_GROUP_NAME,
            Name=schedule_name
        )
        logger.info(f"Successfully deleted schedule: {schedule_name}")
        return True
    except Exception as e:
        logger.error(f"Failed to delete schedule {schedule_name}: {e}")
        return False


def lambda_handler(event, context):
    """
    Main reconciliation loop handler
    Triggered by EventBridge rate(5 minutes)
    """
    setup_logger(context.aws_request_id)
    
    logger.info("Starting schedule reconciliation")
    
    try:
        # 1. Fetch desired state from Git
        config = fetch_config_from_git()
        queries = config.get('queries', {})
        
        if not queries:
            logger.warning("No queries found in config")
            return {'statusCode': 200, 'message': 'No queries to reconcile'}
        
        # 2. Get current state from EventBridge
        existing_schedules = list_existing_schedules()
        
        # 3. Calculate diff
        to_create, to_update, to_delete = calculate_diff(queries, existing_schedules)
        
        # 4. Apply changes
        results = {
            'created': 0,
            'updated': 0,
            'deleted': 0,
            'failed': 0
        }
        
        # Create new schedules
        for query_id in to_create:
            if create_schedule(query_id, queries[query_id]):
                results['created'] += 1
            else:
                results['failed'] += 1
        
        # Update existing schedules
        for query_id in to_update:
            if update_schedule(query_id, queries[query_id]):
                results['updated'] += 1
            else:
                results['failed'] += 1
        
        # Delete obsolete schedules
        for schedule_name in to_delete:
            if delete_schedule(schedule_name):
                results['deleted'] += 1
            else:
                results['failed'] += 1
        
        logger.info(f"Reconciliation complete: {results}")
        
        return {
            'statusCode': 200,
            'message': 'Reconciliation completed',
            'results': results
        }
        
    except Exception as e:
        logger.error(f"Reconciliation failed: {e}")
        raise