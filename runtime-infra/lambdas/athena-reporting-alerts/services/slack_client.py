"""Slack notification service layer - SNS with mrkdwn (Slack Markdown) support"""
import boto3
import json
from config import logger

sns = boto3.client('sns')


def build_export_message(query_id, description, total_rows, s3_path, presigned_url, execution_date, timestamp):
    """Build mrkdwn message for export mode using Slack markdown syntax"""
    return f"""*📊 Athena Reporting - Export Complete*

*Query:* {query_id}
*Description:* {description}
*Date:* {execution_date}
*Total Records:* {total_rows}

*S3 Path:* `{s3_path}`

📥 <{presigned_url}|Download CSV Report> _(valid 24h)_

_Executed at: {timestamp}_"""


def build_alert_message(query_id, alert_name, alert_count, threshold, operator, s3_path, presigned_url, execution_date, timestamp):
    """Build mrkdwn message for alert mode using Slack markdown syntax"""
    csv_section = f"\n*S3 Path:* `{s3_path}`\n\n📥 <{presigned_url}|Download Alert Data> _(valid 24h)_" if s3_path != 'N/A' else ""
    
    return f"""*⚠️ Athena Reporting - ALERT Triggered*

*Query:* {query_id}
*Alert:* {alert_name}
*Date:* {execution_date}
*Matched Records:* {alert_count}
*Threshold:* {operator} {threshold}{csv_section}

_Executed at: {timestamp}_"""


def send_slack_notification(slack_config, message_variables, sns_topic_arn, mode='export'):
    """
    Send Slack notification via SNS with mrkdwn (Slack Markdown) formatting
    
    Args:
        slack_config: Slack configuration dict from query config
        message_variables: Dict of variables for message
        sns_topic_arn: SNS Topic ARN
        mode: 'export' or 'alert' to determine template
    """
    if not slack_config.get('enabled', False):
        logger.info("Slack notifications disabled for this query")
        return
    
    if not sns_topic_arn:
        logger.warning("SNS Topic ARN not configured, cannot send notification")
        return
    
    # Extract common variables
    query_id = message_variables.get('query_id', 'Unknown')
    description = message_variables.get('description', 'N/A')
    total_rows = message_variables.get('total_rows', 0)
    s3_path = message_variables.get('s3_path', 'N/A')
    presigned_url = message_variables.get('presigned_url', 'N/A')
    execution_date = message_variables.get('date', 'Unknown')
    timestamp = message_variables.get('timestamp', 'Unknown')
    
    # Build message using Slack mrkdwn syntax
    if mode == 'export':
        message = build_export_message(
            query_id, description, total_rows, s3_path,
            presigned_url, execution_date, timestamp
        )
    else:  # alert mode
        alert_name = message_variables.get('alert_name', 'Unknown')
        alert_count = message_variables.get('alert_count', 0)
        threshold = message_variables.get('threshold', 0)
        operator = message_variables.get('operator', '>')
        
        message = build_alert_message(
            query_id, alert_name, alert_count, threshold, operator,
            s3_path, presigned_url, execution_date, timestamp
        )
    
    logger.info(f"Sending mrkdwn Slack notification via SNS to topic: {sns_topic_arn}")
    
    try:
        response = sns.publish(
            TopicArn=sns_topic_arn,
            Message=message,
            Subject=f"Athena Reporting: {query_id}"
        )
        
        message_id = response.get('MessageId')
        logger.info(f"Slack notification sent via SNS - MessageId: {message_id}")
        
    except Exception as e:
        logger.error(f"Failed to send SNS notification: {e}")