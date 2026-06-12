import base64
import json
import os
from datetime import datetime

TARGET_TABLE_NAME = os.environ.get("TARGET_TABLE_NAME", "pn-UserAttributes")
ENVIRONMENT = os.environ.get("ENVIRONMENT", "Missing")

print(f"Initialization complete. TARGET_TABLE_NAME={TARGET_TABLE_NAME}, ENVIRONMENT={ENVIRONMENT}")


def lambda_handler(event, context):
    records = event.get("records", [])
    print(f"Starting Firehose preprocessing Lambda. Processing {len(records)} records.")

    output = []
    kept_records = 0
    dropped_records = 0
    failed_records = 0

    for record in records:
        record_id = record.get("recordId")
        data = record.get("data")

        try:
            payload_str = base64.b64decode(data).decode("utf-8")
            payload = json.loads(payload_str)

            table_name = payload.get("tableName")

            if table_name == TARGET_TABLE_NAME:
                result = "Ok"
                kept_records += 1
            else:
                result = "Dropped"
                dropped_records += 1

            output.append({
                "recordId": record_id,
                "result": result,
                "data": data
            })

        except Exception as e:
            failed_records += 1
            print(f"Error processing Firehose recordId={record_id}: {str(e)}")

            output.append({
                "recordId": record_id,
                "result": "ProcessingFailed",
                "data": data
            })

    print(
        f"Batch processed at {datetime.utcnow().isoformat()}. "
        f"Kept={kept_records}, Dropped={dropped_records}, Failed={failed_records}"
    )

    return {
        "records": output
    }