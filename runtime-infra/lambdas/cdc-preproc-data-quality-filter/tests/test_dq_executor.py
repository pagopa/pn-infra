import pytest

from processor.dq_executor import (
    execute_check,
    execute_dq,
    execute_rule,
    is_excluded,
    matches_condition,
)


def _field(value):
    return {"S": value}


# Verify every rule type in its success case, its failure case, and with an invalid value.
@pytest.mark.parametrize(
    "image,rule,expected",
    [
        pytest.param(
            {"pk": _field("a"), "sk": _field("b")},
            {"type": "required", "fields": ["pk", "sk"]},
            True,
            id="required-all-fields-present",
        ),
        pytest.param(
            {"pk": _field("a")},
            {"type": "required", "fields": ["pk", "sk"]},
            False,
            id="required-field-missing-or-blank",
        ),
        pytest.param(
            {"pk": _field("a")},
            {"type": "required", "fields": []},
            False,
            id="required-no-fields-configured",
        ),
        pytest.param(
            {"accepted": {"BOOL": True}},
            {"type": "not_null", "field": "accepted"},
            True,
            id="not_null-value-present",
        ),
        pytest.param(
            {},
            {"type": "not_null", "field": "accepted"},
            False,
            id="not_null-value-missing",
        ),
        pytest.param(
            {"pk": _field("AB#PF-1")},
            {"type": "starts_with", "field": "pk", "value": "AB#"},
            True,
            id="starts_with-match",
        ),
        pytest.param(
            {"pk": _field("CO#PF-1")},
            {"type": "starts_with", "field": "pk", "value": "AB#"},
            False,
            id="starts_with-mismatch",
        ),
        pytest.param(
            {"pk": {"BOOL": True}},
            {"type": "starts_with", "field": "pk", "value": "AB#"},
            False,
            id="starts_with-value-not-string",
        ),
        pytest.param(
            {"pk": _field("VC#PF-1")},
            {"type": "starts_with_any", "field": "pk", "values": ["VA#", "VC#"]},
            True,
            id="starts_with_any-match",
        ),
        pytest.param(
            {"pk": _field("AB#PF-1")},
            {"type": "starts_with_any", "field": "pk", "values": ["VA#", "VC#"]},
            False,
            id="starts_with_any-no-match",
        ),
        pytest.param(
            {"pk": _field("AB#PF-1")},
            {"type": "starts_with_any", "field": "pk", "values": []},
            False,
            id="starts_with_any-values-empty",
        ),
        pytest.param(
            {"sk": _field("INVALID#1")},
            {"type": "not_starts_with_any", "field": "sk", "values": ["TOS#", "DATAPRIVACY#"]},
            True,
            id="not_starts_with_any-no-match",
        ),
        pytest.param(
            {"sk": _field("TOS#1")},
            {"type": "not_starts_with_any", "field": "sk", "values": ["TOS#", "DATAPRIVACY#"]},
            False,
            id="not_starts_with_any-match",
        ),
        pytest.param(
            {"sk": {"BOOL": True}},
            {"type": "not_starts_with_any", "field": "sk", "values": ["TOS#", "DATAPRIVACY#"]},
            False,
            id="not_starts_with_any-value-not-string",
        ),
        pytest.param(
            {"sk": _field("INVALID#1")},
            {"type": "not_starts_with_any", "field": "sk", "values": []},
            False,
            id="not_starts_with_any-values-empty",
        ),
        pytest.param(
            {"addresshash": _field("ENABLED")},
            {"type": "allowed_values", "field": "addresshash", "values": ["ENABLED", "DISABLED"]},
            True,
            id="allowed_values-in-list",
        ),
        pytest.param(
            {"addresshash": _field("OTHER")},
            {"type": "allowed_values", "field": "addresshash", "values": ["ENABLED", "DISABLED"]},
            False,
            id="allowed_values-not-in-list",
        ),
        pytest.param(
            {"sk": {"BOOL": True}},
            {"type": "matches_regex", "field": "sk", "pattern": ".*"},
            False,
            id="matches_regex-value-not-string",
        ),
    ],
)
def test_execute_rule(image, rule, expected):
    assert execute_rule(image, rule) is expected


