"""
S3 Presigned URL Access Analyzer
Modified version: publishes ONLY CloudWatch metrics using EMF.
"""

import json
import os
from datetime import datetime
from collections import defaultdict
from typing import Dict, Any
import boto3

sns = boto3.client("sns")

# ENV
ENVIRONMENT = os.environ.get("ENVIRONMENT", "production")
SNS_TOPIC_ARN = os.environ.get("SNS_TOPIC_ARN")
ALERT_THRESHOLD = int(os.environ.get("ALERT_THRESHOLD", "5"))

EMF_NAMESPACE = "CustomSecurity/URLAccessAnalyzer"
EMF_DIMENSIONS = [["BucketName"]]
EMF_METRIC_UNIT = "Count"

# Local tracker
access_tracker = defaultdict(lambda: {"count": 0, "ips": set(), "first_seen": None})


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


def lambda_handler(event, context):
    print(f"Received event: {json.dumps(event)}")

    try:
        detail = event.get("detail", {})

        # Extract event fields
        event_name = detail.get("eventName")
        event_time = detail.get("eventTime")
        source_ip = detail.get("sourceIPAddress")
        user_agent = detail.get("userAgent")
        error_code = detail.get("errorCode")

        request_params = detail.get("requestParameters", {})
        bucket_name = request_params.get("bucketName")
        object_key = request_params.get("key")

        is_presigned = is_presigned_url_access(detail)

        log_entry = {
            "timestamp": event_time,
            "event_name": event_name,
            "bucket": bucket_name,
            "object_key": object_key,
            "source_ip": source_ip,
            "user_agent": user_agent,
            "is_presigned": is_presigned,
            "error_code": error_code,
        }

        ##if object_key is not start with PN_ favicon.ico skip processing (common noise in access logs)
        if object_key and not object_key.startswith("PN_"):
            #print("Skipping favicon.ico access")
            return {"statusCode": 200, "body": "Skipped non-PN_ object access"}
        
        print("Access log:", json.dumps(log_entry))

        # Process access
        if event_name == "GetObject":
            if error_code:
                handle_failed_access(log_entry)
            else:
                handle_successful_access(log_entry)

        # Publish EMF metrics
        publish_emf_metrics(log_entry)

        # Suspicious checks
        #if is_suspicious_access(log_entry):
        #    send_alert(
        #        log_entry,
        #        "Suspicious access pattern detected",
        #        alert_type="S3 Suspicious Access",
        #        severity="WARNING",
        #    )

        return {"statusCode": 200, "body": "EMF metrics emitted"}

    except Exception as e:
        print(f"ERROR: {str(e)}")
        raise


# --------------------------------------------------------------------------
# DETECTION LOGIC UNCHANGED
# --------------------------------------------------------------------------

def is_presigned_url_access(detail: Dict[str, Any]) -> bool:
    user_identity = detail.get("userIdentity", {})
    user_type = user_identity.get("type", "")
    request_params = detail.get("requestParameters", {})

    has_signature = any(k in str(request_params) for k in ["X-Amz-Signature", "Signature"])
    is_anon = user_type in ["AWSAccount", "Unknown", "AssumedRole"]

    return has_signature or (is_anon and not user_identity.get("sessionContext"))


def handle_successful_access(log_entry):
    object_key = log_entry.get("object_key")
    source_ip = log_entry.get("source_ip")

    key = f"{object_key}:{source_ip}"
    access_tracker[key]["count"] += 1
    access_tracker[key]["ips"].add(source_ip)

    if not access_tracker[key]["first_seen"]:
        access_tracker[key]["first_seen"] = log_entry["timestamp"]

    print(f"PRESIGNED_URL_ACCESS {object_key} from {source_ip}")


def handle_failed_access(log_entry):
    source_ip = log_entry.get("source_ip")
    error_code = log_entry.get("error_code")

    key = f"failed:{source_ip}"
    access_tracker[key]["count"] += 1

    print(f"ACCESS_DENIED from {source_ip} - {error_code}")

    if access_tracker[key]["count"] >= ALERT_THRESHOLD:
        send_alert(
            log_entry,
            f"Multiple failed access attempts from {source_ip}",
            alert_type="S3 Failed Access Attempts",
            severity="CRITICAL",
        )


def is_suspicious_access(log_entry):
    source_ip = log_entry.get("source_ip")
    user_agent = log_entry.get("user_agent", "").lower()

    suspicious_agents = ["curl", "wget", "python", "bot", "scanner"]
    if any(a in user_agent for a in suspicious_agents):
        print("Suspicious UA:", user_agent)
        return True

    return False

def publish_emf_metrics(log_entry):
    """
    Emit metrics via EMF to stdout (CloudWatch will parse them).
    """

    timestamp_ms = int(datetime.utcnow().timestamp() * 1000)

    metrics = []

    # Total S3 access metric
    metrics.append(("S3URLAccess", 1))

    # Presigned URL metric
    if log_entry.get("is_presigned"):
        metrics.append(("PresignedURLAccess", 1))

    # Failed access metric
    if log_entry.get("error_code"):
        metrics.append(("FailedS3Access", 1))

    for metric_name, value in metrics:
        emf = {
            "_aws": {
                "Timestamp": timestamp_ms,
                "CloudWatchMetrics": [
                    {
                        "Namespace": EMF_NAMESPACE,
                        "Dimensions": EMF_DIMENSIONS,
                        "Metrics": [
                            {"Name": metric_name, "Unit": EMF_METRIC_UNIT}
                        ],
                    }
                ],
            },
            "BucketName": log_entry.get("bucket"),
            metric_name: value,
        }

        print(json.dumps(emf))


# --------------------------------------------------------------------------
# SNS ALERT
# --------------------------------------------------------------------------

def send_alert(log_entry, message, alert_type, severity):
    if not SNS_TOPIC_ARN:
        return

    resource = log_entry.get("bucket") or "Unknown"
    if log_entry.get("object_key"):
        resource = f"s3://{log_entry.get('bucket')}/{log_entry.get('object_key')}"

    body = build_alert_body(
        alert_type=alert_type,
        severity=severity,
        detected_at=log_entry.get("timestamp"),
        resource=resource,
        operation=log_entry.get("event_name"),
        summary=message,
        details={
            "Bucket": log_entry.get("bucket"),
            "Object Key": log_entry.get("object_key"),
            "Source IP": log_entry.get("source_ip"),
            "User Agent": log_entry.get("user_agent"),
            "Error Code": log_entry.get("error_code"),
            "Presigned URL": log_entry.get("is_presigned"),
        },
    )

    sns.publish(
        TopicArn=SNS_TOPIC_ARN,
        Subject=build_alert_subject(severity, alert_type),
        Message=body,
    )

    print("Alert sent")