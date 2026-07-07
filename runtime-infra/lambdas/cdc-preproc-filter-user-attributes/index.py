import base64
import json
import os
from datetime import datetime

TARGET_TABLE_NAME = os.environ.get("TARGET_TABLE_NAME", "pn-UserAttributes")
ENVIRONMENT = os.environ.get("ENVIRONMENT", "Missing")

print(f"Initialization complete. TARGET_TABLE_NAME={TARGET_TABLE_NAME}, ENVIRONMENT={ENVIRONMENT}")


def get_ddb_value(image, field_name):
    field = image.get(field_name)
    if not field:
        return None

    if "S" in field:
        return field["S"]
    if "BOOL" in field:
        return field["BOOL"]
    if "N" in field:
        return field["N"]

    return None


def get_dynamodb_image(payload):
    dynamodb = payload.get("dynamodb", {})

    if dynamodb.get("NewImage"):
        return dynamodb.get("NewImage"), "NewImage"

    if dynamodb.get("OldImage"):
        return dynamodb.get("OldImage"), "OldImage"

    if dynamodb.get("Keys"):
        return dynamodb.get("Keys"), "Keys"

    return {}, "Missing"


def is_excluded_record(pk):
    if not pk:
        return False

    return pk.startswith(("VA#", "VC#"))


def remove_ddb_fields(payload, field_names):
    dynamodb = payload.get("dynamodb", {})

    for image_name in ("NewImage", "OldImage"):
        image = dynamodb.get(image_name)

        if isinstance(image, dict):
            for field_name in field_names:
                image.pop(field_name, None)


def run_dq_checks(payload):
    image, image_source = get_dynamodb_image(payload)

    pk = get_ddb_value(image, "pk")
    sk = get_ddb_value(image, "sk")
    created = get_ddb_value(image, "created")
    last_modified = get_ddb_value(image, "lastModified")
    addresshash = get_ddb_value(image, "addresshash") or get_ddb_value(image, "addressHash")
    accepted = get_ddb_value(image, "accepted")

    dq_errors = []

    # DQ1 - controlla i campi minimi richiesti dal data contract.
    if not pk or not sk or not created or not last_modified:
        dq_errors.append("DQ_REQUIRED_FIELDS")

    # DQ2 - accetta solo entità UserAttributes importabili: recapiti AB# o consensi CO#.
    if pk and not (pk.startswith("AB#") or pk.startswith("CO#")):
        dq_errors.append("DQ_ALLOWED_PK_PREFIX")

    # DQ3 - controlla le regole di dominio per recapiti e consensi.
    if pk and pk.startswith("AB#"):
        is_legal = sk and sk.startswith("LEGAL#")
        is_courtesy = sk and sk.startswith("COURTESY#")

        if not is_legal and not is_courtesy:
            dq_errors.append("DQ_BUSINESS_RULES")
        elif not addresshash:
            dq_errors.append("DQ_BUSINESS_RULES")
        elif is_legal and not (sk.endswith("#PEC") or sk.endswith("#SERCQ")):
            dq_errors.append("DQ_BUSINESS_RULES")
        elif is_courtesy and not (sk.endswith("#SMS") or sk.endswith("#EMAIL") or sk.endswith("#APPIO")):
            dq_errors.append("DQ_BUSINESS_RULES")
        elif is_courtesy and sk.endswith("#APPIO") and addresshash not in ("ENABLED", "DISABLED"):
            dq_errors.append("DQ_BUSINESS_RULES")

    if pk and pk.startswith("CO#"):
        if not sk or not (sk.startswith("TOS#") or sk.startswith("DATAPRIVACY#")):
            dq_errors.append("DQ_BUSINESS_RULES")
        elif accepted is None:
            dq_errors.append("DQ_BUSINESS_RULES")

    return dq_errors, image_source


def lambda_handler(event, context):
    records = event.get("records", [])
    print(f"Starting Firehose preprocessing Lambda. Processing {len(records)} records.")

    output = []
    kept_records = 0
    dropped_records = 0
    clean_records = 0
    quarantine_records = 0
    excluded_records = 0
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

                image, image_source = get_dynamodb_image(payload)
                pk = get_ddb_value(image, "pk")

                if is_excluded_record(pk):
                    processing_layer = "excluded"
                    excluded_records += 1
                    print(
                        f"Record excluded for Firehose recordId={record_id}. "
                        f"PK={pk}, ImageSource={image_source}"
                    )
                else:
                    dq_errors, image_source = run_dq_checks(payload)

                    if len(dq_errors) == 0:
                        processing_layer = "clean"
                        clean_records += 1
                    else:
                        processing_layer = "quarantine"
                        quarantine_records += 1
                        print(
                            f"DQ failed for Firehose recordId={record_id}. "
                            f"ImageSource={image_source}, Errors={dq_errors}"
                        )

            else:
                result = "Dropped"
                dropped_records += 1
                processing_layer = "dropped"

            if result == "Ok":
                remove_ddb_fields(payload, ("addresshash", "addressHash"))

                output_data = base64.b64encode(
                    json.dumps(payload, separators=(",", ":")).encode("utf-8")
                ).decode("utf-8")
            else:
                output_data = data

            output.append({
                "recordId": record_id,
                "result": result,
                "data": output_data,
                "metadata": {
                    "partitionKeys": {
                        "TABLE_NAME": table_name or "UNKNOWN",
                        "PROCESSING_LAYER": processing_layer
                    }
                }
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
        f"Kept={kept_records}, Dropped={dropped_records}, "
        f"Clean={clean_records}, Quarantine={quarantine_records}, "
        f"Excluded={excluded_records}, Failed={failed_records}"
    )

    return {
        "records": output
    }