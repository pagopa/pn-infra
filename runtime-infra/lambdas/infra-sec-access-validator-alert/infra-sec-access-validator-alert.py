"""
Unauthorized Access Validator Lambda Function

Validates DynamoDB and S3 access against authorized roles from CSV.
Supports cross-account access monitoring.
Publishes metrics using CloudWatch Embedded Metric Format (EMF).

Customer: PN-CONFIDENTIAL-INFORMATION
Resources: pn-ConfidentialObjects (DynamoDB), pn-safestorage (S3)
"""

import json
import boto3
import os
import csv
import hashlib
from io import StringIO
from datetime import datetime

sns = boto3.client('sns')
s3 = boto3.client('s3')

# Environment variables
SNS_TOPIC_ARN = os.environ['SNS_TOPIC_ARN']

# Support for multiple DynamoDB tables (comma-separated list)
# Handles both DYNAMODB_TABLE_NAMES and DYNAMODB_TABLE_NAME for backward compatibility
_raw_ddb_tables = os.environ.get('DYNAMODB_TABLE_NAMES', os.environ.get('DYNAMODB_TABLE_NAME', ''))
DYNAMODB_TABLES = [t.strip() for t in _raw_ddb_tables.split(',') if t.strip()]

S3_BUCKET_NAME = os.environ['S3_BUCKET_NAME']
S3_CRITICAL_PREFIX = os.environ.get('S3_CRITICAL_PREFIX', 'PN_NOTIFICATION_ATTACHMENT')
AUTHORIZED_ROLES_CSV = os.environ.get('AUTHORIZED_ROLES_CSV', '')
CSV_S3_BUCKET = os.environ.get('CSV_S3_BUCKET', '')
CSV_S3_KEY = os.environ.get('CSV_S3_KEY', 'config/authorized-roles.csv')
ENVIRONMENT = os.environ.get('ENVIRONMENT', 'production')
ALERT_ON_CROSS_ACCOUNT = os.environ.get('ALERT_ON_CROSS_ACCOUNT', 'false').lower() == 'true'
EXPECTED_CSV_HASH = os.environ.get('CSV_HASH', '')

# CRITICAL SECURITY: Whitelist of allowed AWS account IDs
# Only roles from these accounts can access resources
ALLOWED_ACCOUNT_IDS = os.environ.get('ALLOWED_ACCOUNT_IDS', '').split(',')
ALLOWED_ACCOUNT_IDS = [acc.strip() for acc in ALLOWED_ACCOUNT_IDS if acc.strip()]


def validate_csv_integrity(csv_content):
    """
    Verify CSV hasn't been tampered with by comparing hash.
    This prevents privilege escalation attacks where someone modifies the CSV.
    """
    if not EXPECTED_CSV_HASH:
        print("WARNING: CSV_HASH not set - integrity check skipped")
        return True
    
    actual_hash = hashlib.sha256(csv_content.encode()).hexdigest()
    
    if actual_hash != EXPECTED_CSV_HASH:
        error_msg = f"CSV INTEGRITY VIOLATION DETECTED!\nExpected hash: {EXPECTED_CSV_HASH}\nActual hash: {actual_hash}"
        print(f"CRITICAL: {error_msg}")
        
        # Send critical alert
        try:
            sns.publish(
                TopicArn=SNS_TOPIC_ARN,
                Subject='CRITICAL: CSV Integrity Violation - Possible Tampering',
                Message=f"""
CRITICAL SECURITY ALERT: CSV INTEGRITY VIOLATION

The authorized roles CSV has been modified without proper deployment!
This could indicate a privilege escalation attack.

Expected SHA256: {EXPECTED_CSV_HASH}
Actual SHA256:   {actual_hash}

IMMEDIATE ACTION REQUIRED:
1. Investigate who modified the CSV
2. Review CloudTrail logs for Lambda configuration changes
3. Compare current CSV with Git repository
4. Restore CSV from Git if unauthorized
5. Review all recent access attempts

Environment: {ENVIRONMENT}
Lambda: {os.environ.get('AWS_LAMBDA_FUNCTION_NAME', 'unknown')}
Time: {datetime.utcnow().isoformat()}
"""
            )
        except Exception as e:
            print(f"Failed to send integrity violation alert: {str(e)}")
        
        raise ValueError("CSV integrity check failed - possible tampering detected")
    
    print(f"CSV integrity verified (hash: {actual_hash[:16]}...)")
    return True


