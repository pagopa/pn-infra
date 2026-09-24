"""AWS IAM Access Analyzer operations used by the exporter."""

import json
import re


ACTION_PATTERN = re.compile(r"^[a-z0-9-]+:[A-Za-z0-9*]+$")
ARCHIVE_RULE_PREFIX = "auto-exclude-"


def sync_archive_rules(*, analyzer_client, analyzer_arn, patterns, logger):
    """Create one archive rule per pattern, remove obsolete ones, then apply all."""
    analyzer_name = analyzer_arn.rsplit("/", 1)[-1]

    try:
        existing = analyzer_client.list_archive_rules(analyzerName=analyzer_name)
        existing_rules = {rule["ruleName"]: rule for rule in existing.get("archiveRules", [])}
    except Exception as exc:
        logger.warning(json.dumps({"msg": "list_archive_rules failed", "error": str(exc)}))
        return

    desired_rules = {}
    for pattern in patterns:
        rule_name = f"{ARCHIVE_RULE_PREFIX}{pattern}"
        desired_rules[rule_name] = pattern

    for rule_name, pattern in desired_rules.items():
        if rule_name not in existing_rules:
            try:
                analyzer_client.create_archive_rule(
                    analyzerName=analyzer_name,
                    ruleName=rule_name,
                    filter={"resource": {"contains": [pattern]}},
                )
                logger.info(json.dumps({
                    "msg": "created archive rule",
                    "rule": rule_name,
                    "pattern": pattern,
                }))
            except Exception as exc:
                logger.warning(json.dumps({
                    "msg": "create_archive_rule failed",
                    "rule": rule_name,
                    "error": str(exc),
                }))

    for rule_name in existing_rules:
        if rule_name.startswith(ARCHIVE_RULE_PREFIX) and rule_name not in desired_rules:
            try:
                analyzer_client.delete_archive_rule(
                    analyzerName=analyzer_name,
                    ruleName=rule_name,
                )
                logger.info(json.dumps({
                    "msg": "deleted obsolete archive rule",
                    "rule": rule_name,
                }))
            except Exception as exc:
                logger.warning(json.dumps({
                    "msg": "delete_archive_rule failed",
                    "rule": rule_name,
                    "error": str(exc),
                }))

    try:
        all_rules = analyzer_client.list_archive_rules(analyzerName=analyzer_name)
        for rule in all_rules.get("archiveRules", []):
            rule_name = rule["ruleName"]
            logger.info(json.dumps({"msg": "applying archive rule", "rule": rule_name}))
            analyzer_client.apply_archive_rule(
                analyzerArn=analyzer_arn,
                ruleName=rule_name,
            )
    except Exception as exc:
        logger.warning(json.dumps({"msg": "apply_archive_rules failed", "error": str(exc)}))


def iter_findings(*, analyzer_client, analyzer_arn):
    """Yield all active findings, transparently following pagination tokens."""
    token = None
    while True:
        kwargs = {
            "analyzerArn": analyzer_arn,
            "maxResults": 100,
            "filter": {"status": {"eq": ["ACTIVE"]}},
        }
        if token:
            kwargs["nextToken"] = token
        response = analyzer_client.list_findings_v2(**kwargs)
        yield from response.get("findings", [])
        token = response.get("nextToken")
        if not token:
            return


def get_finding_details(*, analyzer_client, analyzer_arn, finding_id, logger):
    """Return the finding details, failing open when Access Analyzer is unavailable."""
    try:
        response = analyzer_client.get_finding_v2(
            analyzerArn=analyzer_arn,
            id=finding_id,
        )
        details = response.get("findingDetails")
        return details if isinstance(details, list) else []
    except Exception as exc:
        logger.warning(json.dumps({
            "msg": "get_finding_v2 failed",
            "finding_id": finding_id,
            "error": str(exc),
        }))
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


def extract_unused_actions(details):
    """Extract and deduplicate unused IAM actions from finding details."""
    actions = set()
    if isinstance(details, list):
        for item in details:
            if not isinstance(item, dict):
                continue
            permission_details = item.get("unusedPermissionDetails")
            if not isinstance(permission_details, dict):
                continue
            for action_item in permission_details.get("actions", []):
                if isinstance(action_item, dict):
                    action_name = action_item.get("action")
                    if isinstance(action_name, str) and action_name:
                        actions.add(action_name)
    _collect_actions(details, actions)
    return sorted(actions)
