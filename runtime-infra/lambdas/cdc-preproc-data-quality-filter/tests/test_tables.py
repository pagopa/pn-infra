import base64
import json

import pytest

import index
from processor.dq_executor import execute_dq
from processor.input_loader import load_table_config
from tests.utils.builders import build_firehose_event
from tests.utils.classes import LambdaContext, is_dq_routing
from tests.utils.tables import PAYLOADS


# checks DQ routing (clean/quarantine/excluded) and reported errors, using each table's real config
@pytest.mark.parametrize(
    # only DQ-routing cases apply here; ERROR cases have no execute_dq result to compare.
    "case",
    [case for case in PAYLOADS if is_dq_routing(case.category)],
    ids=lambda case: case.record_id,
)
def test_execute_dq(case):
    config = load_table_config(case.table.value)
    assert config is not None

    result = execute_dq(payload=case.payload, config=config)

    assert result == case.expected["dq_result"]


# end-to-end lambda_handler check with real config
@pytest.mark.parametrize("case", PAYLOADS, ids=lambda case: case.record_id)
def test_lambda_handler(case):
    event = build_firehose_event(case)
    original_data = event["records"][0]["data"]

    result = index.lambda_handler(event, LambdaContext())
    records = result["records"]

    assert len(records) == 1

    record = records[0]
    expected = case.expected

    if expected["result"] == "Ok":
        # compare data decoded, against the filtered payload, not raw base64
        decoded_data = json.loads(base64.b64decode(record["data"]))

        # merge decoded data over the raw record so the comparison ignores base64 encoding.
        assert record | {"data": decoded_data} == {
            "recordId": case.record_id,
            "result": "Ok",
            "data": expected["filtered_payload"],
            "metadata": expected["metadata"],
        }
    else:
        # original record is returned unchanged, with no metadata
        assert record == {
            "recordId": case.record_id,
            "result": expected["result"],
            "data": original_data,
        }
