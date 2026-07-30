import base64
import json


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