# Verify that an unsupported rule type raises a ValueError.
def test_execute_rule_unsupported_type_raises_value_error():
    with pytest.raises(ValueError):
        execute_rule({}, {"type": "not_a_real_check"})


# Verify that an empty or missing condition is always treated as satisfied.
def test_matches_condition_true_when_condition_empty():
    assert matches_condition({"pk": _field("AB#1")}, {}) is True
    assert matches_condition({"pk": _field("AB#1")}, None) is True


# Verify that a condition is evaluated using its configured operator.
def test_matches_condition_evaluates_operator():
    image = {"pk": _field("AB#1")}
    condition = {"field": "pk", "operator": "starts_with", "value": "AB#"}

    assert matches_condition(image, condition) is True

    condition_false = {"field": "pk", "operator": "starts_with", "value": "CO#"}
    assert matches_condition(image, condition_false) is False


# Verify that no exclusion is applied when no exclusion rule matches.
def test_is_excluded_no_match_returns_false_and_none():
    image = {"pk": _field("AB#1")}
    exclusions = [
        {"name": "excluded_pk_prefix", "type": "starts_with_any", "field": "pk", "values": ["VA#", "VC#"]}
    ]

    excluded, name = is_excluded(image, exclusions)

    assert excluded is False
    assert name is None


# Verify that a matching exclusion rule returns its name along with the match.
def test_is_excluded_match_returns_true_and_exclusion_name():
    image = {"pk": _field("VC#1")}
    exclusions = [
        {"name": "excluded_pk_prefix", "type": "starts_with_any", "field": "pk", "values": ["VA#", "VC#"]}
    ]

    excluded, name = is_excluded(image, exclusions)

    assert excluded is True
    assert name == "excluded_pk_prefix"


# Verify that a conditional exclusion is not applied when its "when" condition
# is not met.
def test_is_excluded_conditional_when_not_met_returns_false_and_none():
    image = {
        "pk": _field("AB#1"),
        "sk": _field("INVALID#1"),
    }
    exclusions = [
        {
            "name": "excluded_invalid_consents",
            "type": "conditional",
            "when": {
                "field": "pk",
                "operator": "starts_with",
                "value": "CO#",
            },
            "rules": [
                {
                    "type": "not_starts_with_any",
                    "field": "sk",
                    "values": ["TOS#", "DATAPRIVACY#"],
                }
            ],
        }
    ]

    excluded, name = is_excluded(image, exclusions)

    assert excluded is False
    assert name is None


# Verify that a conditional exclusion is applied when its "when" condition is
# met and its nested rule matches.
def test_is_excluded_conditional_match_returns_true_and_exclusion_name():
    image = {
        "pk": _field("CO#1"),
        "sk": _field("INVALID#1"),
    }
    exclusions = [
        {
            "name": "excluded_invalid_consents",
            "type": "conditional",
            "when": {
                "field": "pk",
                "operator": "starts_with",
                "value": "CO#",
            },
            "rules": [
                {
                    "type": "not_starts_with_any",
                    "field": "sk",
                    "values": ["TOS#", "DATAPRIVACY#"],
                }
            ],
        }
    ]

    excluded, name = is_excluded(image, exclusions)

    assert excluded is True
    assert name == "excluded_invalid_consents"


# Verify that a check with an unmet "when" condition is skipped and counted as passed.
def test_execute_check_passes_automatically_when_condition_not_met():
    image = {"pk": _field("CO#1")}
    check = {
        "name": "check_invalid_legal_courtesy",
        "when": {"field": "pk", "operator": "starts_with", "value": "AB#"},
        "rules": [
            {"type": "starts_with_any", "field": "sk", "values": ["LEGAL#", "COURTESY#"]}
        ],
    }

    assert execute_check(image, check) is True


