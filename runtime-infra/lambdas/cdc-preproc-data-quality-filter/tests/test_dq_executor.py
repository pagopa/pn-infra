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


# test che verifica ogni tipo di regola (required, not_null, starts_with, starts_with_any, allowed_values, matches_regex)
# nei rispettivi casi di successo, fallimento e valore non valido
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
            {"sk": _field("COURTESY#default#EMAIL")},
            {"type": "matches_regex", "field": "sk", "pattern": "^COURTESY#.*#(SMS|EMAIL|APPIO)$"},
            True,
            id="matches_regex-match",
        ),
        pytest.param(
            {"sk": _field("COURTESY#default#FAX")},
            {"type": "matches_regex", "field": "sk", "pattern": "^COURTESY#.*#(SMS|EMAIL|APPIO)$"},
            False,
            id="matches_regex-mismatch",
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


# test che verifica che venga sollevato un errore per un tipo di regola non supportato
def test_execute_rule_unsupported_type_raises_value_error():
    with pytest.raises(ValueError):
        execute_rule({}, {"type": "not_a_real_check"})


# test che verifica che una condizione assente (vuota o None) sia sempre considerata soddisfatta
def test_matches_condition_true_when_condition_empty():
    assert matches_condition({"pk": _field("AB#1")}, {}) is True
    assert matches_condition({"pk": _field("AB#1")}, None) is True


# test che verifica che la condizione venga valutata applicando l'operatore configurato
def test_matches_condition_evaluates_operator():
    image = {"pk": _field("AB#1")}
    condition = {"field": "pk", "operator": "starts_with", "value": "AB#"}

    assert matches_condition(image, condition) is True

    condition_false = {"field": "pk", "operator": "starts_with", "value": "CO#"}
    assert matches_condition(image, condition_false) is False


# test che verifica che nessuna esclusione venga applicata quando nessuna regola di esclusione corrisponde
def test_is_excluded_no_match_returns_false_and_none():
    image = {"pk": _field("AB#1")}
    exclusions = [
        {"name": "excluded_pk_prefix", "type": "starts_with_any", "field": "pk", "values": ["VA#", "VC#"]}
    ]

    excluded, name = is_excluded(image, exclusions)

    assert excluded is False
    assert name is None


# test che verifica che venga restituito il nome dell'esclusione quando una regola corrisponde
def test_is_excluded_match_returns_true_and_exclusion_name():
    image = {"pk": _field("VC#1")}
    exclusions = [
        {"name": "excluded_pk_prefix", "type": "starts_with_any", "field": "pk", "values": ["VA#", "VC#"]}
    ]

    excluded, name = is_excluded(image, exclusions)

    assert excluded is True
    assert name == "excluded_pk_prefix"


# test che verifica che un controllo con condizione "when" non soddisfatta venga considerato automaticamente superato
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


# test che verifica che le regole annidate vengano valutate quando la condizione "when" è soddisfatta
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


# test che verifica che, in assenza di "when", il controllo venga valutato direttamente come regola singola
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


# test che verifica che il payload venga instradato come "clean" quando nessun controllo fallisce
def test_execute_dq_returns_clean_when_no_errors():
    payload = {"dynamodb": {"NewImage": {"pk": _field("KEEP#1")}}}

    result = execute_dq(payload=payload, config=_synthetic_config())

    assert result["processingLayer"] == "clean"
    assert result["errors"] == []
    assert result["imageSource"] == "NewImage"
    assert result["exclusion"] is None


# test che verifica che il payload venga instradato come "quarantine" e riporti l'errore quando un controllo fallisce
def test_execute_dq_returns_quarantine_when_check_fails():
    payload = {"dynamodb": {"NewImage": {"other": _field("value")}}}

    result = execute_dq(payload=payload, config=_synthetic_config())

    assert result["processingLayer"] == "quarantine"
    assert result["errors"] == [
        {"code": "DQ_REQUIRED_FIELDS", "check": "check_required_fields"}
    ]
    assert result["exclusion"] is None


# test che verifica che il payload venga instradato come "excluded" quando corrisponde a una regola di esclusione
def test_execute_dq_returns_excluded_when_exclusion_matches():
    payload = {"dynamodb": {"NewImage": {"pk": _field("EXCLUDED#1")}}}

    result = execute_dq(payload=payload, config=_synthetic_config())

    assert result["processingLayer"] == "excluded"
    assert result["errors"] == []
    assert result["exclusion"] == "excluded_pk_prefix"


# test che verifica che vengano usati gli stati di routing di default quando la
# configurazione non li specifica, per tutti e tre gli instradamenti possibili
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


# test che verifica che l'assenza di immagini disponibili venga riportata come sorgente "Missing"
def test_execute_dq_reports_missing_image_as_missing_source():
    result = execute_dq(payload={"dynamodb": {}}, config=_synthetic_config())

    assert result["imageSource"] == "Missing"
