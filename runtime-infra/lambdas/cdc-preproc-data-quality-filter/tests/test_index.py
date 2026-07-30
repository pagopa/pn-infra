import index
from tests.fixtures.firehose_events import encode_raw_data, encode_record_data


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


# sostituisce le dipendenze del lambda_handler per isolare la logica di orchestrazione:
# config assente => Dropped, altrimenti il layer restituito dal finto execute_dq
def _stub_pipeline(monkeypatch, table_config, processing_layer=None):
    monkeypatch.setattr(index, "load_table_config", lambda table_name: table_config)

    if processing_layer is not None:
        monkeypatch.setattr(
            index,
            "execute_dq",
            lambda payload, config: _dq_result(processing_layer),
        )
        monkeypatch.setattr(
            index,
            "apply_filters",
            lambda payload, processing_layer, filters: payload,
        )


# test che verifica che la codifica produca il base64 del JSON compatto e che la
# decodifica ricostruisca il payload originale
def test_encode_payload_produces_compact_base64_json():
    payload = {"foo": "bar", "nested": {"a": 1}}
    # base64 di {"foo":"bar","nested":{"a":1}}, senza spazi tra i separatori
    expected_encoded = "eyJmb28iOiJiYXIiLCJuZXN0ZWQiOnsiYSI6MX19"

    encoded = index.encode_payload(payload)

    assert encoded == expected_encoded
    assert index.decode_payload(expected_encoded) == payload


# test che verifica che il nome tabella nei metadata diventi "UNKNOWN" quando non specificato
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


# test che verifica che un record con JSON non valido venga marcato come ProcessingFailed
# senza metadata, restituendo il data originale
def test_lambda_handler_processing_failed_on_invalid_json():
    record = _raw_record("bad-record", "this-is-not-json")

    result = index.lambda_handler({"records": [record]}, None)

    assert result["records"] == [
        {
            "recordId": "bad-record",
            "result": "ProcessingFailed",
            "data": record["data"],
        }
    ]


# test che verifica che il record venga scartato (Dropped) quando la tabella non ha una configurazione
def test_lambda_handler_dropped_when_table_config_missing(monkeypatch):
    _stub_pipeline(monkeypatch, table_config=None)

    record = _record("dropped-record", {"tableName": "some-table", "dynamodb": {}})

    result = index.lambda_handler({"records": [record]}, None)

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


# test che verifica che il percorso "Ok" componga correttamente risultato DQ, filtri e metadata nell'output
def test_lambda_handler_ok_flow_uses_dq_result_and_filters(monkeypatch):
    _stub_pipeline(monkeypatch, table_config={"filters": []}, processing_layer="clean")

    payload = {"tableName": "some-table", "dynamodb": {}}

    result = index.lambda_handler({"records": [_record("ok-record", payload)]}, None)
    record = result["records"][0]

    assert record["result"] == "Ok"
    assert record["metadata"] == {
        "partitionKeys": {
            "TABLE_NAME": "some-table",
            "PROCESSING_LAYER": "clean",
        }
    }
    assert index.decode_payload(record["data"]) == payload


# test che verifica che un processing layer non supportato restituito dal DQ produca ProcessingFailed
def test_lambda_handler_processing_failed_on_unsupported_processing_layer(monkeypatch):
    _stub_pipeline(
        monkeypatch,
        table_config={"filters": []},
        processing_layer="not-a-real-layer",
    )

    record = _record("unsupported-layer-record", {"tableName": "t", "dynamodb": {}})

    result = index.lambda_handler({"records": [record]}, None)

    assert result["records"] == [
        {
            "recordId": "unsupported-layer-record",
            "result": "ProcessingFailed",
            "data": record["data"],
        }
    ]


# test che verifica che ogni record di un batch venga elaborato in modo indipendente:
# il fallimento di uno non blocca né altera l'esito degli altri
def test_lambda_handler_processes_records_independently(monkeypatch):
    _stub_pipeline(monkeypatch, table_config=None)

    event = {
        "records": [
            _record("r1", {"tableName": "t1", "dynamodb": {}}),
            _raw_record("r2", "not-json"),
            _record("r3", {"tableName": "t3", "dynamodb": {}}),
        ]
    }

    result = index.lambda_handler(event, None)

    assert [(r["recordId"], r["result"]) for r in result["records"]] == [
        ("r1", "Dropped"),
        ("r2", "ProcessingFailed"),
        ("r3", "Dropped"),
    ]