# Verify that nested rules are evaluated once the "when" condition is met.
def test_execute_check_evaluates_nested_rules_when_condition_met():
    image = {
        "pk": _field("AB#1"),
        "sk": _field("TEST_PROVA#default#EMAIL"),
    }
    check = {
        "name": "check_invalid_legal_courtesy",
        "when": {"field": "pk", "operator": "starts_with", "value": "AB#"},
        "rules": [
            {"type": "starts_with_any", "field": "sk", "values": ["LEGAL#", "COURTESY#"]}
        ],
    }

    assert execute_check(image, check) is False


# Verify that a check with no "when" is evaluated directly as a plain rule.
def test_execute_check_without_when_evaluates_rule_directly():
    image = {"pk": _field("a"), "sk": _field("b")}
    check = {"type": "required", "fields": ["pk", "sk"]}

    assert execute_check(image, check) is True


def _synthetic_config():
    return {
        "imageSelection": {"priority": ["NewImage", "OldImage", "Keys"]},
        "routing": {
            "cleanStatus": "clean",
            "quarantineStatus": "quarantine",
            "excludedStatus": "excluded",
        },
        "exclusions": [
            {
                "name": "excluded_pk_prefix",
                "type": "starts_with",
                "field": "pk",
                "value": "EXCLUDED#",
            }
        ],
        "checks": [
            {
                "name": "check_required_fields",
                "type": "required",
                "fields": ["pk"],
                "errorCode": "DQ_REQUIRED_FIELDS",
            }
        ],
    }


# Verify that the payload is routed to "clean" when no check fails.
def test_execute_dq_returns_clean_when_no_errors():
    payload = {"dynamodb": {"NewImage": {"pk": _field("KEEP#1")}}}

    result = execute_dq(payload=payload, config=_synthetic_config())

    assert result["processingLayer"] == "clean"
    assert result["errors"] == []
    assert result["imageSource"] == "NewImage"
    assert result["exclusion"] is None


# Verify that the payload is routed to "quarantine" and the failing check is reported
# as an error when a check fails.
def test_execute_dq_returns_quarantine_when_check_fails():
    payload = {"dynamodb": {"NewImage": {"other": _field("value")}}}

    result = execute_dq(payload=payload, config=_synthetic_config())

    assert result["processingLayer"] == "quarantine"
    assert result["errors"] == [
        {"code": "DQ_REQUIRED_FIELDS", "check": "check_required_fields"}
    ]
    assert result["exclusion"] is None


# Verify that the payload is routed to "excluded" when an exclusion rule matches,
# without running any of the checks.
def test_execute_dq_returns_excluded_when_exclusion_matches():
    payload = {"dynamodb": {"NewImage": {"pk": _field("EXCLUDED#1")}}}

    result = execute_dq(payload=payload, config=_synthetic_config())

    assert result["processingLayer"] == "excluded"
    assert result["errors"] == []
    assert result["exclusion"] == "excluded_pk_prefix"


# Verify that the default routing statuses are used for all three layers when the
# config doesn't set them explicitly.
@pytest.mark.parametrize(
    "image,expected_layer",
    [
        pytest.param({"pk": _field("KEEP#1")}, "clean", id="clean-default"),
        pytest.param({"other": _field("x")}, "quarantine", id="quarantine-default"),
        pytest.param({"pk": _field("EXCLUDED#1")}, "excluded", id="excluded-default"),
    ],
)
def test_execute_dq_falls_back_to_default_routing_statuses(image, expected_layer):
    config = _synthetic_config()
    config["routing"] = {}

    result = execute_dq(
        payload={"dynamodb": {"NewImage": image}},
        config=config,
    )

    assert result["processingLayer"] == expected_layer


# Verify that the image source is reported as "Missing" when no image is available.
def test_execute_dq_reports_missing_image_as_missing_source():
    result = execute_dq(payload={"dynamodb": {}}, config=_synthetic_config())

    assert result["imageSource"] == "Missing"
