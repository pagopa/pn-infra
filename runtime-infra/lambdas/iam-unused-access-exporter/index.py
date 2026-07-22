"""
IAM Access Analyzer - unused access exporter.

For each page of ListFindingsV2 on the local ACCOUNT_UNUSED_ACCESS Analyzer,
appends rows to an in-memory CSV, then uploads to REPORTS_BUCKET at
<env>/<core|confinfo>/<account_id>/<yyyy-mm-dd>/findings-HHMMSS.csv
using S3 default server-side encryption (SSE-S3).
"""
import csv
import io
import json
import logging
import os
import re
from datetime import datetime, timezone

import boto3
from botocore.config import Config

log = logging.getLogger()
log.setLevel(logging.INFO)

ANALYZER_ARN  = os.environ["ANALYZER_ARN"]
BUCKET        = os.environ["REPORTS_BUCKET"]
ENV_NAME      = os.environ["ENV_NAME"]
ACCOUNT_ROLE  = os.environ["ACCOUNT_ROLE"]  # 'core' | 'confinfo'
AWS_REGION    = os.environ.get("AWS_REGION", "eu-south-1")
RESOLVE_ROLE_TAGS = os.environ.get("RESOLVE_ROLE_TAGS", "true").lower() == "true"
SNS_TOPIC_ARN = os.environ.get("SNS_TOPIC_ARN", "")
REPORT_NOTIFICATIONS_ENABLED = os.environ.get("REPORT_NOTIFICATIONS_ENABLED", "false").lower() == "true"
EXCLUDE_TAG_KEY = os.environ.get("EXCLUDE_TAG_KEY", "")
ARCHIVE_RULE_PATTERNS = [p.strip() for p in os.environ.get("ARCHIVE_RULE_PATTERNS", "").split(",") if p.strip()]

aa  = boto3.client("accessanalyzer", config=Config(retries={"max_attempts": 10, "mode": "adaptive"}))
s3  = boto3.client(
    "s3",
    region_name=AWS_REGION,
    config=Config(signature_version="s3v4", s3={"addressing_style": "virtual"}),
)
sts = boto3.client("sts")
iam = boto3.client("iam")
sns = boto3.client("sns")

CSV_HEADER = [
    "finding_id", "finding_type", "resource", "resource_type",
    "status", "created_at", "updated_at", "analyzed_at",
    "unused_action_count", "unused_actions", "microservice_tag", "details_json"
]

ACTION_PATTERN = re.compile(r"^[a-z0-9-]+:[A-Za-z0-9*]+$")

ARCHIVE_RULE_PREFIX = "auto-exclude-"

def _sync_archive_rules():
    """Create one archive rule per pattern, remove obsolete ones, then apply all."""
    analyzer_name = ANALYZER_ARN.rsplit("/", 1)[-1]

    # List existing auto-managed rules
    try:
        existing = aa.list_archive_rules(analyzerName=analyzer_name)
        existing_rules = {r["ruleName"]: r for r in existing.get("archiveRules", [])}
    except Exception as exc:
        log.warning(json.dumps({"msg": "list_archive_rules failed", "error": str(exc)}))
        return

    # Desired rules: one per pattern
    desired_rules = {}
    for pattern in ARCHIVE_RULE_PATTERNS:
        rule_name = f"{ARCHIVE_RULE_PREFIX}{pattern}"
        desired_rules[rule_name] = pattern

    # Create missing rules
    for rule_name, pattern in desired_rules.items():
        if rule_name not in existing_rules:
            try:
                aa.create_archive_rule(
                    analyzerName=analyzer_name,
                    ruleName=rule_name,
                    filter={"resource": {"contains": [pattern]}},
                )
                log.info(json.dumps({"msg": "created archive rule", "rule": rule_name, "pattern": pattern}))
            except Exception as exc:
                log.warning(json.dumps({"msg": "create_archive_rule failed", "rule": rule_name, "error": str(exc)}))

    # Delete obsolete auto-managed rules
    for rule_name in existing_rules:
        if rule_name.startswith(ARCHIVE_RULE_PREFIX) and rule_name not in desired_rules:
            try:
                aa.delete_archive_rule(analyzerName=analyzer_name, ruleName=rule_name)
                log.info(json.dumps({"msg": "deleted obsolete archive rule", "rule": rule_name}))
            except Exception as exc:
                log.warning(json.dumps({"msg": "delete_archive_rule failed", "rule": rule_name, "error": str(exc)}))

    # Apply all rules (including manually created ones)
    try:
        all_rules = aa.list_archive_rules(analyzerName=analyzer_name)
        for rule in all_rules.get("archiveRules", []):
            rule_name = rule["ruleName"]
            log.info(json.dumps({"msg": "applying archive rule", "rule": rule_name}))
            aa.apply_archive_rule(analyzerArn=ANALYZER_ARN, ruleName=rule_name)
    except Exception as exc:
        log.warning(json.dumps({"msg": "apply_archive_rules failed", "error": str(exc)}))

