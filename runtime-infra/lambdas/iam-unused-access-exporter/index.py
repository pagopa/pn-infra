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
from datetime import datetime, timezone

import boto3
from access_analyzer import (
    extract_unused_actions as _extract_unused_actions,
    get_finding_details as _get_finding_details,
    iter_findings as _iter_findings,
    sync_archive_rules as _sync_archive_rules,
)
from botocore.config import Config
from fine_grained_exclusions import (
    filter_unused_actions as _filter_unused_actions,
    load_rules as _load_fine_grained_exclusion_rules,
)
from html_reporting import export_html_report
from iam_roles import (
    has_exclude_tag as _has_exclude_tag,
    parse_role_name as _parse_role_name,
    resolve_microservice_tag as _resolve_microservice_tag,
)
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
HTML_REPORT_ENABLED = os.environ.get("HTML_REPORT_ENABLED", "false").lower() == "true"
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


def lambda_handler(event, context):
    account_id = sts.get_caller_identity()["Account"]
    now = datetime.now(timezone.utc)
    request_id = (context.aws_request_id if context else "local")
    key = f"{ENV_NAME}/{ACCOUNT_ROLE}/{account_id}/{now:%Y-%m-%d}/{account_id}-findings-{now:%H%M%S}-{request_id}.csv"

    _sync_archive_rules(
        analyzer_client=aa,
        analyzer_arn=ANALYZER_ARN,
        patterns=ARCHIVE_RULE_PATTERNS,
        logger=log,
    )
    fine_grained_exclusion_rules = _load_fine_grained_exclusion_rules(
        ssm_client=ssm,
        parameter_name=FINE_GRAINED_EXCLUSIONS_SSM_PARAMETER,
        logger=log,
    )

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
    html_report_rows = []
    for f in _iter_findings(analyzer_client=aa, analyzer_arn=ANALYZER_ARN):
        resource = f.get("resource", "")
        # Check if resource has the exclude tag — if so, skip from CSV
        if EXCLUDE_TAG_KEY:
            role_name = _parse_role_name(resource)
            if role_name and _has_exclude_tag(
                iam_client=iam,
                role_name=role_name,
                cache=role_tag_cache,
                tag_key=EXCLUDE_TAG_KEY,
                logger=log,
            ):
                skipped_by_tag += 1
                continue
        details = _get_finding_details(
            analyzer_client=aa,
            analyzer_arn=ANALYZER_ARN,
            finding_id=f.get("id"),
            logger=log,
        )
        unused_actions = _extract_unused_actions(details)
        microservice_tag = _resolve_microservice_tag(
            iam_client=iam,
            resource=f.get("resource"),
            cache=role_tag_cache,
            enabled=RESOLVE_ROLE_TAGS,
            logger=log,
        )
        unused_actions, suppressed_actions, suppression_rule_ids = _filter_unused_actions(
            finding=f,
            unused_actions=unused_actions,
            rules=fine_grained_exclusion_rules,
            microservice=microservice_tag,
            role_trust_cache=role_trust_cache,
            iam_client=iam,
            logger=log,
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

        unused_action_count = ""
        if unused_actions:
            unused_action_count = len(unused_actions)

        finding_type = f.get("findingType", "Unknown")
        finding_type_counts[finding_type] = finding_type_counts.get(finding_type, 0) + 1

        enriched = dict(f)
        if details:
            enriched["findingDetails"] = details

        if HTML_REPORT_ENABLED:
            html_report_rows.append({
                "finding_id": f.get("id"),
                "finding_type": f.get("findingType"),
                "resource": f.get("resource"),
                "resource_type": f.get("resourceType"),
                "status": f.get("status"),
                "unused_actions": unused_actions,
                "suppressed_actions": suppressed_actions,
                "suppression_rule_ids": suppression_rule_ids,
                "microservice_tag": microservice_tag,
            })

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

    if HTML_REPORT_ENABLED:
        html_metrics = {
            "Finding": count,
            "Esclusi per tag": skipped_by_tag,
            "Azioni ignorate": suppressed_action_count,
            "Finding esclusi da regole": fully_suppressed_findings,
            "Finding parzialmente filtrati": partially_suppressed_findings,
        }
        try:
            html_key, html_size = export_html_report(
                s3_client=s3,
                bucket=BUCKET,
                csv_key=key,
                generated_at=now,
                account_id=account_id,
                environment=ENV_NAME,
                account_role=ACCOUNT_ROLE,
                report_rows=html_report_rows,
                metrics=html_metrics,
            )
            log.info(json.dumps({"msg": "html report exported", "key": html_key, "size": html_size}))
        except Exception as exc:
            log.exception(json.dumps({"msg": "html report export failed", "error": str(exc)}))

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
