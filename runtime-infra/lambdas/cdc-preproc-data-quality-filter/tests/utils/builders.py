import base64
import json

from tests.utils.classes import Category, DQCaseSpec, DQTestCase, PayloadInput, Table


def field(value):
    return {"S": value}


def number(value):
    return {"N": str(value)}


def boolean(value):
    return {"BOOL": value}


def build_payload(payload_input: PayloadInput):
    dynamodb = {}

    if payload_input.keys is not None:
        dynamodb["Keys"] = payload_input.keys

    if payload_input.new_image is not None:
        dynamodb["NewImage"] = payload_input.new_image

    if payload_input.old_image is not None:
        dynamodb["OldImage"] = payload_input.old_image

    return {
        "tableName": payload_input.table.value,
        "dynamodb": dynamodb,
    }


# A single DQ error, matching the shape of an item in execute_dq()["errors"].
def dq_error(code, check):
    return {
        "code": code,
        "check": check,
    }


# The expected output for a kept record (clean/quarantine/excluded), shaped like the
# real lambda output so tests can compare it directly.
def expect_ok(
    table: Table,
    category: Category,
    image_source,
    errors,
    filtered_payload,
    exclusion=None,
):
    return {
        "result": "Ok",
        # what execute_dq itself returns.
        "dq_result": {
            "processingLayer": category.value,
            "errors": errors,
            "imageSource": image_source,
            "exclusion": exclusion,
        },
        "metadata": {
            "partitionKeys": {
                "TABLE_NAME": table.value,
                "PROCESSING_LAYER": category.value,
            }
        },
        # this is what ends up in "data" once filters run.
        "filtered_payload": filtered_payload,
    }


# Builds a full DQTestCase from a spec. Table comes from spec.payload_input, so
# callers don't have to pass it again alongside category.
def dq_case(spec: DQCaseSpec) -> DQTestCase:
    payload_input = spec.payload_input
    filtered_input = (
        payload_input.without(*spec.removed_fields)
        if spec.removed_fields
        else payload_input
    )

    return DQTestCase(
        table=payload_input.table,
        category=spec.category,
        name=spec.name,
        record_id=spec.record_id,
        payload=build_payload(payload_input),
        expected=expect_ok(
            table=payload_input.table,
            category=spec.category,
            image_source=spec.image_source,
            errors=spec.errors,
            exclusion=spec.exclusion,
            filtered_payload=build_payload(filtered_input),
        ),
    )


def encode_record_data(payload):
    payload_json = json.dumps(
        payload,
        separators=(",", ":"),
        ensure_ascii=False,
    )

    return base64.b64encode(payload_json.encode("utf-8")).decode("utf-8")


def encode_raw_data(raw_text):
    return base64.b64encode(raw_text.encode("utf-8")).decode("utf-8")


def build_firehose_event(case):
    if isinstance(case.payload, str):
        data = encode_raw_data(case.payload)
    else:
        data = encode_record_data(case.payload)

    return {
        "records": [
            {
                "recordId": case.record_id,
                "data": data,
            }
        ]
    }
