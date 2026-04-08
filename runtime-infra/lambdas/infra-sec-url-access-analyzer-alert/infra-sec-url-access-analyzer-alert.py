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

# Local tracker
access_tracker = defaultdict(lambda: {"count": 0, "ips": set(), "first_seen": None})


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
        if is_suspicious_access(log_entry):
            send_alert(log_entry, "Suspicious access pattern detected")

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
        send_alert(log_entry, f"Multiple failed access attempts from {source_ip}")


def is_suspicious_access(log_entry):
    source_ip = log_entry.get("source_ip")
    user_agent = log_entry.get("user_agent", "").lower()

    suspicious_agents = ["curl", "wget", "python", "bot", "scanner"]
    if any(a in user_agent for a in suspicious_agents):
        print("Suspicious UA:", user_agent)
        return True

    return False


# --------------------------------------------------------------------------
# EMF METRICS (REPLACES ALL PutMetricData)
# --------------------------------------------------------------------------

def publish_emf_metrics(log_entry):
    """
    Emit metrics via EMF to stdout (CloudWatch will parse them).
    """

    timestamp_ms = int(datetime.utcnow().timestamp() * 1000)

    base_dimensions = ["BucketName"]

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
                        "Namespace": "S3URLMonitoring",
                        "Dimensions": [base_dimensions],
                        "Metrics": [
                            {"Name": metric_name, "Unit": "Count"}
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

def send_alert(log_entry, message):
    if not SNS_TOPIC_ARN:
        return

    body = f"""
S3 Presigned URL Access Alert

Message: {message}
Object: {log_entry.get("object_key")}
IP: {log_entry.get("source_ip")}
Error: {log_entry.get("error_code")}

Environment: {ENVIRONMENT}
"""

    sns.publish(
        TopicArn=SNS_TOPIC_ARN,
        Subject=f"[{ENVIRONMENT}] S3 URL Access Alert",
        Message=body,
    )

    print("Alert sent")