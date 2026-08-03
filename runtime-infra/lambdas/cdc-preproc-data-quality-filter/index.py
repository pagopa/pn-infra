import base64
import json

from config import logger, setup_logger
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
    setup_logger(context.aws_request_id)

    records = event.get("records", [])

    logger.info(
        "Starting Firehose preprocessing Lambda. "
        "Processing %s records.",
        len(records),
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
        event_id = None

        try:
            payload = decode_payload(original_data)

            event_id = payload.get("eventID")
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

            filtered_payload = apply_filters(
                payload=payload,
                processing_layer=processing_layer,
                filters=table_config.get("filters", []),
            )

            output.append({
                "recordId": record_id,
                "result": "Ok",
                "data": encode_payload(filtered_payload),
                "metadata": build_metadata(
                    table_name=table_name,
                    processing_layer=processing_layer,
                ),
            })

            counters["kept"] += 1
            counters[processing_layer] += 1

            if processing_layer == "clean":
                logger.info(
                    "Record routed to clean. "
                    "EventID=%s, "
                    "Result=Ok, "
                    "ProcessingLayer=%s, "
                    "TableName=%s, "
                    "ImageSource=%s",
                    event_id,
                    processing_layer,
                    table_name,
                    image_source,
                )

            elif processing_layer == "excluded":
                logger.info(
                    "Record routed to excluded. "
                    "EventID=%s, "
                    "Result=Ok, "
                    "ProcessingLayer=%s, "
                    "TableName=%s, "
                    "ImageSource=%s, "
                    "Exclusion=%s",
                    event_id,
                    processing_layer,
                    table_name,
                    image_source,
                    dq_result.get("exclusion"),
                )

            elif processing_layer == "quarantine":
                logger.error(
                    "Record routed to quarantine. "
                    "EventID=%s, "
                    "Result=Ok, "
                    "ProcessingLayer=%s, "
                    "TableName=%s, "
                    "ImageSource=%s, "
                    "Errors=%s",
                    event_id,
                    processing_layer,
                    table_name,
                    image_source,
                    json.dumps(
                        dq_errors,
                        separators=(",", ":"),
                        ensure_ascii=False,
                    ),
                )     

        except Exception as error:
            counters["failed"] += 1
        
            logger.exception(
                "PROCESSING_FAILED Technical error during record processing. "
                "RecordID=%s, "
                "ErrorType=%s, "
                "Error=%s",
                record_id,
                type(error).__name__,
                str(error),
            )
        
            output.append({
                "recordId": record_id,
                "result": "ProcessingFailed",
                "data": original_data,
            })

    logger.info(
        "Batch processed. "
        "Kept=%s, "
        "Dropped=%s, "
        "Clean=%s, "
        "Quarantine=%s, "
        "Excluded=%s, "
        "Failed=%s",
        counters["kept"],
        counters["dropped"],
        counters["clean"],
        counters["quarantine"],
        counters["excluded"],
        counters["failed"],
    )

    return {
        "records": output
    }