def _iter_findings():
    token = None
    while True:
        kwargs = {
            "analyzerArn": ANALYZER_ARN,
            "maxResults": 100,
            "filter": {"status": {"eq": ["ACTIVE"]}},
        }
        if token:
            kwargs["nextToken"] = token
        resp = aa.list_findings_v2(**kwargs)
        for finding in resp.get("findings", []):
            yield finding
        token = resp.get("nextToken")
        if not token:
            return

def _get_finding_details(finding_id):
    try:
        resp = aa.get_finding_v2(analyzerArn=ANALYZER_ARN, id=finding_id)
        details = resp.get("findingDetails")
        return details if isinstance(details, list) else []
    except Exception as exc:
        log.warning(json.dumps({"msg": "get_finding_v2 failed", "finding_id": finding_id, "error": str(exc)}))
        return []

def _collect_actions(node, output):
    if isinstance(node, dict):
        for value in node.values():
            _collect_actions(value, output)
        return
    if isinstance(node, list):
        for item in node:
            _collect_actions(item, output)
        return
    if isinstance(node, str) and ACTION_PATTERN.match(node):
        output.add(node)

def _extract_unused_actions(details):
    actions = set()
    if isinstance(details, list):
        for item in details:
            if not isinstance(item, dict):
                continue
            upd = item.get("unusedPermissionDetails")
            if not isinstance(upd, dict):
                continue
            for action_item in upd.get("actions", []):
                if isinstance(action_item, dict):
                    action_name = action_item.get("action")
                    if isinstance(action_name, str) and action_name:
                        actions.add(action_name)
    _collect_actions(details, actions)
    return sorted(actions)

def _parse_role_name(resource):
    value = str(resource or "")
    marker = ":role/"
    if marker in value:
        role_part = value.split(marker, 1)[1]
        return role_part.strip("/").split("/")[-1]
    return ""

def _resolve_microservice_tag(resource, cache):
    if not RESOLVE_ROLE_TAGS:
        return "no-tag"

    role_name = _parse_role_name(resource)
    if not role_name:
        return "no-tag"

    if role_name in cache:
        return cache[role_name]

    microservice = ""
    try:
        response = iam.list_role_tags(RoleName=role_name)
        for tag in response.get("Tags", []):
            if str(tag.get("Key", "")).lower() == "microservice":
                microservice = str(tag.get("Value") or "").strip()
                break
    except Exception as exc:
        log.warning(json.dumps({"msg": "list_role_tags failed", "role_name": role_name, "error": str(exc)}))

    if not microservice:
        microservice = "no-tag"

    cache[role_name] = microservice
    return microservice

def _has_exclude_tag(role_name, cache):
    """Check if a role has the exclude tag. Uses a shared cache with prefix to avoid collisions."""
    cache_key = f"__exclude__{role_name}"
    if cache_key in cache:
        return cache[cache_key]

    result = False
    try:
        response = iam.list_role_tags(RoleName=role_name)
        for tag in response.get("Tags", []):
            if str(tag.get("Key", "")) == EXCLUDE_TAG_KEY and str(tag.get("Value", "")).lower() == "true":
                result = True
                break
    except Exception as exc:
        log.warning(json.dumps({"msg": "list_role_tags failed (exclude check)", "role_name": role_name, "error": str(exc)}))

    cache[cache_key] = result
    return result

