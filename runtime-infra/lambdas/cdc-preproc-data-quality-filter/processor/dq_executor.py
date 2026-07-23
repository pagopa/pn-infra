import re

from processor.ddb_utils import (
    get_image,
    get_value,
    has_value,
)


def _check_required(image, rule):
    fields = rule.get("fields", [])

    return bool(fields) and all(
        has_value(image, field_name)
        for field_name in fields
    )


def _check_not_null(image, rule):
    return has_value(image, rule.get("field"))


def _check_starts_with(image, rule):
    value = get_value(image, rule.get("field"))
    prefix = rule.get("value")

    return (
        isinstance(value, str)
        and isinstance(prefix, str)
        and value.startswith(prefix)
    )


def _check_starts_with_any(image, rule):
    value = get_value(image, rule.get("field"))
    prefixes = rule.get("values", [])

    return (
        isinstance(value, str)
        and bool(prefixes)
        and value.startswith(tuple(prefixes))
    )


def _check_allowed_values(image, rule):
    value = get_value(image, rule.get("field"))

    return value in rule.get("values", [])


def _check_matches_regex(image, rule):
    value = get_value(image, rule.get("field"))
    pattern = rule.get("pattern")

    return (
        isinstance(value, str)
        and isinstance(pattern, str)
        and re.fullmatch(pattern, value) is not None
    )


CHECK_HANDLERS = {
    "required": _check_required,
    "not_null": _check_not_null,
    "starts_with": _check_starts_with,
    "starts_with_any": _check_starts_with_any,
    "allowed_values": _check_allowed_values,
    "matches_regex": _check_matches_regex,
}


def execute_rule(image, rule):
    rule_type = rule.get("type")
    handler = CHECK_HANDLERS.get(rule_type)

    if handler is None:
        raise ValueError(
            f"Unsupported Data Quality rule: {rule_type}"
        )

    return handler(image, rule)


def matches_condition(image, condition):
    if not condition:
        return True

    condition_rule = {
        "type": condition.get("operator"),
        "field": condition.get("field"),
        "value": condition.get("value"),
        "values": condition.get("values", []),
        "pattern": condition.get("pattern"),
    }

    return execute_rule(image, condition_rule)


def is_excluded(image, exclusions):
    for exclusion in exclusions:
        if execute_rule(image, exclusion):
            return True, exclusion.get("name")

    return False, None


def execute_check(image, check):
    condition = check.get("when")

    if condition and not matches_condition(image, condition):
        return True

    nested_rules = check.get("rules")

    if nested_rules:
        return all(
            execute_rule(image, nested_rule)
            for nested_rule in nested_rules
        )

    return execute_rule(image, check)


def execute_dq(payload, config):
    image_priority = (
        config
        .get("imageSelection", {})
        .get(
            "priority",
            ["NewImage", "OldImage", "Keys"],
        )
    )

    image, image_source = get_image(
        payload=payload,
        priority=image_priority,
    )

    routing = config.get("routing", {})

    excluded, exclusion_name = is_excluded(
        image=image,
        exclusions=config.get("exclusions", []),
    )

    if excluded:
        return {
            "processingLayer": routing.get(
                "excludedStatus",
                "excluded",
            ),
            "errors": [],
            "imageSource": image_source,
            "exclusion": exclusion_name,
        }

    errors = []

    for check in config.get("checks", []):
        if execute_check(image, check):
            continue

        errors.append({
            "code": check.get(
                "errorCode",
                "DQ_CHECK_FAILED",
            ),
            "check": check.get(
                "name",
                "unnamed_check",
            ),
        })

    if errors:
        processing_layer = routing.get(
            "quarantineStatus",
            "quarantine",
        )
    else:
        processing_layer = routing.get(
            "cleanStatus",
            "clean",
        )

    return {
        "processingLayer": processing_layer,
        "errors": errors,
        "imageSource": image_source,
        "exclusion": None,
    }