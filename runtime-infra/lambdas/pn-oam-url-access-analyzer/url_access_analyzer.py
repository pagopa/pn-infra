"""
S3 Presigned URL Access Analyzer
Monitors and analyzes S3 object access via presigned URLs
"""

import json
import os
import boto3
from datetime import datetime
from collections import defaultdict
from typing import Dict, Any, List

# Initialize AWS clients
cloudwatch = boto3.client('cloudwatch')
sns = boto3.client('sns')

# Environment variables
ENVIRONMENT = os.environ.get('ENVIRONMENT', 'production')
SNS_TOPIC_ARN = os.environ.get('SNS_TOPIC_ARN')
BUCKET_NAME = os.environ.get('BUCKET_NAME')
ALERT_THRESHOLD = int(os.environ.get('ALERT_THRESHOLD', '5'))

# In-memory cache for tracking access patterns (Lambda container reuse)
access_tracker = defaultdict(lambda: {'count': 0, 'ips': set(), 'first_seen': None})


def lambda_handler(event, context):
    """
    Main Lambda handler for S3 URL access monitoring
    """
    print(f"Received event: {json.dumps(event)}")
    
    try:
        # Parse CloudTrail event from EventBridge
        detail = event.get('detail', {})
        
        # Extract key information
        event_name = detail.get('eventName')
        event_time = detail.get('eventTime')
        source_ip = detail.get('sourceIPAddress')
        user_agent = detail.get('userAgent')
        error_code = detail.get('errorCode')
        request_params = detail.get('requestParameters', {})
        response_elements = detail.get('responseElements', {})
        
        # Extract S3-specific details
        bucket_name = request_params.get('bucketName')
        object_key = request_params.get('key')
        
        # Determine if this is presigned URL access
        is_presigned = is_presigned_url_access(detail)
        
        # Log the access
        log_entry = {
            'timestamp': event_time,
            'event_name': event_name,
            'bucket': bucket_name,
            'object_key': object_key,
            'source_ip': source_ip,
            'user_agent': user_agent,
            'is_presigned': is_presigned,
            'error_code': error_code
        }
        
        print(f"Access log: {json.dumps(log_entry)}")
        
        # Analyze access pattern
        if event_name == 'GetObject':
            if error_code:
                handle_failed_access(log_entry)
            else:
                handle_successful_access(log_entry)
        
        # Publish custom metrics
        publish_metrics(log_entry)
        
        # Check for suspicious patterns
        if is_suspicious_access(log_entry):
            send_alert(log_entry, "Suspicious access pattern detected")
        
        return {
            'statusCode': 200,
            'body': json.dumps('Access analyzed successfully')
        }
        
    except Exception as e:
        print(f"Error processing event: {str(e)}")
        raise


def is_presigned_url_access(detail: Dict[str, Any]) -> bool:
    """
    Determine if the access was via presigned URL
    Presigned URLs typically don't have userIdentity with IAM credentials
    """
    user_identity = detail.get('userIdentity', {})
    user_type = user_identity.get('type', '')
    
    # Presigned URL access typically shows as:
    # - type: "AWSAccount" or "Unknown"
    # - No sessionContext
    # - Request contains signature parameters
    
    request_params = detail.get('requestParameters', {})
    
    # Check for signature parameters (indicates presigned URL)
    has_signature = any(key in str(request_params) for key in ['X-Amz-Signature', 'Signature'])
    
    # Check user identity type
    is_anonymous_or_account = user_type in ['AWSAccount', 'Unknown', 'AssumedRole']
    
    return has_signature or (is_anonymous_or_account and not user_identity.get('sessionContext'))


def handle_successful_access(log_entry: Dict[str, Any]):
    """
    Handle successful S3 object access
    """
    object_key = log_entry.get('object_key', 'unknown')
    source_ip = log_entry.get('source_ip', 'unknown')
    
    # Track access patterns
    key = f"{object_key}:{source_ip}"
    access_tracker[key]['count'] += 1
    access_tracker[key]['ips'].add(source_ip)
    
    if not access_tracker[key]['first_seen']:
        access_tracker[key]['first_seen'] = log_entry['timestamp']
    
    print(f"PRESIGNED_URL_ACCESS {object_key} from {source_ip}")