def load_csv_content():
    """
    Load CSV content from environment variable or S3.
    Prioritizes environment variable for speed, falls back to S3 for large files.
    """
    # Try environment variable first (fast, no API calls)
    if AUTHORIZED_ROLES_CSV:
        print("Loading CSV from environment variable")
        return AUTHORIZED_ROLES_CSV
    
    # Fallback to S3 if environment variable is empty or too large
    if CSV_S3_BUCKET:
        print(f"Loading CSV from S3: s3://{CSV_S3_BUCKET}/{CSV_S3_KEY}")
        try:
            response = s3.get_object(Bucket=CSV_S3_BUCKET, Key=CSV_S3_KEY)
            csv_content = response['Body'].read().decode('utf-8')
            print(f"Successfully loaded CSV from S3 ({len(csv_content)} bytes)")
            return csv_content
        except Exception as e:
            print(f"ERROR: Failed to load CSV from S3: {str(e)}")
            raise
    
    raise ValueError("No CSV source configured. Set AUTHORIZED_ROLES_CSV or CSV_S3_BUCKET.")


class AuthorizedRolesRegistry:
    """Parse and manage authorized roles from CSV"""
    
    def __init__(self, csv_content):
        self.roles = []
        self.parse_csv(csv_content)
    
    def parse_csv(self, csv_content):
        """Parse CSV content into structured role data"""
        reader = csv.DictReader(StringIO(csv_content), delimiter=';')
        
        for row in reader:
            self.roles.append({
                'account': row['Account'].strip(),
                'role_name': row['Role'].strip(),
                'arn': row['ARN'].strip(),
                'access': row['Access'].strip(),
                'resources': row['Resources'].strip()
            })
        
        print(f"Loaded {len(self.roles)} authorized roles from CSV")
    
    def is_authorized(self, principal_arn, resource_type, operation, account_id):
        """
        Check if a principal ARN is authorized for the operation
        """
        # CRITICAL SECURITY CHECK: Validate account ID first
        if ALLOWED_ACCOUNT_IDS and account_id not in ALLOWED_ACCOUNT_IDS:
            return False, None, f"Account ID {account_id} not in allowed accounts list. This prevents role name spoofing from unauthorized accounts."
        
        # Extract role name from ARN
        if ':assumed-role/' in principal_arn:
            role_part = principal_arn.split(':assumed-role/')[1]
            role_name = role_part.split('/')[0]
        elif ':role/' in principal_arn:
            role_name = principal_arn.split(':role/')[1]
        elif ':user/' in principal_arn:
            role_name = principal_arn.split(':user/')[1]
        else:
            return False, None, f"Unable to parse principal ARN: {principal_arn}"
        
        # Check against authorized roles
        for role in self.roles:
            if role_name in role['arn'] or role['role_name'] == role_name:
                resource_match = False
                if resource_type == 'dynamodb' and 'DynamoDB' in role['resources']:
                    resource_match = True
                elif resource_type == 's3' and 'S3 bucket' in role['resources']:
                    resource_match = True
                
                if not resource_match:
                    continue
                
                access_level = role['access']
                operation_allowed = self._check_operation_permission(operation, access_level, resource_type)
                
                if operation_allowed:
                    return True, role, f"Authorized: {role['role_name']} with {access_level} access"
                else:
                    return False, role, f"Insufficient permissions: {role['role_name']} has {access_level} but operation requires more"
        
        return False, None, f"Role not found in authorized list: {role_name}"
    
    def _check_operation_permission(self, operation, access_level, resource_type):
        """Check if an operation is allowed for the given access level"""
        read_ops = {
            'dynamodb': ['GetItem', 'BatchGetItem', 'Query', 'Scan'],
            's3': ['GetObject', 'ListBucket', 'HeadObject']
        }
        write_ops = {
            'dynamodb': ['PutItem', 'UpdateItem', 'BatchWriteItem'],
            's3': ['PutObject', 'CopyObject']
        }
        delete_ops = {
            'dynamodb': ['DeleteItem'],
            's3': ['DeleteObject', 'DeleteObjects']
        }
        restore_ops = {
            's3': ['RestoreObject']
        }
        
        if access_level in ['Full', 'FullAdmin', 'MasterAdmin']:
            return True
        if 'ReadOnly' in access_level:
            return operation in read_ops.get(resource_type, [])
        if 'Read/Write' in access_level:
            return operation in read_ops.get(resource_type, []) or operation in write_ops.get(resource_type, [])
        if 'Read/Write/Delete' in access_level:
            return (operation in read_ops.get(resource_type, []) or 
                    operation in write_ops.get(resource_type, []) or 
                    operation in delete_ops.get(resource_type, []))
        if 'ReadOnly/Restore' in access_level:
            return (operation in read_ops.get(resource_type, []) or 
                    operation in restore_ops.get(resource_type, []))
        return False