def lambda_handler(event, context):
    account_id = sts.get_caller_identity()["Account"]
    now = datetime.now(timezone.utc)
    request_id = (context.aws_request_id if context else "local")
    key = f"{ENV_NAME}/{ACCOUNT_ROLE}/{account_id}/{now:%Y-%m-%d}/{account_id}-findings-{now:%H%M%S}-{request_id}.csv"

    _sync_archive_rules()

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(CSV_HEADER)

    count = 0
    skipped_by_tag = 0
    finding_type_counts = {}
    role_tag_cache = {}
    for f in _iter_findings():
        resource = f.get("resource", "")
        # Check if resource has the exclude tag — if so, skip from CSV
        if EXCLUDE_TAG_KEY:
            role_name = _parse_role_name(resource)
            if role_name and _has_exclude_tag(role_name, role_tag_cache):
                skipped_by_tag += 1
                continue
        details = _get_finding_details(f.get("id"))
        unused_actions = _extract_unused_actions(details)
        microservice_tag = _resolve_microservice_tag(f.get("resource"), role_tag_cache)
        unused_action_count = ""
        if unused_actions:
            unused_action_count = len(unused_actions)

        finding_type = f.get("findingType", "Unknown")
        finding_type_counts[finding_type] = finding_type_counts.get(finding_type, 0) + 1

        enriched = dict(f)
        if details:
            enriched["findingDetails"] = details

        writer.writerow([
            f.get("id"),
            f.get("findingType"),
            f.get("resource"),
            f.get("resourceType"),
            f.get("status"),
            f.get("createdAt").isoformat() if f.get("createdAt") else "",
            f.get("updatedAt").isoformat() if f.get("updatedAt") else "",
            f.get("analyzedAt").isoformat() if f.get("analyzedAt") else "",
            unused_action_count,
            ";".join(unused_actions),
            microservice_tag,
            json.dumps(enriched, default=str, separators=(",", ":")),
        ])
        count += 1

    csv_bytes = buf.getvalue().encode("utf-8")
    s3.put_object(
        Bucket=BUCKET,
        Key=key,
        Body=csv_bytes,
        ContentType="text/csv",
    )

    if REPORT_NOTIFICATIONS_ENABLED and SNS_TOPIC_ARN:
        dashboard_name = f"pn-iam-unused-access-{ENV_NAME}"
        dashboard_url = (
            f"https://{AWS_REGION}.console.aws.amazon.com/cloudwatch/home"
            f"?region={AWS_REGION}#dashboards/dashboard/{dashboard_name}"
        )
        account_label = f"{ACCOUNT_ROLE}-{ENV_NAME}"
        report_download_url = s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": BUCKET, "Key": key},
            ExpiresIn=3600,
        )
        message = {
            "schemaVersion": "1.0",
            "eventId": request_id,
            "eventType": "report",
            "producer": "pn-iam-unused-access-analyzer",
            "eventName": "unused-access-findings",
            "occurredAt": now.isoformat(),
            "severity": "info",
            "environment": ENV_NAME,
            "data": {
                "accountId": account_id,
                "accountRole": ACCOUNT_ROLE,
                "findingCount": count,
                "findingTypeCounts": finding_type_counts,
                "skippedByTag": skipped_by_tag,
            },
            "links": {
                "dashboard": dashboard_url,
                "report": f"s3://{BUCKET}/{key}",
            },
            "attachment": {
                "filename": key.rsplit("/", 1)[-1],
                "contentType": "text/csv",
                "size": len(csv_bytes),
                "downloadUrl": report_download_url,
            },
        }
        try:
            sns.publish(
                TopicArn=SNS_TOPIC_ARN,
                Subject=f"[{account_label}] IAM unused access report"[:100],
                Message=json.dumps(message, separators=(",", ":")),
            )
            log.info(json.dumps({"msg": "sns report sent", "topic": SNS_TOPIC_ARN, "findings": count}))
        except Exception as exc:
            log.exception(json.dumps({"msg": "sns publish failed", "error": str(exc)}))
            raise

    log.info(json.dumps({"msg": "export completed", "account_id": account_id,
                         "account_role": ACCOUNT_ROLE, "env": ENV_NAME,
                         "key": key, "rows": count, "skipped_by_tag": skipped_by_tag}))
    return {"status": "ok", "rows": count, "skipped_by_tag": skipped_by_tag, "key": key}