def handle_failed_access(log_entry: Dict[str, Any]):
    """
    Handle failed S3 object access attempts
    """
    object_key = log_entry.get('object_key', 'unknown')
    source_ip = log_entry.get('source_ip', 'unknown')
    error_code = log_entry.get('error_code', 'unknown')
    
    print(f"ACCESS_DENIED {object_key} from {source_ip} - Error: {error_code}")
    
    # Track failed attempts
    key = f"failed:{source_ip}"
    access_tracker[key]['count'] += 1
    
    # Alert if too many failures from same IP
    if access_tracker[key]['count'] >= ALERT_THRESHOLD:
        send_alert(log_entry, f"Multiple failed access attempts from {source_ip}")


def is_suspicious_access(log_entry: Dict[str, Any]) -> bool:
    """
    Detect suspicious access patterns
    """
    source_ip = log_entry.get('source_ip', '')
    user_agent = log_entry.get('user_agent', '')
    object_key = log_entry.get('object_key', '')
    
    suspicious_indicators = []
    
    # Check for suspicious user agents
    suspicious_agents = ['curl', 'wget', 'python-requests', 'bot', 'scanner']
    if any(agent in user_agent.lower() for agent in suspicious_agents):
        suspicious_indicators.append(f"Suspicious user agent: {user_agent}")
    
    # Check for rapid access from same IP
    ip_key = f"ip:{source_ip}"
    if access_tracker[ip_key]['count'] > 100:  # More than 100 requests
        suspicious_indicators.append(f"High volume from IP: {source_ip}")
    
    # Check for access to multiple objects from same IP
    if len(access_tracker[ip_key]['ips']) > 50:
        suspicious_indicators.append(f"Access to many objects from: {source_ip}")
    
    if suspicious_indicators:
        print(f"SUSPICIOUS_ACCESS {', '.join(suspicious_indicators)}")
        return True
    
    return False


def publish_metrics(log_entry: Dict[str, Any]):
    """
    Publish custom CloudWatch metrics
    """
    try:
        metrics = []
        
        # Base dimensions
        dimensions = [
            {'Name': 'Environment', 'Value': ENVIRONMENT},
            {'Name': 'BucketName', 'Value': BUCKET_NAME}
        ]
        
        # Metric for total access
        metrics.append({
            'MetricName': 'S3URLAccess',
            'Value': 1,
            'Unit': 'Count',
            'Dimensions': dimensions
        })
        
        # Metric for presigned URL access
        if log_entry.get('is_presigned'):
            metrics.append({
                'MetricName': 'PresignedURLAccess',
                'Value': 1,
                'Unit': 'Count',
                'Dimensions': dimensions
            })
        
        # Metric for failed access
        if log_entry.get('error_code'):
            metrics.append({
                'MetricName': 'FailedS3Access',
                'Value': 1,
                'Unit': 'Count',
                'Dimensions': dimensions + [
                    {'Name': 'ErrorCode', 'Value': log_entry['error_code']}
                ]
            })
        
        # Publish metrics
        if metrics:
            cloudwatch.put_metric_data(
                Namespace='S3URLMonitoring',
                MetricData=metrics
            )
            print(f"Published {len(metrics)} metrics to CloudWatch")
            
    except Exception as e:
        print(f"Error publishing metrics: {str(e)}")


def send_alert(log_entry: Dict[str, Any], message: str):
    """
    Send SNS alert for suspicious activity
    """
    if not SNS_TOPIC_ARN:
        print("SNS topic ARN not configured, skipping alert")
        return
    
    try:
        subject = f"[{ENVIRONMENT}] S3 URL Access Alert"
        
        alert_body = f"""
S3 Presigned URL Access Alert

Alert: {message}

Details:
- Timestamp: {log_entry.get('timestamp')}
- Event: {log_entry.get('event_name')}
- Bucket: {log_entry.get('bucket')}
- Object: {log_entry.get('object_key')}
- Source IP: {log_entry.get('source_ip')}
- User Agent: {log_entry.get('user_agent')}
- Error Code: {log_entry.get('error_code', 'None')}
- Presigned URL: {log_entry.get('is_presigned')}

Environment: {ENVIRONMENT}

Action Required:
1. Review the access pattern in CloudWatch Logs
2. Verify if this is legitimate access
3. Check for any security policy violations
4. Consider blocking the source IP if malicious

CloudWatch Logs: /aws/lambda/{os.environ.get('AWS_LAMBDA_FUNCTION_NAME')}
        """
        
        sns.publish(
            TopicArn=SNS_TOPIC_ARN,
            Subject=subject,
            Message=alert_body
        )
        
        print(f"Alert sent: {message}")
        
    except Exception as e:
        print(f"Error sending alert: {str(e)}")
