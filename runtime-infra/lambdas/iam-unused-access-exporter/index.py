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
from urllib.parse import unquote

import boto3
from botocore.config import Config
from reporting import publish_warning_report

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
FINE_GRAINED_EXCLUSIONS_SSM_PARAMETER = os.environ.get("FINE_GRAINED_EXCLUSIONS_SSM_PARAMETER", "")
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
ssm = boto3.client("ssm", config=Config(retries={"max_attempts": 10, "mode": "adaptive"}))

CSV_HEADER = [
    "finding_id", "finding_type", "resource", "resource_type",
    "status", "created_at", "updated_at", "analyzed_at",
    "unused_action_count", "unused_actions", "suppressed_action_count",
    "suppressed_actions", "suppression_rule_ids", "microservice_tag", "details_json"
]

ACTION_PATTERN = re.compile(r"^[a-z0-9-]+:[A-Za-z0-9*]+$")

ARCHIVE_RULE_PREFIX = "auto-exclude-"

def _load_fine_grained_exclusion_rules():
    """Load and validate the action-level exclusion rules from Parameter Store."""
    if not FINE_GRAINED_EXCLUSIONS_SSM_PARAMETER:
        return []

    try:
        response = ssm.get_parameter(Name=FINE_GRAINED_EXCLUSIONS_SSM_PARAMETER)
        parameter = response.get("Parameter") or {}
        document = json.loads(parameter.get("Value", ""))
        if not isinstance(document, dict):
            raise ValueError("configuration root must be an object")
        if document.get("version") != 1:
            raise ValueError("configuration version must be 1")

        raw_rules = document.get("rules")
        if not isinstance(raw_rules, list):
            raise ValueError("rules must be an array")

        rules = []
        rule_ids = set()
        for index, rule in enumerate(raw_rules):
            if not isinstance(rule, dict):
                raise ValueError(f"rule at index {index} must be an object")

            rule_id = rule.get("id")
            if not isinstance(rule_id, str) or not rule_id.strip():
                raise ValueError(f"rule at index {index} must have a non-empty id")
            rule_id = rule_id.strip()
            if rule_id in rule_ids:
                raise ValueError(f"duplicate rule id: {rule_id}")
            rule_ids.add(rule_id)

            enabled = rule.get("enabled", True)
            if not isinstance(enabled, bool):
                raise ValueError(f"rule {rule_id} enabled must be a boolean")

            actions = rule.get("actions")
            if not isinstance(actions, list) or not actions:
                raise ValueError(f"rule {rule_id} actions must be a non-empty array")
            if any(not isinstance(action, str) or not ACTION_PATTERN.fullmatch(action.strip()) for action in actions):
                raise ValueError(f"rule {rule_id} contains an invalid action")

            trusted_services = rule.get("trustedServices")
            if not isinstance(trusted_services, list) or not trusted_services:
                raise ValueError(f"rule {rule_id} trustedServices must be a non-empty array")
            if any(not isinstance(service, str) or not service.strip() for service in trusted_services):
                raise ValueError(f"rule {rule_id} contains an invalid trusted service")

            if enabled:
                rules.append({
                    "id": rule_id,
                    "actions": {action.strip().casefold() for action in actions},
                    "trusted_services": {service.strip().casefold() for service in trusted_services},
                })

        log.info(json.dumps({
            "msg": "fine-grained exclusion rules loaded",
            "parameter": FINE_GRAINED_EXCLUSIONS_SSM_PARAMETER,
            "parameter_version": parameter.get("Version"),
            "rules": len(rules),
        }))
        return rules
    except Exception as exc:
        log.warning(json.dumps({
            "msg": "fine-grained exclusion rules unavailable; no actions will be suppressed",
            "parameter": FINE_GRAINED_EXCLUSIONS_SSM_PARAMETER,
            "error": str(exc),
        }))
        return []

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

def _get_role_trusted_services(role_name, cache):
    """Return service principals allowed by a role trust policy."""
    if role_name in cache:
        return cache[role_name]

    services = set()
    try:
        response = iam.get_role(RoleName=role_name)
        policy = (response.get("Role") or {}).get("AssumeRolePolicyDocument") or {}
        if isinstance(policy, str):
            policy = json.loads(unquote(policy))
        if not isinstance(policy, dict):
            raise ValueError("AssumeRolePolicyDocument is not an object")

        statements = policy.get("Statement", [])
        if isinstance(statements, dict):
            statements = [statements]
        if not isinstance(statements, list):
            raise ValueError("trust policy Statement is not an array")

        for statement in statements:
            if not isinstance(statement, dict) or str(statement.get("Effect", "")).casefold() != "allow":
                continue
            principal = statement.get("Principal")
            if not isinstance(principal, dict):
                continue
            service_principals = principal.get("Service", [])
            if isinstance(service_principals, str):
                service_principals = [service_principals]
            if isinstance(service_principals, list):
                services.update(
                    service.strip().casefold()
                    for service in service_principals
                    if isinstance(service, str) and service.strip()
                )
    except Exception as exc:
        log.warning(json.dumps({
            "msg": "get_role failed during fine-grained exclusion check",
            "role_name": role_name,
            "error": str(exc),
        }))

    cache[role_name] = services
    return services