# Initialize registry (loaded once per Lambda container lifecycle)
csv_content = load_csv_content()

# Validate CSV integrity before using it
validate_csv_integrity(csv_content)

registry = AuthorizedRolesRegistry(csv_content)


def lambda_handler(event, context):
    """
    Main handler function.
    Processes CloudTrail events from EventBridge via SQS and validates access.
    """
    print(f"Processing event: {json.dumps(event)}")
    
    failed_items = []
    
    for record in event.get('Records', []):
        try:
            sqs_body = json.loads(record['body'])
            detail = sqs_body.get('detail', {})
        
            event_name = detail.get('eventName')
            event_source = detail.get('eventSource')
            
            user_identity = detail.get('userIdentity', {})
            principal_arn = user_identity.get('arn', '')
            account_id = user_identity.get('accountId', '')
            
            request_params = detail.get('requestParameters', {})
            
            resource_type = None
            resource_name = None
            object_key = None
            
            if event_source == 'dynamodb.amazonaws.com':
                resource_type = 'dynamodb'
                # Extract specific table name from CloudTrail event
                resource_name = request_params.get('tableName', 'UnknownTable')
                
                # Safety check: log if we get an event for a table not in our allowed list
                if DYNAMODB_TABLES and resource_name not in DYNAMODB_TABLES and resource_name != 'UnknownTable':
                    print(f"INFO: Event received for table {resource_name} which is not in the primary DYNAMODB_TABLES list.")
                    
            elif event_source == 's3.amazonaws.com':
                resource_type = 's3'
                resource_name = request_params.get('bucketName', S3_BUCKET_NAME)
                object_key = request_params.get('key', '')
                
                if object_key and not object_key.startswith(f"{S3_CRITICAL_PREFIX}/"):
                    print(f"WARNING: S3 event for non-critical prefix: {object_key} (expected: {S3_CRITICAL_PREFIX}/)")
            
            print(f"Access attempt: {principal_arn} (Account: {account_id}) -> {resource_type}:{resource_name}{f'/{object_key}' if object_key else ''} ({event_name})")
            
            is_authorized, matched_role, reason = registry.is_authorized(
                principal_arn, 
                resource_type, 
                event_name,
                account_id
            )
            
            publish_metric('AccessAttempts', 1, resource_type, event_name)
            
            if is_authorized:
                print(f"AUTHORIZED: {reason}")
                publish_metric('AuthorizedAccess', 1, resource_type, event_name)
                log_access(detail, 'AUTHORIZED', matched_role, reason)
            else:
                print(f"UNAUTHORIZED: {reason}")
                publish_metric('UnauthorizedAccess', 1, resource_type, event_name)
                send_unauthorized_access_alert(detail, reason, matched_role)
                log_access(detail, 'UNAUTHORIZED', matched_role, reason)
        
        except Exception as e:
            print(f"Error processing record: {str(e)}")
            import traceback
            traceback.print_exc()
            
            publish_metric('ValidationErrors', 1, 'unknown', 'error')
            
            failed_items.append({
                'itemIdentifier': record['messageId']
            })
    
    return {
        'batchItemFailures': failed_items
    }


def publish_metric(metric_name, value, resource_type, operation):
    """
    Publish custom CloudWatch metric using Embedded Metric Format (EMF).
    This avoids direct CloudWatch API calls, preventing throttling and reducing costs.
    """
    try:
        # EMF requires timestamp in milliseconds
        timestamp = int(datetime.utcnow().timestamp() * 1000)
        
        # Construct the EMF JSON payload
        emf_payload = {
            "_aws": {
                "Timestamp": timestamp,
                "CloudWatchMetrics": [
                    {
                        "Namespace": "CustomSecurity",
                        "Dimensions": [["Environment", "ResourceType", "Operation"]],
                        "Metrics": [
                            {
                                "Name": metric_name,
                                "Unit": "Count"
                            }
                        ]
                    }
                ]
            },
            "Environment": ENVIRONMENT,
            "ResourceType": resource_type,
            "Operation": operation,
            metric_name: value  # The actual metric value must be a top-level property matching the Name
        }
        
        # Printing to stdout automatically registers the metric in CloudWatch via the logs agent
        print(json.dumps(emf_payload))
        
    except Exception as e:
        print(f"Error building EMF metric: {str(e)}")


