import base64
import json
from datetime import datetime, timezone

from processor.input_loader import load_table_config
from processor.dq_executor import execute_dq
from processor.payload_filter import apply_filters


def decode_payload(encoded_data):
    decoded_data = base64.b64decode(
        encoded_data
    ).decode("utf-8")

    return json.loads(decoded_data)


def encode_payload(payload):
    payload_json = json.dumps(
        payload,
        separators=(",", ":"),
        ensure_ascii=False,
    )

    return base64.b64encode(
        payload_json.encode("utf-8")
    ).decode("utf-8")


def build_metadata(table_name, processing_layer):
    return {
        "partitionKeys": {
            "TABLE_NAME": table_name or "UNKNOWN",
            "PROCESSING_LAYER": processing_layer,
        }
    }


def lambda_handler(event, context):
    records = event.get("records", [])

    print(
        "Starting Firehose preprocessing Lambda. "
        f"Processing {len(records)} records."
    )

    output = []

    counters = {
        "kept": 0,
        "dropped": 0,
        "clean": 0,
        "quarantine": 0,
        "excluded": 0,
        "failed": 0,
    }

    for record in records:
        record_id = record.get("recordId")
        original_data = record.get("data")

        try:
            payload = decode_payload(original_data)
            table_name = payload.get("tableName")

            table_config = load_table_config(table_name)

            if table_config is None:
                counters["dropped"] += 1

                output.append({
                    "recordId": record_id,
                    "result": "Dropped",
                    "data": original_data,
                    "metadata": build_metadata(
                        table_name=table_name,
                        processing_layer="dropped",
                    ),
                })

                continue

            dq_result = execute_dq(
                payload=payload,
                config=table_config,
            )

            processing_layer = dq_result["processingLayer"]
            dq_errors = dq_result.get("errors", [])
            image_source = dq_result.get(
                "imageSource",
                "Missing",
            )

            if processing_layer not in (
                "clean",
                "quarantine",
                "excluded",
            ):
                raise ValueError(
                    "Unsupported processing layer: "
                    f"{processing_layer}"
                )

            if dq_errors:
                print(
                    "Data Quality checks failed. "
                    f"RecordId={record_id}, "
                    f"TableName={table_name}, "
                    f"ImageSource={image_source}, "
                    f"Errors={json.dumps(dq_errors)}"
                )

            if processing_layer == "excluded":
                print(
                    "Record excluded. "
                    f"RecordId={record_id}, "
                    f"TableName={table_name}, "
                    f"ImageSource={image_source}, "
                    f"Exclusion={dq_result.get('exclusion')}"
                )

            filtered_payload = apply_filters(
                payload=payload,
                processing_layer=processing_layer,
                filters=table_config.get("filters", []),
            )

            counters["kept"] += 1
            counters[processing_layer] += 1

            output.append({
                "recordId": record_id,
                "result": "Ok",
                "data": encode_payload(filtered_payload),
                "metadata": build_metadata(
                    table_name=table_name,
                    processing_layer=processing_layer,
                ),
            })

        except Exception as error:
            counters["failed"] += 1

            print(
                "Technical error during record processing. "
                f"RecordId={record_id}, "
                f"ErrorType={type(error).__name__}, "
                f"Error={str(error)}"
            )

            output.append({
                "recordId": record_id,
                "result": "ProcessingFailed",
                "data": original_data,
            })

    execution_time = datetime.now(timezone.utc).isoformat()

    print(
        f"Batch processed at {execution_time}. "
        f"Kept={counters['kept']}, "
        f"Dropped={counters['dropped']}, "
        f"Clean={counters['clean']}, "
        f"Quarantine={counters['quarantine']}, "
        f"Excluded={counters['excluded']}, "
        f"Failed={counters['failed']}"
    )

    return {
        "records": output
    }