import json
import os
import re
from datetime import datetime, timezone

import boto3


ec2 = boto3.client("ec2")
sns = boto3.client("sns")

REPORT_PRODUCER = "pn-ec2-cost-saving"
REPORT_EVENT_NAME = "monthly-ec2-inventory"
REPORT_MARKDOWN_MAX_CHARS = 3000
STOPPED_AT_PATTERN = re.compile(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) GMT")
VISIBLE_INSTANCE_STATES = ("pending", "running", "stopping", "stopped")


def lambda_handler(event, context):
    action = (event or {}).get("action", "stop")

    if action == "stop":
        return stop_tagged_instances()
    if action == "report":
        return publish_monthly_report(context)

    raise ValueError(f"Unsupported action: {action}")


def stop_tagged_instances():
    tag_name = os.environ["StopEc2FunctionTagName"]
    tag_value = os.environ["StopEc2FunctionTagValue"]
    instance_ids = []

    for instance in describe_instances(
        filters=[
            {"Name": f"tag:{tag_name}", "Values": [tag_value]},
            {"Name": "instance-state-name", "Values": ["running"]},
        ]
    ):
        instance_ids.append(instance["InstanceId"])
        print(
            "EC2 instance that will be stopped: "
            f"{instance['InstanceId']} ({instance['InstanceType']}) - "
            f"State: {instance['State']['Name']}"
        )

    for start in range(0, len(instance_ids), 100):
        ec2.stop_instances(InstanceIds=instance_ids[start : start + 100])

    return {
        "action": "stop",
        "identifiedInstances": len(instance_ids),
        "instanceIds": instance_ids,
    }


def publish_monthly_report(context):
    now = datetime.now(timezone.utc)
    required_tag_name = os.environ.get("Ec2ReportRequiredTagName", "ToStop")
    required_tag_value = os.environ.get("Ec2ReportRequiredTagValue", "true")
    instances = [
        normalize_instance(instance, now, required_tag_name, required_tag_value)
        for instance in describe_instances(
            filters=[
                {"Name": "instance-state-name", "Values": list(VISIBLE_INSTANCE_STATES)}
            ]
        )
    ]
    instances.sort(key=lambda item: (item["is_off"], item["name"].lower(), item["id"]))

    running_count = sum(not instance["is_off"] for instance in instances)
    stopped_count = sum(instance["is_off"] for instance in instances)
    violation_count = sum(instance["tag_violation"] for instance in instances)
    account_id = os.environ["AwsAccountId"]
    account_type = os.environ["AccountType"]
    environment = os.environ["EnvironmentType"]

    base_event_id = getattr(context, "aws_request_id", None) or (
        f"ec2-report-{account_id}-{now.strftime('%Y%m%dT%H%M%SZ')}"
    )
    title = f"Report mensile EC2 - {environment.upper()} {account_type}"
    markdown_parts = split_markdown_report(
        build_markdown_report(
            instances=instances,
            account_id=account_id,
            account_type=account_type,
            environment=environment,
            region=os.environ.get("AWS_REGION", "unknown"),
            required_tag_name=required_tag_name,
            required_tag_value=required_tag_value,
        ),
        REPORT_MARKDOWN_MAX_CHARS,
    )
    message = {
        "schemaVersion": "1.0",
        "eventType": "report",
        "producer": REPORT_PRODUCER,
        "eventName": REPORT_EVENT_NAME,
        "occurredAt": now.isoformat(),
        "severity": "warning" if violation_count else "info",
        "environment": environment,
        "data": {
            "metrics": {
                "Account": account_id,
                "Ambito": account_type,
                "Totale EC2": len(instances),
                "Accese": running_count,
                "Spente": stopped_count,
                "Non conformi": violation_count,
            },
            "details": {},
        },
        "links": {},
    }

    message_ids = []
    for part_number, markdown_body in enumerate(markdown_parts, start=1):
        part_suffix = (
            f" ({part_number}/{len(markdown_parts)})" if len(markdown_parts) > 1 else ""
        )
        part_message = {
            **message,
            "eventId": f"{base_event_id}-part-{part_number}"
            if len(markdown_parts) > 1
            else base_event_id,
            "title": f"{title}{part_suffix}",
            "presentation": {
                "format": "slack-mrkdwn",
                "body": markdown_body,
            },
        }
        response = sns.publish(
            TopicArn=os.environ["WarningSNSTopicArn"],
            Subject=(
                f"[{environment}/{account_type}] Report mensile EC2{part_suffix}"
            )[:100],
            Message=json.dumps(part_message, separators=(",", ":")),
        )
        message_ids.append(response.get("MessageId"))

    print(
        json.dumps(
            {
                "action": "report",
                "accountId": account_id,
                "accountType": account_type,
                "environment": environment,
                "instances": len(instances),
                "tagViolations": violation_count,
                "reportParts": len(markdown_parts),
                "snsMessageIds": message_ids,
            },
            separators=(",", ":"),
        )
    )
    return {
        "action": "report",
        "instances": len(instances),
        "running": running_count,
        "stopped": stopped_count,
        "tagViolations": violation_count,
        "reportParts": len(markdown_parts),
        "snsMessageIds": message_ids,
    }