def log_access(detail, status, matched_role, reason):
    """Log access attempt for audit trail"""
    log_entry = {
        'timestamp': detail.get('eventTime'),
        'status': status,
        'principal': detail.get('userIdentity', {}).get('arn'),
        'operation': detail.get('eventName'),
        'resource': detail.get('requestParameters', {}),
        'source_ip': detail.get('sourceIPAddress'),
        'matched_role': matched_role['role_name'] if matched_role else None,
        'reason': reason
    }
    print(f"ACCESS_LOG: {json.dumps(log_entry)}")


def send_unauthorized_access_alert(detail, reason, matched_role):
    """Send SNS alert for unauthorized access"""
    try:
        user_identity = detail.get('userIdentity', {})
        request_params = detail.get('requestParameters', {})
        event_name = detail.get('eventName')
        
        object_info = []
        if 'key' in request_params:
            object_info.append(f"s3://{request_params.get('bucketName')}/{request_params['key']}")
        elif 'delete' in request_params and isinstance(request_params['delete'], dict):
            objects = request_params['delete'].get('object', [])
            if isinstance(objects, list):
                for obj in objects[:10]:
                    if isinstance(obj, dict) and 'key' in obj:
                        object_info.append(f"s3://{request_params.get('bucketName')}/{obj['key']}")
                if len(objects) > 10:
                    object_info.append(f"... and {len(objects) - 10} more objects")
        
        message_lines = [
            "=" * 70,
            "⚠️  SECURITY ALERT: UNAUTHORIZED ACCESS DETECTED",
            "=" * 70,
            "",
            f"Environment: {ENVIRONMENT}",
            f"Time: {detail.get('eventTime')}",
            f"Event ID: {detail.get('eventID')}",
            "",
            "PRINCIPAL INFORMATION:",
            "-" * 70,
            f"  Type: {user_identity.get('type')}",
            f"  ARN: {user_identity.get('arn')}",
            f"  Principal ID: {user_identity.get('principalId')}",
            f"  Account ID: {user_identity.get('accountId')}",
            f"  Source IP: {detail.get('sourceIPAddress')}",
            f"  User Agent: {detail.get('userAgent')}",
            "",
            "ACCESS ATTEMPT:",
            "-" * 70,
            f"  Operation: {event_name}",
            f"  Event Source: {detail.get('eventSource')}",
            # Modified to show dynamic table name or bucket name safely
            f"  Resource: {request_params.get('tableName', request_params.get('bucketName', 'Unknown'))}",
        ]
        
        if object_info:
            message_lines.append("  Objects:")
            for obj in object_info:
                message_lines.append(f"    - {obj}")
        else:
            message_lines.append(f"  Request Details: {json.dumps(request_params, indent=4)}")
        
        message_lines.extend([
            "",
            "MONITORING RESULT:",
            "-" * 70,
            f"  Status: UNAUTHORIZED (Not in authorized roles list)",
            f"  Reason: {reason}",
            f"  Note: This is a MONITORING alert - the operation was NOT blocked",
        ])
        
        if matched_role:
            message_lines.extend([
                f"  Matched Role: {matched_role['role_name']}",
                f"  Allowed Access: {matched_role['access']}",
                f"  Allowed Resources: {matched_role['resources']}"
            ])
        
        message_lines.extend([
            "",
            "=" * 70,
            "RECOMMENDED ACTIONS:",
            "=" * 70,
            "1. Review if this access should be authorized",
            "2. If legitimate, add the role to authorized-roles.csv",
            "3. If suspicious, investigate the principal and source IP",
            "4. Review CloudTrail logs for full event details",
            "5. Check if credentials may be compromised",
            "",
            "IMPORTANT: This is a detective control (monitoring only).",
            "The operation was NOT prevented. To block unauthorized access,",
            "implement preventive controls (IAM policies, SCPs, bucket policies).",
            "",
            f"CloudTrail Event ID: {detail.get('eventID')}",
            f"AWS Region: {detail.get('awsRegion')}",
            "",
            "CloudWatch Logs:",
            f"  /aws/lambda/{os.environ.get('AWS_LAMBDA_FUNCTION_NAME', 'unknown')}",
            ""
        ])
        
        message = "\n".join(message_lines)
        
        response = sns.publish(
            TopicArn=SNS_TOPIC_ARN,
            Subject=f'CRITICAL: Unauthorized Access Detected - {ENVIRONMENT}',
            Message=message
        )
        
        print(f"Alert sent - SNS MessageId: {response['MessageId']}")
        
    except Exception as e:
        print(f"Error sending alert: {str(e)}")
        raise