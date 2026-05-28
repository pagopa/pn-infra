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


def build_alert_subject(severity, alert_type):
    return f"[{ENVIRONMENT}] {severity}: {alert_type}"


def build_alert_body(alert_type, severity, detected_at, resource, operation, summary, details=None):
    lines = [
        f"Alert Type: {alert_type}",
        f"Severity: {severity}",
        f"Environment: {ENVIRONMENT}",
        f"Detected At: {detected_at or datetime.utcnow().isoformat()}",
        f"Resource: {resource or 'Unknown'}",
        f"Operation/Event: {operation or 'Unknown'}",
        f"Summary: {summary}",
    ]

    if details:
        lines.append("")
        lines.append("Details:")
        for key, value in details.items():
            if value is None or value == "":
                continue
            lines.append(f"{key}: {value}")

    return "\n".join(lines)


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
            message = build_alert_body(
                alert_type='CSV Integrity Violation',
                severity='CRITICAL',
                detected_at=datetime.utcnow().isoformat(),
                resource=(f"s3://{CSV_S3_BUCKET}/{CSV_S3_KEY}" if CSV_S3_BUCKET else 'AUTHORIZED_ROLES_CSV'),
                operation='CSV validation',
                summary='Authorized roles CSV hash does not match the expected value.',
                details={
                    'Expected SHA256': EXPECTED_CSV_HASH,
                    'Actual SHA256': actual_hash,
                    'Lambda': os.environ.get('AWS_LAMBDA_FUNCTION_NAME', 'unknown'),
                    'Action Required': (
                        'Investigate who modified the CSV; review CloudTrail for Lambda configuration changes; '
                        'compare the current CSV with Git; restore it if unauthorized; review recent access attempts.'
                    )
                }
            )
            sns.publish(
                TopicArn=SNS_TOPIC_ARN,
                Subject=build_alert_subject('CRITICAL', 'CSV Integrity Violation'),
                Message=message
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


# CSV schema constants
_REQUIRED_CSV_COLUMNS = {'Role', 'ARN', 'Access', 'Resources'}
_OPTIONAL_CSV_COLUMNS = set()
_VALID_ACCESS_LEVELS = {'Full', 'ReadOnly', 'ReadWrite'}

# EMF metric publication constants
EMF_NAMESPACE = 'CustomSecurity/AccessValidator'
EMF_DIMENSIONS = [["ResourceType", "Operation"]]
EMF_METRIC_UNIT = 'Count'


class AuthorizedRolesRegistry:
    """Parse and manage authorized roles from CSV.
    
    Expected CSV format (semicolon-delimited):
        Role;ARN;Access;Resources
    
    Required columns: Role, ARN, Access, Resources
    Access must be one of: Full, ReadOnly, ReadWrite
    """
    
    def __init__(self, csv_content):
        self.roles = []
        self.parse_csv(csv_content)
    
    def parse_csv(self, csv_content):
        """Parse and strictly validate CSV content into structured role data.
        
        Raises ValueError if:
        - Missing any of the required columns: Role, ARN, Access, Resources
        - Contains columns other than required + optional ones
        - Any row contains an access level not in {Full, ReadOnly, ReadWrite}
        """
        reader = csv.DictReader(StringIO(csv_content), delimiter=';')
        
        # Validate CSV structure
        if not reader.fieldnames:
            raise ValueError("CSV is empty or has no headers")
        
        actual_columns = {col.strip() for col in reader.fieldnames}
        
        # Check required columns
        missing = _REQUIRED_CSV_COLUMNS - actual_columns
        if missing:
            raise ValueError(
                f"CSV missing required columns: {sorted(missing)}. "
                f"Required: {sorted(_REQUIRED_CSV_COLUMNS)}"
            )
        
        # Check for unexpected columns
        allowed = _REQUIRED_CSV_COLUMNS | _OPTIONAL_CSV_COLUMNS
        extra = actual_columns - allowed
        if extra:
            raise ValueError(
                f"CSV contains unexpected columns: {sorted(extra)}. "
                f"Allowed: {sorted(allowed)}"
            )
        
        for row_num, row in enumerate(reader, start=2):
            arn       = row['ARN'].strip()
            access    = row['Access'].strip()
            resources = row['Resources'].strip()
            
            if access not in _VALID_ACCESS_LEVELS:
                raise ValueError(
                    f"Invalid access level '{access}' on CSV row {row_num} for ARN '{arn}'. "
                    f"Allowed values: {sorted(_VALID_ACCESS_LEVELS)}"
                )
            
            self.roles.append({
                'arn':       arn,
                'access':    access,
                'resources': resources
            })
        
        print(f"Loaded {len(self.roles)} authorized roles from CSV")
    
    def is_authorized(self, principal_arn, resource_type, operation, account_id):
        """
        Check if a principal ARN is authorized for the operation.
        
        For assumed-role principals, extracts the role name and account from the ARN
        and matches against CSV entries by role name + account, not by full ARN substring.
        """
        # CRITICAL SECURITY CHECK: Validate account ID first
        if ALLOWED_ACCOUNT_IDS and account_id not in ALLOWED_ACCOUNT_IDS:
            return False, None, (
                f"Account ID {account_id} not in allowed accounts list. "
                "This prevents role ARN spoofing from unauthorized accounts."
            )
        
        # Extract principal's role name and account from CloudTrail ARN
        principal_role_name, principal_account = self._extract_role_info(principal_arn)
        
        if not principal_role_name:
            return False, None, f"Unable to parse principal ARN: {principal_arn}"
        
        # Check against authorized roles by role name + account
        for role in self.roles:
            csv_role_name, csv_account = self._extract_role_info(role['arn'])
            
            # Match both role name and account ID
            if principal_role_name != csv_role_name or principal_account != csv_account:
                continue
            
            resource_match = False
            role_resources = role['resources']
            role_resources_lower = role_resources.lower()
            if resource_type == 'dynamodb':
                # Support both legacy labels ("DynamoDB") and ARN-based values
                if (
                    'dynamodb' in role_resources_lower or
                    resource_type in role_resources_lower
                ):
                    resource_match = True
            elif resource_type == 's3':
                # Support both legacy labels ("S3 bucket") and ARN-based values
                if (
                    's3 bucket' in role_resources_lower or
                    'arn:aws:s3:::' in role_resources_lower or
                    resource_type in role_resources_lower
                ):
                    resource_match = True
            
            if not resource_match:
                continue
            
            access_level = role['access']
            operation_allowed = self._check_operation_permission(operation, access_level, resource_type)
            
            if operation_allowed:
                return True, role, f"Authorized: {csv_role_name} with {access_level} access"
            else:
                return False, role, (
                    f"Insufficient permissions: {csv_role_name} has {access_level} "
                    "but operation requires more"
                )
        
        return False, None, (
            f"Role not found "
            "in authorized list {principal_role_name} (account: {principal_account}) "
        )
    
    @staticmethod

    
    def _extract_role_info(arn):
        """
        Extract role name and account ID from an IAM ARN.
        
        Handles:
        - arn:aws:iam::123456789:role/MyRole → ('MyRole', '123456789')
        - arn:aws:iam::123456789:role/path/To/MyRole → ('MyRole', '123456789')
        - arn:aws:iam::123456789:assumed-role/MyRole/session → ('MyRole', '123456789')
        - arn:aws:iam::123456789:user/MyUser → ('MyUser', '123456789')
        
        Returns: (role_name, account_id) or (None, None) if unable to parse
        """
        parts = arn.split(":")
        if len(parts) < 6:
            return None, None
        
        account_id = parts[4]
        resource_part = ":".join(parts[5:])
        
        # Extract role name from various ARN formats
        role_name = None
        if resource_part.startswith("role/"):
            # role/MyRole or role/path/To/MyRole -> take last segment as role name
            role_name = resource_part[len("role/"):].split("/")[-1]
        elif resource_part.startswith("assumed-role/"):
            # assumed-role/MyRole/session-name
            assumed_parts = resource_part.split("/")
            if len(assumed_parts) >= 2:
                role_name = assumed_parts[1]
        elif resource_part.startswith("user/"):
            # user/MyUser
            role_name = resource_part[len("user/"):].split("/")[-1]
        
        return role_name, account_id
    
    def _check_operation_permission(self, operation, access_level, resource_type):
        """Check if an operation is allowed for the given access level.
        
        Supported access levels:
          Full      – all operations
          ReadOnly  – read operations only
          ReadWrite – read and write operations
        """
        read_ops = {
            'dynamodb': ['GetItem', 'BatchGetItem', 'Query', 'Scan'],
            's3': ['GetObject', 'ListBucket', 'HeadObject']
        }
        write_ops = {
            'dynamodb': ['PutItem', 'UpdateItem', 'BatchWriteItem'],
            's3': ['PutObject', 'CopyObject']
        }
        
        if access_level == 'Full':
            return True
        if access_level == 'ReadOnly':
            return operation in read_ops.get(resource_type, [])
        if access_level == 'ReadWrite':
            return (
                operation in read_ops.get(resource_type, []) or
                operation in write_ops.get(resource_type, [])
            )
        # Should never reach here after CSV validation, but be safe
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
    #print(f"Processing event: {json.dumps(event)}")
    
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
                #Se la chiave contiene favicon.ico ignore                   
                if object_key and not object_key.startswith(f"{S3_CRITICAL_PREFIX}"):
                    pass
                    #print(f"WARNING: S3 event for non-critical prefix: {object_key} (expected: {S3_CRITICAL_PREFIX})")
            
            is_authorized, matched_role, reason = registry.is_authorized(
                principal_arn, 
                resource_type, 
                event_name,
                account_id
            )
            
            publish_emf_metric('AccessAttempts', 1, resource_type, event_name)
            
            if is_authorized:
                pass
                #print(f"AUTHORIZED: {reason}")
                #publish_emf_metric('AuthorizedAccess', 1, resource_type, event_name)
                #log_access(detail, 'AUTHORIZED', matched_role, reason)
            else:
                print(f"UNAUTHORIZED: {reason} | Access attempt: {principal_arn} (Account: {account_id}) -> {resource_type}:{resource_name}{f'/{object_key}' if object_key else ''} ({event_name})")
                publish_emf_metric('UnauthorizedAccess', 1, resource_type, event_name)
                send_unauthorized_access_alert(detail, reason, matched_role)
                log_access(detail, 'UNAUTHORIZED', matched_role, reason)
        
        except Exception as e:
            print(f"Error processing record: {str(e)}")
            import traceback
            traceback.print_exc()
            
            publish_emf_metric('ValidationErrors', 1, 'unknown', 'error')
            
            failed_items.append({
                'itemIdentifier': record['messageId']
            })
    
    return {
        'batchItemFailures': failed_items
    }


def publish_emf_metric(metric_name, value, resource_type, operation):
    """
    Publish a custom CloudWatch metric using Embedded Metric Format (EMF).

    EMF metrics are emitted by printing a JSON payload to stdout.
    The top-level metric key must exactly match the metric Name definition.
    """
    try:
        timestamp_ms = int(datetime.utcnow().timestamp() * 1000)

        emf_metric_definition = {
            "Name": metric_name,
            "Unit": EMF_METRIC_UNIT
        }
        
        emf_payload = {
            "_aws": {
                "Timestamp": timestamp_ms,
                "CloudWatchMetrics": [
                    {
                        "Namespace": EMF_NAMESPACE,
                        "Dimensions": EMF_DIMENSIONS,
                        "Metrics": [emf_metric_definition]
                    }
                ]
            },
            "ResourceType": resource_type,
            "Operation": operation,
            metric_name: value
        }
        
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
        'matched_role_arn': matched_role['arn'] if matched_role else None,
        'reason': reason,
        'resource_type': detail.get('eventSource')
    }
    print(f"ACCESS_LOG: {json.dumps(log_entry)}")


