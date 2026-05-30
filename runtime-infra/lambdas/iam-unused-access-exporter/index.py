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
RESOLVE_ROLE_TAGS = os.environ.get("RESOLVE_ROLE_TAGS", "true").lower() == "true"
SNS_TOPIC_ARN = os.environ.get("SNS_TOPIC_ARN", "")
EXCLUDE_RESOURCE_PATTERNS = [
    p.strip() for p in os.environ.get("EXCLUDE_RESOURCE_PATTERNS", "").split(",") if p.strip()
]

aa  = boto3.client("accessanalyzer", config=Config(retries={"max_attempts": 10, "mode": "adaptive"}))
s3  = boto3.client("s3")
sts = boto3.client("sts")
iam = boto3.client("iam")
sns = boto3.client("sns")

CSV_HEADER = [
    "finding_id", "finding_type", "resource", "resource_type",
    "status", "created_at", "updated_at", "analyzed_at",
    "unused_action_count", "unused_actions", "microservice_tag", "details_json"
]

ACTION_PATTERN = re.compile(r"^[a-z0-9-]+:[A-Za-z0-9*]+$")

def _apply_archive_rules():
    """Apply all archive rules to existing findings so they get archived before export."""
    try:
        rules = aa.list_archive_rules(analyzerName=ANALYZER_ARN.rsplit("/", 1)[-1])
        for rule in rules.get("archiveRules", []):
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

def lambda_handler(event, context):
    account_id = sts.get_caller_identity()["Account"]
    now = datetime.now(timezone.utc)
    key = f"{ENV_NAME}/{ACCOUNT_ROLE}/{account_id}/{now:%Y-%m-%d}/findings-{now:%H%M%S}.csv"

    _apply_archive_rules()

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(CSV_HEADER)

    count = 0
    skipped = 0
    finding_type_counts = {}
    role_tag_cache = {}
    for f in _iter_findings():
        resource = f.get("resource", "")
        if EXCLUDE_RESOURCE_PATTERNS and any(p in resource for p in EXCLUDE_RESOURCE_PATTERNS):
            skipped += 1
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

    s3.put_object(
        Bucket=BUCKET,
        Key=key,
        Body=buf.getvalue().encode("utf-8"),
        ContentType="text/csv",
    )

    if count > 0 and SNS_TOPIC_ARN:
        dashboard_name = f"pn-iam-unused-access-{ENV_NAME}"
        region = os.environ.get("AWS_REGION", "eu-south-1")
        dashboard_url = (
            f"https://{region}.console.aws.amazon.com/cloudwatch/home"
            f"?region={region}#dashboards/dashboard/{dashboard_name}"
        )
        account_label = f"{ACCOUNT_ROLE}-{ENV_NAME}"
        breakdown_lines = "\n".join(
            f"  - {ftype}: {fcount}" for ftype, fcount in sorted(finding_type_counts.items())
        )
        subject = f"[{account_label}] IAM unused access: {count} finding rilevati"
        message = (
            f"Account: {account_id} ({account_label})\n"
            f"Ambiente: {ENV_NAME}\n"
            f"Ruolo account: {ACCOUNT_ROLE}\n\n"
            f"Sono stati rilevati {count} finding IAM unused access.\n\n"
            f"Dettaglio per tipologia:\n{breakdown_lines}\n\n"
            f"Consultare la dashboard CloudWatch per i dettagli:\n{dashboard_url}\n\n"
            f"Report CSV: s3://{BUCKET}/{key}"
        )
        try:
            sns.publish(
                TopicArn=SNS_TOPIC_ARN,
                Subject=subject[:100],
                Message=message,
            )
            log.info(json.dumps({"msg": "sns alert sent", "topic": SNS_TOPIC_ARN, "findings": count}))
        except Exception as exc:
            log.warning(json.dumps({"msg": "sns publish failed", "error": str(exc)}))

    log.info(json.dumps({"msg": "export completed", "account_id": account_id,
                         "account_role": ACCOUNT_ROLE, "env": ENV_NAME,
                         "key": key, "rows": count, "skipped": skipped}))
    return {"status": "ok", "rows": count, "skipped": skipped, "key": key}
