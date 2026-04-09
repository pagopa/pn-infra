import json
import boto3
import os
import base64
import ast
from datetime import datetime
from decimal import Decimal
from collections import defaultdict

# AWS clients
sns = boto3.client('sns')

# Environment variables
SNS_TOPIC_ARN = os.environ.get('SNS_TOPIC_ARN')
ENVIRONMENT = os.environ.get('ENVIRONMENT', 'Missing')

# Parsing ultra-resiliente per TABLE_CONFIG
raw_config = os.environ.get('TABLE_CONFIG', '{}').strip()

if raw_config.startswith('"') and raw_config.endswith('"'):
    raw_config = raw_config[1:-1]
elif raw_config.startswith("'") and raw_config.endswith("'"):
    raw_config = raw_config[1:-1]

raw_config = raw_config.replace('\\"', '"')

try:
    TABLE_CONFIG = json.loads(raw_config)
except json.JSONDecodeError:
    try:
        TABLE_CONFIG = ast.literal_eval(raw_config)
    except Exception as e:
        print(f"Error parsing TABLE_CONFIG with fallback: {e}")
        TABLE_CONFIG = {}

if not isinstance(TABLE_CONFIG, dict):
    TABLE_CONFIG = {}

# LOG 1: Verifica configurazione iniziale
print(f"Initialization complete. TABLE_CONFIG loaded: {TABLE_CONFIG}")

# CloudWatch EMF namespace
METRIC_NAMESPACE = 'CustomSecurity/DynamoDB'


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

TABLE_POLICIES = {
    "no-delete": {"INSERT", "MODIFY"},
    "append-only": {"INSERT"},
    "standard": {"INSERT", "MODIFY", "REMOVE"},
}

VIOLATION_METRIC_BY_EVENT = {
    "REMOVE": "DeletionViolation",
    "MODIFY": "ModificationViolation",
    "INSERT": "InsertionViolation",
}


class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)


def lambda_handler(event, context):
    num_records = len(event.get('Records', []))
    print(f"Starting Lambda handler. Processing {num_records} Kinesis records.")
    
    violations = []
    allowed_operations_count = defaultdict(int)
    normalized_table_config = normalize_table_config(TABLE_CONFIG)

    for kinesis_record in event.get('Records', []):
        try:
            payload_b64 = kinesis_record['kinesis']['data']
            payload_str = base64.b64decode(payload_b64).decode('utf-8')
            record = json.loads(payload_str)
            
            event_name = record.get('eventName')
            table_name = record.get('tableName')

            if not event_name or not table_name:
                continue

            table_type = normalized_table_config.get(table_name)
            if not table_type:
                continue

            if is_violation(event_name, table_type):
                violation_obj = build_violation(record, table_name, table_type)
                violations.append(violation_obj)
                
                # LOG DETTAGLIATO SU CLOUDWATCH
                print(f"VIOLATION DETECTED: Operation {event_name} not allowed on table {table_name} ({table_type})")
                print(f"VIOLATION DETAIL PAYLOAD: {json.dumps(violation_obj, cls=DecimalEncoder)}")
                
                metric_name = VIOLATION_METRIC_BY_EVENT.get(event_name, "UnknownViolation")
                publish_emf_metric(table_name, metric_name, 1)
                continue

            allowed_operations_count[table_name] += 1
        
        except Exception as e:
            print(f"Error processing Kinesis record: {str(e)}")
            raise e

    publish_allowed_operations_summary(allowed_operations_count)

    print(f"Batch processed successfully. Violations: {len(violations)}, Allowed Operations: {sum(allowed_operations_count.values())}")

    if violations:
        print(f"Dispatching critical SNS alert for {len(violations)} violations (Summary Only)...")
        send_alert(violations)

    return {
        'statusCode': 200,
        'violationsDetected': len(violations),
        'allowedOperations': sum(allowed_operations_count.values()),
        'violations': violations
    }


# ============================================================
# HELPERS
# ============================================================

def build_violation(record, table_name, table_type):
    dynamodb_data = record.get('dynamodb', {})
    return {
        'AlertType': 'TABLE_POLICY_VIOLATION',
        'Severity': 'CRITICAL',
        'Table': table_name,
        'TableType': table_type,
        'EventType': record.get('eventName'),
        'EventID': record.get('eventID'),
        'Keys': dynamodb_data.get('Keys', {}),
        'OldImage': dynamodb_data.get('OldImage', {}),
        'NewImage': dynamodb_data.get('NewImage', {}),
        'Timestamp': str(dynamodb_data.get('ApproximateCreationDateTime')),
        'SequenceNumber': dynamodb_data.get('SequenceNumber')
    }

def normalize_table_config(table_config):
    normalized = {}
    for table_name, table_type in table_config.items():
        normalized[str(table_name)] = str(table_type).strip().lower()
    return normalized

def is_violation(event_name, table_type):
    allowed_events = TABLE_POLICIES.get(table_type)
    if allowed_events is None:
        return False
    return event_name not in allowed_events

def publish_emf_metric(table_name, metric_name, value):
    try:
        emf_payload = {
            "_aws": {
                "Timestamp": int(datetime.utcnow().timestamp() * 1000),
                "CloudWatchMetrics": [
                    {
                        "Namespace": METRIC_NAMESPACE,
                        "Dimensions": [["TableName"]],
                        "Metrics": [{"Name": metric_name, "Unit": "Count"}]
                    }
                ]
            },
            metric_name: value,
            "TableName": table_name
        }
        print(json.dumps(emf_payload))
    except Exception as e:
        print(f"Error publishing EMF metric: {str(e)}")

def publish_allowed_operations_summary(allowed_ops_count):
    for table_name, count in allowed_ops_count.items():
        publish_emf_metric(table_name, "AllowedOperations", count)

def send_alert(violations):
    if not SNS_TOPIC_ARN or SNS_TOPIC_ARN == "":
        print("Warning: SNS_TOPIC_ARN not provided, skipping alert.")
        return

    # Crea un riepilogo raggruppando per Tabella e Tipo Evento
    summary = defaultdict(int)
    for v in violations:
        group_key = f"{v['Table']} ({v['EventType']})"
        summary[group_key] += 1

    unique_tables = sorted({v['Table'] for v in violations})
    unique_events = sorted({v['EventType'] for v in violations})
    summary_lines = []

    for key, count in summary.items():
        summary_lines.append(f"- {key}: {count} violation(s)")

    message = build_alert_body(
        alert_type="DynamoDB Table Policy Violation",
        severity="CRITICAL",
        detected_at=datetime.utcnow().isoformat(),
        resource=", ".join(unique_tables),
        operation=", ".join(unique_events),
        summary=f"Detected {len(violations)} policy violation(s) in the current batch.",
        details={
            "Violation Count": len(violations),
            "Tables": ", ".join(unique_tables),
            "Event Types": ", ".join(unique_events),
            "Batch Summary": "\n".join(summary_lines),
            "Action Required": "Check CloudWatch logs for 'VIOLATION DETAIL PAYLOAD' to inspect exact keys and modified data.",
        }
    )

    sns.publish(
        TopicArn=SNS_TOPIC_ARN,
        Subject=build_alert_subject("CRITICAL", "DynamoDB Table Policy Violation"),
        Message=message
    )