def send_unauthorized_access_alert(detail, reason, matched_role):
    """Send SNS alert for unauthorized access"""
    try:
        user_identity = detail.get('userIdentity', {})
        request_params = detail.get('requestParameters', {})
        event_name = detail.get('eventName')
        event_source = detail.get('eventSource')
        
        object_info = []
        if event_source == 's3.amazonaws.com' and isinstance(request_params.get('key'), str):
            object_info.append(f"s3://{request_params.get('bucketName')}/{request_params['key']}")
        elif event_source == 's3.amazonaws.com' and 'delete' in request_params and isinstance(request_params['delete'], dict):
            objects = request_params['delete'].get('object', [])
            if isinstance(objects, list):
                for obj in objects[:10]:
                    if isinstance(obj, dict) and 'key' in obj:
                        object_info.append(f"s3://{request_params.get('bucketName')}/{obj['key']}")
                if len(objects) > 10:
                    object_info.append(f"... and {len(objects) - 10} more objects")
        
        resource_name = request_params.get('tableName', request_params.get('bucketName', 'Unknown'))
        resource = ", ".join(object_info) if object_info else resource_name

        message = build_alert_body(
            alert_type='Unauthorized Access',
            severity='CRITICAL',
            detected_at=detail.get('eventTime'),
            resource=resource,
            operation=event_name,
            summary='Access attempt not present in the authorized roles list or not allowed for the requested operation.',
            details={
                'Event ID': detail.get('eventID'),
                'Event Source': detail.get('eventSource'),
                'Principal Type': user_identity.get('type'),
                'Principal ARN': user_identity.get('arn'),
                'Principal ID': user_identity.get('principalId'),
                'Account ID': user_identity.get('accountId'),
                'Source IP': detail.get('sourceIPAddress'),
                'User Agent': detail.get('userAgent'),
                'Objects': '; '.join(object_info) if object_info else None,
                'Request Details': json.dumps(request_params, indent=2) if not object_info else None,
                'Reason': reason,
                'Matched Role ARN': matched_role['arn'] if matched_role else None,
                'Allowed Access': matched_role['access'] if matched_role else None,
                'Allowed Resources': matched_role['resources'] if matched_role else None,
                'AWS Region': detail.get('awsRegion'),
                'CloudWatch Logs': f"/aws/lambda/{os.environ.get('AWS_LAMBDA_FUNCTION_NAME', 'unknown')}",
                'Action Required': (
                    'Review if this access should be authorized; if legitimate add the role to authorized-roles.csv; '
                    'if suspicious investigate the principal and source IP; review CloudTrail logs; check credential compromise.'
                ),
                'Note': 'This is a detective control. The operation was not blocked.',
            }
        )
        
        response = sns.publish(
            TopicArn=SNS_TOPIC_ARN,
            Subject=build_alert_subject('CRITICAL', 'Unauthorized Access'),
            Message=message
        )
        
        print(f"Alert sent - SNS MessageId: {response['MessageId']}")
        
    except Exception as e:
        print(f"Error sending alert: {str(e)}")
        raise