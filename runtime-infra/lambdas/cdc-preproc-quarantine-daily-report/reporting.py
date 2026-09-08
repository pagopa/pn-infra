"""Warning notification dispatcher integration for application reports."""

import json


def publish_warning_report(
    *,
    sns_client,
    topic_arn,
    event_id,
    producer,
    event_name,
    occurred_at,
    environment,
    title,
    metrics,
    details,
    links,
):
    if not title:
        raise ValueError("Report title is required")

    if not isinstance(metrics, dict) or not metrics:
        raise ValueError(
            "Report metrics must be a non-empty dictionary"
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
    }

    sns_client.publish(
        TopicArn=topic_arn,
        Subject=f"[{environment}] {title}"[:100],
        Message=json.dumps(
            message,
            separators=(",", ":"),
        ),
    )
