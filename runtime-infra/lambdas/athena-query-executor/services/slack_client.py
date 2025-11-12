"""Slack notification service layer - SNS only"""
import boto3
import json
from config import logger

sns = boto3.client('sns')


def format_message(template, variables):
    """
    Format message template with variables
    
    Args:
        template: Message template string with {variable} placeholders
        variables: Dict of variable values
    
    Returns:
        Formatted message string
    """
    try:
        return template.format(**variables)
    except KeyError as e:
        logger.error(f"Missing variable in message template: {e}")
        # Return template with missing variables highlighted
        return template + f"\n\n[ERROR: Missing variable {e}]"


def send_slack_notification(slack_config, message_variables, sns_topic_arn):
    """
    Send Slack notification via SNS → Email → Slack channel
    
    Args:
        slack_config: Slack configuration dict from query config
        message_variables: Dict of variables for message template
        sns_topic_arn: SNS Topic ARN (configured in environment or passed)
    """
    if not slack_config.get('enabled', False):
        logger.info("Slack notifications disabled for this query")
        return
    
    if not sns_topic_arn:
        logger.warning("SNS Topic ARN not configured, cannot send notification")
        return
    
    # Format message from template
    message_template = slack_config.get('message_template', 'Query completed: {query_id}')
    message = format_message(message_template, message_variables)
    
    logger.info(f"Sending Slack notification via SNS to topic: {sns_topic_arn}")
    
    try:
        # Publish to SNS topic (which has email subscription to Slack channel)
        response = sns.publish(
            TopicArn=sns_topic_arn,
            Message=message,
            Subject=f"Athena Query Notification: {message_variables.get('query_id', 'Unknown')}"
        )
        
        message_id = response.get('MessageId')
        logger.info(f"Slack notification sent via SNS - MessageId: {message_id}")
        
    except Exception as e:
        logger.error(f"Failed to send SNS notification: {e}")
        # Don't raise - notification failure shouldn't fail the entire Lambda