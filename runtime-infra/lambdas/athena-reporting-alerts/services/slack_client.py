"""Slack notification service layer - SNS with HTML email support"""
import boto3
import json
from config import logger

sns = boto3.client('sns')


def build_export_message_plain(query_id, description, total_rows, s3_path, presigned_url, execution_date, timestamp):
    """Build plain text message for export mode (fallback)"""
    return f"""Athena Reporting - Export Complete

Query: {query_id}
Description: {description}
Date: {execution_date}
Total Records: {total_rows}

S3 Path: {s3_path}

Download CSV Report (valid 24h):
{presigned_url}

Executed at: {timestamp}"""


def build_export_message_html(query_id, description, total_rows, s3_path, presigned_url, execution_date, timestamp):
    """Build HTML message for export mode"""
    return f"""<html>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
<div style="max-width: 600px; margin: 0 auto; padding: 20px;">
  <h2 style="color: #2c3e50; border-bottom: 3px solid #3498db; padding-bottom: 10px;">
    📊 Athena Reporting - Export Complete
  </h2>
  
  <table style="width: 100%; border-collapse: collapse; margin: 20px 0;">
    <tr>
      <td style="padding: 8px; font-weight: bold; width: 150px;">Query:</td>
      <td style="padding: 8px;">{query_id}</td>
    </tr>
    <tr style="background-color: #f8f9fa;">
      <td style="padding: 8px; font-weight: bold;">Description:</td>
      <td style="padding: 8px;">{description}</td>
    </tr>
    <tr>
      <td style="padding: 8px; font-weight: bold;">Date:</td>
      <td style="padding: 8px;">{execution_date}</td>
    </tr>
    <tr style="background-color: #f8f9fa;">
      <td style="padding: 8px; font-weight: bold;">Total Records:</td>
      <td style="padding: 8px;">{total_rows}</td>
    </tr>
    <tr>
      <td style="padding: 8px; font-weight: bold;">S3 Path:</td>
      <td style="padding: 8px; font-size: 11px; word-break: break-all;">{s3_path}</td>
    </tr>
  </table>
  
  <div style="text-align: center; margin: 30px 0;">
    <a href="{presigned_url}"
       style="display: inline-block; padding: 12px 30px; background-color: #3498db;
              color: white; text-decoration: none; border-radius: 5px; font-weight: bold;
              box-shadow: 0 2px 5px rgba(0,0,0,0.2);">
      📥 Download CSV Report
    </a>
    <p style="margin-top: 10px; font-size: 12px; color: #7f8c8d;">
      Link valid for 24 hours
    </p>
  </div>
  
  <p style="font-size: 12px; color: #95a5a6; margin-top: 30px; border-top: 1px solid #ecf0f1; padding-top: 10px;">
    Executed at: {timestamp}
  </p>
</div>
</body>
</html>"""


def build_alert_message_plain(query_id, alert_name, alert_count, threshold, operator, s3_path, presigned_url, execution_date, timestamp):
    """Build plain text message for alert mode (fallback)"""
    csv_section = f"\nS3 Path: {s3_path}\n\nDownload CSV Report (valid 24h):\n{presigned_url}" if s3_path != 'N/A' else ""
    
    return f"""Athena Reporting - ALERT Triggered

Query: {query_id}
Alert: {alert_name}
Date: {execution_date}
Matched Records: {alert_count}
Threshold: {operator} {threshold}{csv_section}

Executed at: {timestamp}"""