def _filter_unused_actions(finding, unused_actions, rules, role_trust_cache):
    """Split unused actions into reportable and suppressed lists."""
    if not rules or not unused_actions:
        return unused_actions, [], []
    if finding.get("findingType") != "UnusedPermission":
        return unused_actions, [], []
    if finding.get("resourceType") != "AWS::IAM::Role":
        return unused_actions, [], []

    role_name = _parse_role_name(finding.get("resource"))
    if not role_name:
        return unused_actions, [], []

    trusted_services = _get_role_trusted_services(role_name, role_trust_cache)
    if not trusted_services:
        return unused_actions, [], []

    visible_actions = []
    suppressed_actions = []
    matched_rule_ids = set()
    for action in unused_actions:
        action_key = action.casefold()
        matching_rules = [
            rule for rule in rules
            if action_key in rule["actions"]
            and trusted_services.intersection(rule["trusted_services"])
        ]
        if matching_rules:
            suppressed_actions.append(action)
            matched_rule_ids.update(rule["id"] for rule in matching_rules)
        else:
            visible_actions.append(action)

    return visible_actions, suppressed_actions, sorted(matched_rule_ids)

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
    fine_grained_exclusion_rules = _load_fine_grained_exclusion_rules()

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(CSV_HEADER)

    count = 0
    skipped_by_tag = 0
    fully_suppressed_findings = 0
    partially_suppressed_findings = 0
    suppressed_action_count = 0
    finding_type_counts = {}
    role_tag_cache = {}
    role_trust_cache = {}
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
        unused_actions, suppressed_actions, suppression_rule_ids = _filter_unused_actions(
            f,
            unused_actions,
            fine_grained_exclusion_rules,
            role_trust_cache,
        )
        if suppressed_actions:
            suppressed_action_count += len(suppressed_actions)
            log.info(json.dumps({
                "msg": "unused actions suppressed by fine-grained rules",
                "finding_id": f.get("id"),
                "resource": resource,
                "actions": suppressed_actions,
                "rules": suppression_rule_ids,
            }))
            if not unused_actions:
                fully_suppressed_findings += 1
                continue
            partially_suppressed_findings += 1

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
            len(suppressed_actions),
            ";".join(suppressed_actions),
            ";".join(suppression_rule_ids),
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
        if count:
            markdown_body = (
                f":warning: Individuati *{count} finding* di accesso IAM inutilizzato "
                f"nell'account `{ACCOUNT_ROLE}`."
            )
        else:
            markdown_body = (
                f":white_check_mark: Nessun finding di accesso IAM inutilizzato "
                f"nell'account `{ACCOUNT_ROLE}`."
            )
        if skipped_by_tag:
            markdown_body += f"\n_Sono stati esclusi {skipped_by_tag} finding tramite tag._"
        if suppressed_action_count:
            markdown_body += (
                f"\n_Sono state ignorate {suppressed_action_count} azioni tramite regole granulari "
                f"({fully_suppressed_findings} finding esclusi, "
                f"{partially_suppressed_findings} parzialmente filtrati)._"
            )
        try:
            publish_warning_report(
                sns_client=sns,
                s3_client=s3,
                topic_arn=SNS_TOPIC_ARN,
                subject=f"[{account_label}] IAM unused access report",
                event_id=request_id,
                producer="pn-iam-unused-access-analyzer",
                event_name="unused-access-findings",
                occurred_at=now,
                environment=ENV_NAME,
                title="IAM unused access report",
                metrics={
                    "Finding": count,
                    "Ruolo account": ACCOUNT_ROLE,
                    "Esclusi per tag": skipped_by_tag,
                    "Azioni escluse da regole granulari": suppressed_action_count,
                    "Finding esclusi da regole granulari": fully_suppressed_findings,
                    "Finding parzialmente filtrati": partially_suppressed_findings,
                },
                details=finding_type_counts,
                links={
                    "dashboard": dashboard_url,
                    "report": f"s3://{BUCKET}/{key}",
                },
                attachment={
                    "bucket": BUCKET,
                    "key": key,
                    "filename": key.rsplit("/", 1)[-1],
                    "size": len(csv_bytes),
                },
                markdown_body=markdown_body,
            )
            log.info(json.dumps({"msg": "sns report sent", "topic": SNS_TOPIC_ARN, "findings": count}))
        except Exception as exc:
            log.exception(json.dumps({"msg": "sns publish failed", "error": str(exc)}))
            raise

    log.info(json.dumps({"msg": "export completed", "account_id": account_id,
                         "account_role": ACCOUNT_ROLE, "env": ENV_NAME,
                         "key": key, "rows": count, "skipped_by_tag": skipped_by_tag,
                         "suppressed_actions": suppressed_action_count,
                         "fully_suppressed_findings": fully_suppressed_findings,
                         "partially_suppressed_findings": partially_suppressed_findings}))
    return {
        "status": "ok",
        "rows": count,
        "skipped_by_tag": skipped_by_tag,
        "suppressed_actions": suppressed_action_count,
        "fully_suppressed_findings": fully_suppressed_findings,
        "partially_suppressed_findings": partially_suppressed_findings,
        "key": key,
    }
