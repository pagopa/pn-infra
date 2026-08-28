import index
from tests.utils.builders import encode_raw_data, encode_record_data
from tests.utils.classes import LambdaContext


def _record(record_id, payload):
    return {"recordId": record_id, "data": encode_record_data(payload)}


def _raw_record(record_id, raw_text):
    return {"recordId": record_id, "data": encode_raw_data(raw_text)}


def _dq_result(processing_layer):
    return {
        "processingLayer": processing_layer,
        "errors": [],
        "imageSource": "NewImage",
        "exclusion": None,
    }


# Stubs out lambda_handler's dependencies so only the orchestration logic is tested:
# missing config routes to Dropped, otherwise the layer returned by the fake execute_dq.
def _stub_pipeline(monkeypatch, table_config, processing_layer=None):
    monkeypatch.setattr(index, "load_table_config", lambda table_name: table_config)

    # only stub execute_dq/apply_filters when a processing_layer is given, i.e.
    # for tests that exercise the "Ok" path rather than the "Dropped" path.
    if processing_layer is not None:
        monkeypatch.setattr(
            index,
            "execute_dq",
            lambda payload, config: _dq_result(processing_layer),
        )
        monkeypatch.setattr(
            index,
            "apply_filters",
            lambda payload, processing_layer, filters: {**payload, "filtered": True},
        )


# Verify that encoding produces compact base64 JSON, and that decoding rebuilds
# the original payload.
def test_encode_payload_produces_compact_base64_json():
    payload = {"foo": "bar", "nested": {"a": 1}}
    # base64 of {"foo":"bar","nested":{"a":1}}, with no spaces after the separators.
    expected_encoded = "eyJmb28iOiJiYXIiLCJuZXN0ZWQiOnsiYSI6MX19"

    encoded = index.encode_payload(payload)

    assert encoded == expected_encoded
    assert index.decode_payload(expected_encoded) == payload


# Verify that the table name in metadata defaults to "UNKNOWN" when not given.
def test_build_metadata_defaults_to_unknown_table_name():
    metadata = index.build_metadata(
        table_name=None,
        processing_layer="clean",
    )

    assert metadata == {
        "partitionKeys": {
            "TABLE_NAME": "UNKNOWN",
            "PROCESSING_LAYER": "clean",
        }
    }


# Verify that a record with invalid JSON is marked ProcessingFailed, with the
# original data returned unchanged and no metadata.
def test_lambda_handler_processing_failed_on_invalid_json():
    record = _raw_record("bad-record", "this-is-not-json")

    result = index.lambda_handler({"records": [record]}, LambdaContext())

    assert result["records"] == [
        {
            "recordId": "bad-record",
            "result": "ProcessingFailed",
            "data": record["data"],
        }
    ]


# Verify that a record is marked Dropped when its table has no config.
def test_lambda_handler_dropped_when_table_config_missing(monkeypatch):
    _stub_pipeline(monkeypatch, table_config=None)

    record = _record("dropped-record", {"tableName": "some-table", "dynamodb": {}})

    result = index.lambda_handler({"records": [record]}, LambdaContext())

    assert result["records"] == [
        {
            "recordId": "dropped-record",
            "result": "Dropped",
            "data": record["data"],
            "metadata": {
                "partitionKeys": {
                    "TABLE_NAME": "some-table",
                    "PROCESSING_LAYER": "dropped",
                }
            },
        }
    ]


# Verify that the "Ok" path composes the DQ result, filters, and metadata correctly
# into the output. apply_filters is stubbed to observably mutate the payload, so
# this fails if lambda_handler stops calling it or drops its output.
def test_lambda_handler_ok_flow_uses_dq_result_and_filters(monkeypatch):
    table_config = {"filters": ["some-filter"]}
    apply_filters_calls = []

    def fake_apply_filters(payload, processing_layer, filters):
        apply_filters_calls.append((payload, processing_layer, filters))
        return {**payload, "filtered": True}

    monkeypatch.setattr(index, "load_table_config", lambda table_name: table_config)
    monkeypatch.setattr(index, "execute_dq", lambda payload, config: _dq_result("clean"))
    monkeypatch.setattr(index, "apply_filters", fake_apply_filters)

    payload = {"tableName": "some-table", "dynamodb": {}}

    result = index.lambda_handler({"records": [_record("ok-record", payload)]}, LambdaContext())
    record = result["records"][0]

    assert record["result"] == "Ok"
    assert record["metadata"] == {
        "partitionKeys": {
            "TABLE_NAME": "some-table",
            "PROCESSING_LAYER": "clean",
        }
    }
    # apply_filters must be called with the decoded payload, the DQ processing
    # layer, and the table's configured filters.
    assert apply_filters_calls == [(payload, "clean", ["some-filter"])]
    # the output must be apply_filters' return value, not the original payload.
    assert index.decode_payload(record["data"]) == {**payload, "filtered": True}


# Verify that a record routed to quarantine is logged at WARNING level, so it does not
# match the lambda-alarms metric filter (which only matches ERROR-level lines).
# setup_logger installs its own stdout handler, bypassing caplog, so we assert
# against captured stdout instead.
def test_lambda_handler_quarantine_logs_at_warning_level(monkeypatch, capsys):
    _stub_pipeline(monkeypatch, table_config={"filters": []}, processing_layer="quarantine")

    payload = {"tableName": "some-table", "dynamodb": {}}

    result = index.lambda_handler({"records": [_record("quarantine-record", payload)]}, LambdaContext())

    record = result["records"][0]
    # quarantine is still a successful outcome for the record itself.
    assert record["result"] == "Ok"
    assert record["metadata"]["partitionKeys"]["PROCESSING_LAYER"] == "quarantine"

    log_lines = capsys.readouterr().out.splitlines()
    # keep only the WARNING-level line(s) emitted for this record.
    warning_lines = [line for line in log_lines if " WARNING " in line]
    # exactly one WARNING line must be emitted, the one raising the alarm.
    assert len(warning_lines) == 1
    assert "Record routed to quarantine" in warning_lines[0]


# Verify that an unsupported processing layer returned by DQ results in ProcessingFailed.
def test_lambda_handler_processing_failed_on_unsupported_processing_layer(monkeypatch):
    _stub_pipeline(
        monkeypatch,
        table_config={"filters": []},
        processing_layer="not-a-real-layer",
    )

    record = _record("unsupported-layer-record", {"tableName": "t", "dynamodb": {}})

    result = index.lambda_handler({"records": [record]}, LambdaContext())

    assert result["records"] == [
        {
            "recordId": "unsupported-layer-record",
            "result": "ProcessingFailed",
            "data": record["data"],
        }
    ]


# Verify that each record in a batch is processed independently, and that one
# record failing doesn't affect the others.
def test_lambda_handler_processes_records_independently(monkeypatch):
    _stub_pipeline(monkeypatch, table_config=None)

    event = {
        "records": [
            _record("r1", {"tableName": "t1", "dynamodb": {}}),
            _raw_record("r2", "not-json"),
            _record("r3", {"tableName": "t3", "dynamodb": {}}),
        ]
    }

    result = index.lambda_handler(event, LambdaContext())

    assert [(r["recordId"], r["result"]) for r in result["records"]] == [
        ("r1", "Dropped"),
        ("r2", "ProcessingFailed"),
        ("r3", "Dropped"),
    ]