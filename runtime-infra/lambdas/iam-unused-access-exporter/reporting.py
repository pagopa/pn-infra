"""Warning notification dispatcher integration for application reports."""

import json


def generate_presigned_report_url(
    *, s3_client, bucket, key, url_expiration_seconds=3600
):
    """Generate a temporary browser URL for a private report stored in S3."""
    return s3_client.generate_presigned_url(
        "get_object",
        Params={
            "Bucket": bucket,
            "Key": key,
        },
        ExpiresIn=url_expiration_seconds,
    )


def publish_warning_report(
    *,
    sns_client,
    s3_client,
    topic_arn,
    subject,
    event_id,
    producer,
    event_name,
    occurred_at,
    environment,
    title,
    metrics,
    details,
    links,
    attachment,
    markdown_body=None,
    url_expiration_seconds=3600,
):
    if not title:
        raise ValueError("Report title is required")
    if not isinstance(metrics, dict) or not metrics:
        raise ValueError("Report metrics must be a non-empty dictionary")

    download_url = generate_presigned_report_url(
        s3_client=s3_client,
        bucket=attachment["bucket"],
        key=attachment["key"],
        url_expiration_seconds=url_expiration_seconds,
    )
    message = {
        "schemaVersion": "1.0",
        "eventId": event_id,
        "eventType": "report",
        "producer": producer,
        "eventName": event_name,
        "occurredAt": occurred_at.isoformat(),
        "severity": "info",
        "environment": environment,
        "title": title,
        "data": {
            "metrics": metrics,
            "details": details,
        },
        "links": links,
        "attachment": {
            "filename": attachment["filename"],
            "contentType": "text/csv",
            "size": attachment["size"],
            "downloadUrl": download_url,
        },
    }
    if markdown_body is not None:
        if not isinstance(markdown_body, str) or not markdown_body.strip():
            raise ValueError("Report markdown body must be a non-empty string")
        message["presentation"] = {
            "format": "slack-mrkdwn",
            "body": markdown_body,
        }
    sns_client.publish(
        TopicArn=topic_arn,
        Subject=subject[:100],
        Message=json.dumps(message, separators=(",", ":")),
    )