def build_alert_message_html(query_id, alert_name, alert_count, threshold, operator, s3_path, presigned_url, execution_date, timestamp):
    """Build HTML message for alert mode"""
    csv_section_html = f"""
  <table style="width: 100%; border-collapse: collapse; margin: 20px 0;">
    <tr style="background-color: #f8f9fa;">
      <td style="padding: 8px; font-weight: bold; width: 150px;">S3 Path:</td>
      <td style="padding: 8px; font-size: 11px; word-break: break-all;">{s3_path}</td>
    </tr>
  </table>
  
  <div style="text-align: center; margin: 30px 0;">
    <a href="{presigned_url}"
       style="display: inline-block; padding: 12px 30px; background-color: #e74c3c;
              color: white; text-decoration: none; border-radius: 5px; font-weight: bold;
              box-shadow: 0 2px 5px rgba(0,0,0,0.2);">
      📥 Download Alert Data
    </a>
    <p style="margin-top: 10px; font-size: 12px; color: #7f8c8d;">
      Link valid for 24 hours
    </p>
  </div>
""" if s3_path != 'N/A' else ""
    
    return f"""<html>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
<div style="max-width: 600px; margin: 0 auto; padding: 20px;">
  <h2 style="color: #e74c3c; border-bottom: 3px solid #e74c3c; padding-bottom: 10px;">
    ⚠️ Athena Reporting - ALERT Triggered
  </h2>
  
  <table style="width: 100%; border-collapse: collapse; margin: 20px 0;">
    <tr>
      <td style="padding: 8px; font-weight: bold; width: 150px;">Query:</td>
      <td style="padding: 8px;">{query_id}</td>
    </tr>
    <tr style="background-color: #f8f9fa;">
      <td style="padding: 8px; font-weight: bold;">Alert:</td>
      <td style="padding: 8px; color: #e74c3c; font-weight: bold;">{alert_name}</td>
    </tr>
    <tr>
      <td style="padding: 8px; font-weight: bold;">Date:</td>
      <td style="padding: 8px;">{execution_date}</td>
    </tr>
    <tr style="background-color: #f8f9fa;">
      <td style="padding: 8px; font-weight: bold;">Matched Records:</td>
      <td style="padding: 8px; font-weight: bold; color: #e74c3c;">{alert_count}</td>
    </tr>
    <tr>
      <td style="padding: 8px; font-weight: bold;">Threshold:</td>
      <td style="padding: 8px;">{operator} {threshold}</td>
    </tr>
  </table>
  {csv_section_html}
  
  <p style="font-size: 12px; color: #95a5a6; margin-top: 30px; border-top: 1px solid #ecf0f1; padding-top: 10px;">
    Executed at: {timestamp}
  </p>
</div>
</body>
</html>"""


def send_slack_notification(slack_config, message_variables, sns_topic_arn, mode='export'):
    """
    Send Slack notification via SNS with HTML and plain text fallback
    
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
    
    # Build both plain text and HTML messages
    if mode == 'export':
        plain_message = build_export_message_plain(
            query_id, description, total_rows, s3_path,
            presigned_url, execution_date, timestamp
        )
        html_message = build_export_message_html(
            query_id, description, total_rows, s3_path,
            presigned_url, execution_date, timestamp
        )
    else:  # alert mode
        alert_name = message_variables.get('alert_name', 'Unknown')
        alert_count = message_variables.get('alert_count', 0)
        threshold = message_variables.get('threshold', 0)
        operator = message_variables.get('operator', '>')
        
        plain_message = build_alert_message_plain(
            query_id, alert_name, alert_count, threshold, operator,
            s3_path, presigned_url, execution_date, timestamp
        )
        html_message = build_alert_message_html(
            query_id, alert_name, alert_count, threshold, operator,
            s3_path, presigned_url, execution_date, timestamp
        )
    
    logger.info(f"Sending HTML+plain Slack notification via SNS to topic: {sns_topic_arn}")
    
    try:
        # Use MessageStructure='json' to send both plain and HTML
        message_json = {
            "default": plain_message,  # Fallback for non-email endpoints
            "email": html_message       # HTML for email (Slack)
        }
        
        response = sns.publish(
            TopicArn=sns_topic_arn,
            Message=json.dumps(message_json),
            MessageStructure='json',
            Subject=f"Athena Reporting: {query_id}"
        )
        
        message_id = response.get('MessageId')
        logger.info(f"Slack notification sent via SNS - MessageId: {message_id}")
        
    except Exception as e:
        logger.error(f"Failed to send SNS notification: {e}")