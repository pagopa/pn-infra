"""Validation and matching for fine-grained unused-action exclusions."""

import re
from fnmatch import fnmatchcase

from iam_roles import get_role_trusted_services, parse_role_name


ACTION_PATTERN = re.compile(r"^[a-z0-9-]+:[A-Za-z0-9*]+$")


def parse_rules(raw_rules):
    """Validate and normalize enabled action-level exclusion rules."""
    if raw_rules is None:
        return []
    if not isinstance(raw_rules, list):
        raise ValueError("fineGrainedExclusions must be an array")

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
        if any(
            not isinstance(action, str) or not ACTION_PATTERN.fullmatch(action.strip())
            for action in actions
        ):
            raise ValueError(f"rule {rule_id} contains an invalid action")

        trusted_services = rule.get("trustedServices")
        if trusted_services is not None:
            if not isinstance(trusted_services, list) or not trusted_services:
                raise ValueError(f"rule {rule_id} trustedServices must be a non-empty array")
            if any(
                not isinstance(service, str) or not service.strip()
                for service in trusted_services
            ):
                raise ValueError(f"rule {rule_id} contains an invalid trusted service")

        role_patterns = rule.get("rolePatterns")
        if role_patterns is not None:
            if not isinstance(role_patterns, list) or not role_patterns:
                raise ValueError(f"rule {rule_id} rolePatterns must be a non-empty array")
            if any(
                not isinstance(pattern, str) or not pattern.strip()
                for pattern in role_patterns
            ):
                raise ValueError(f"rule {rule_id} contains an invalid role pattern")

        if trusted_services is None and role_patterns is None:
            raise ValueError(
                f"rule {rule_id} must define trustedServices or rolePatterns"
            )

        microservices = rule.get("microservices")
        if microservices is not None:
            if not isinstance(microservices, list) or not microservices:
                raise ValueError(f"rule {rule_id} microservices must be a non-empty array")
            if any(
                not isinstance(microservice, str) or not microservice.strip()
                for microservice in microservices
            ):
                raise ValueError(f"rule {rule_id} contains an invalid microservice")

        if enabled:
            rules.append({
                "id": rule_id,
                "actions": {action.strip().casefold() for action in actions},
                "trusted_services": (
                    {service.strip().casefold() for service in trusted_services}
                    if trusted_services is not None
                    else None
                ),
                "role_patterns": (
                    tuple(pattern.strip().casefold() for pattern in role_patterns)
                    if role_patterns is not None
                    else None
                ),
                "microservices": (
                    {microservice.strip().casefold() for microservice in microservices}
                    if microservices is not None
                    else None
                ),
            })

    return rules


def filter_unused_actions(
    *, finding, unused_actions, rules, microservice, role_trust_cache,
    iam_client, logger
):
    """Split unused actions into reportable and suppressed lists."""
    if not rules or not unused_actions:
        return unused_actions, [], []
    if finding.get("findingType") != "UnusedPermission":
        return unused_actions, [], []
    if finding.get("resourceType") != "AWS::IAM::Role":
        return unused_actions, [], []

    role_name = parse_role_name(finding.get("resource"))
    if not role_name:
        return unused_actions, [], []

    trusted_services = set()
    if any(rule["trusted_services"] is not None for rule in rules):
        trusted_services = get_role_trusted_services(
            iam_client=iam_client,
            role_name=role_name,
            cache=role_trust_cache,
            logger=logger,
        )

    visible_actions = []
    suppressed_actions = []
    matched_rule_ids = set()
    microservice_key = str(microservice or "").casefold()
    role_name_key = role_name.casefold()
    for action in unused_actions:
        action_key = action.casefold()
        matching_rules = [
            rule for rule in rules
            if action_key in rule["actions"]
            and (
                rule["trusted_services"] is None
                or trusted_services.intersection(rule["trusted_services"])
            )
            and (
                rule["role_patterns"] is None
                or any(
                    fnmatchcase(role_name_key, pattern)
                    for pattern in rule["role_patterns"]
                )
            )
            and (
                rule.get("microservices") is None
                or microservice_key in rule["microservices"]
            )
        ]
        if matching_rules:
            suppressed_actions.append(action)
            matched_rule_ids.update(rule["id"] for rule in matching_rules)
        else:
            visible_actions.append(action)

    return visible_actions, suppressed_actions, sorted(matched_rule_ids)