def describe_instances(filters):
    paginator = ec2.get_paginator("describe_instances")
    for page in paginator.paginate(Filters=filters):
        for reservation in page.get("Reservations", []):
            yield from reservation.get("Instances", [])


def normalize_instance(instance, now, required_tag_name, required_tag_value):
    tags = {
        tag.get("Key"): tag.get("Value", "")
        for tag in instance.get("Tags", [])
        if tag.get("Key")
    }
    instance_type = instance.get("InstanceType", "unknown")
    state = instance.get("State", {}).get("Name", "unknown")
    is_micro = instance_type.endswith(".micro")
    has_required_tag = tags.get(required_tag_name, "") == required_tag_value
    stopped_at = parse_stopped_at(instance.get("StateTransitionReason", ""))

    return {
        "id": instance.get("InstanceId", "unknown"),
        "name": tags.get("Name", "senza nome"),
        "type": instance_type,
        "state": state,
        "is_off": state in ("stopping", "stopped"),
        "is_micro": is_micro,
        "has_required_tag": has_required_tag,
        "tag_violation": not is_micro and not has_required_tag,
        "stopped_at": stopped_at,
        "stopped_for": elapsed_time(stopped_at, now) if stopped_at else None,
    }


def parse_stopped_at(state_transition_reason):
    match = STOPPED_AT_PATTERN.search(state_transition_reason or "")
    if not match:
        return None
    try:
        return datetime.strptime(match.group(1), "%Y-%m-%d %H:%M:%S").replace(
            tzinfo=timezone.utc
        )
    except ValueError:
        return None


def elapsed_time(started_at, now):
    seconds = max(0, int((now - started_at).total_seconds()))
    days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes = seconds // 60
    parts = []
    if days:
        parts.append(f"{days}g")
    if hours or days:
        parts.append(f"{hours}h")
    parts.append(f"{minutes}m")
    return " ".join(parts)


def build_markdown_report(
    *,
    instances,
    account_id,
    account_type,
    environment,
    region,
    required_tag_name,
    required_tag_value,
):
    running = [instance for instance in instances if not instance["is_off"]]
    stopped = [instance for instance in instances if instance["is_off"]]
    violations = [instance for instance in instances if instance["tag_violation"]]
    lines = [
        f"*Account:* `{escape_markdown(account_id)}` (`{escape_markdown(account_type)}`)",
        f"*Ambiente:* `{escape_markdown(environment.upper())}`",
        f"*Regione:* `{escape_markdown(region)}`",
        (
            "*Regola:* le istanze non `*.micro` devono avere "
            f"`{escape_markdown(required_tag_name)}={escape_markdown(required_tag_value)}`."
        ),
        "",
    ]

    if violations:
        lines.append(
            f":warning: *{len(violations)} istanze non conformi* alla regola del tag."
        )
    else:
        lines.append(":white_check_mark: *Tutte le istanze non-micro sono conformi.*")

    append_instance_group(lines, "Istanze accese", running, required_tag_name)
    append_instance_group(lines, "Istanze spente", stopped, required_tag_name)
    return "\n".join(lines)


def append_instance_group(lines, title, instances, required_tag_name):
    lines.extend(["", f"*{title} ({len(instances)})*"])
    if not instances:
        lines.append("• Nessuna")
        return

    for instance in instances:
        if instance["is_micro"]:
            tag_status = "tag non richiesto"
        elif instance["has_required_tag"]:
            tag_status = f"{required_tag_name}=true"
        else:
            tag_status = f":warning: {required_tag_name}=true mancante"

        state_detail = {
            "pending": "in avvio",
            "running": "accesa",
            "stopping": "in spegnimento",
        }.get(instance["state"], instance["state"])
        if instance["state"] == "stopped":
            if instance["stopped_at"]:
                state_detail = (
                    f"spenta da {instance['stopped_for']} "
                    f"(dal {instance['stopped_at'].strftime('%Y-%m-%d %H:%M UTC')})"
                )
            else:
                state_detail = "spenta, durata non disponibile"
        lines.append(
            "• "
            f"`{escape_markdown(instance['id'])}` — "
            f"{escape_markdown(instance['name'])} — "
            f"`{escape_markdown(instance['type'])}` — "
            f"{state_detail} — {tag_status}"
        )


def split_markdown_report(body, max_chars):
    chunks = []
    current_lines = []
    current_length = 0
    for line in body.splitlines():
        line_length = len(line) + (1 if current_lines else 0)
        if current_lines and current_length + line_length > max_chars:
            chunks.append("\n".join(current_lines))
            current_lines = []
            current_length = 0
            line_length = len(line)
        if len(line) > max_chars:
            for start in range(0, len(line), max_chars):
                if current_lines:
                    chunks.append("\n".join(current_lines))
                    current_lines = []
                    current_length = 0
                chunks.append(line[start : start + max_chars])
            continue
        current_lines.append(line)
        current_length += line_length
    if current_lines:
        chunks.append("\n".join(current_lines))
    return chunks or [body]


def escape_markdown(value):
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("`", "'")
        .replace("\n", " ")
    )
