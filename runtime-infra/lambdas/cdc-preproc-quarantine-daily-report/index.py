import csv
import json
import os
from datetime import datetime, timedelta, timezone

import boto3
from botocore.config import Config

from config import logger, setup_logger
from reporting import publish_warning_report


QUARANTINE_PREFIX = os.environ["QUARANTINE_PREFIX"]
REPORT_PREFIX = os.environ["REPORT_PREFIX"]
TABLE_FOLDER_PREFIX = os.environ["TABLE_FOLDER_PREFIX"]

REPORT_PRODUCER = os.environ["REPORT_PRODUCER"]
REPORT_EVENT_NAME = os.environ["REPORT_EVENT_NAME"]
REPORT_TITLE = os.environ["REPORT_TITLE"]

S3_BUCKET = os.environ["S3_BUCKET"]
ENVIRONMENT = os.environ["ENVIRONMENT"]
SNS_TOPIC_ARN = os.environ.get("SNS_TOPIC_ARN", "")
AWS_REGION = os.environ.get("AWS_REGION", "eu-south-1")
REPORT_NOTIFICATIONS_ENABLED = (
    os.environ.get("REPORT_NOTIFICATIONS_ENABLED", "false").lower() == "true"
)

CSV_HEADER = [
    "awsRegion",
    "eventID",
    "eventName",
    "tableName",
    "recordFormat",
    "eventSource",
    "approximateCreationDateTime",
    "keys",
    "newImage",
    "oldImage",
    "sizeBytes",
]

s3 = boto3.client(
    "s3",
    region_name=AWS_REGION,
    config=Config(
        signature_version="s3v4",
        s3={"addressing_style": "virtual"},
    ),
)

sns = boto3.client("sns")


def _is_table_folder(prefix):
    folder_name = prefix[len(QUARANTINE_PREFIX):].rstrip("/")
    return folder_name.startswith(TABLE_FOLDER_PREFIX)


def _extract_table_name(folder):
    return (
        folder[len(QUARANTINE_PREFIX):]
        .rstrip("/")[len(TABLE_FOLDER_PREFIX):]
    )


def _write_csv_record(
    csv_writer,
    record,
):
    dynamodb = record.get("dynamodb", {})

    csv_writer.writerow(
        [
            record.get("awsRegion", ""),
            record.get("eventID", ""),
            record.get("eventName", ""),
            record.get("tableName", ""),
            record.get("recordFormat", ""),
            record.get("eventSource", ""),
            dynamodb.get(
                "ApproximateCreationDateTime",
                "",
            ),
            json.dumps(
                dynamodb.get("Keys", {}),
                ensure_ascii=False,
                separators=(",", ":"),
            ),
            json.dumps(
                dynamodb.get("NewImage", {}),
                ensure_ascii=False,
                separators=(",", ":"),
            ),
            json.dumps(
                dynamodb.get("OldImage", {}),
                ensure_ascii=False,
                separators=(",", ":"),
            ),
            dynamodb.get("SizeBytes", ""),
        ]
    )


def _write_daily_records(
    day_prefix,
    csv_writer,
):
    paginator = s3.get_paginator("list_objects_v2")

    record_count = 0

    for page in paginator.paginate(
        Bucket=S3_BUCKET,
        Prefix=day_prefix,
    ):
        for obj in page.get("Contents", []):
            if obj.get("Size", 0) <= 0:
                continue

            response = s3.get_object(
                Bucket=S3_BUCKET,
                Key=obj["Key"],
            )

            for line in response["Body"].iter_lines():
                if not line.strip():
                    continue

                record = json.loads(
                    line.decode("utf-8")
                )

                _write_csv_record(
                    csv_writer,
                    record,
                )

                record_count += 1

    return record_count


def lambda_handler(event, context):
    setup_logger(context.aws_request_id)

    try:
        return _generate_report(
            event,
            context,
        )

    except Exception as error:
        logger.exception(
            "QUARANTINE_REPORT_FAILED "
            "Technical error during report generation.\n"
            "ErrorType=%s, Error=%s",
            type(error).__name__,
            str(error),
        )

        raise


def _generate_report(event, context):
    now = datetime.now(timezone.utc)

    # The report processes the complete previous UTC day.
    reference_datetime = now - timedelta(days=1)

    reference_date = reference_datetime.strftime("%Y-%m-%d")
    day_path = reference_datetime.strftime("%Y/%m/%d/")
    generation_time = now.strftime("%Y%m%dT%H%M%SZ")

    logger.info(
        "Starting CDC quarantine daily report. "
        "ReferenceDate=%s, Environment=%s",
        reference_date,
        ENVIRONMENT,
    )

    paginator = s3.get_paginator("list_objects_v2")

    # Retrieve all CDC table folders available under quarantine.
    folders = [
        item["Prefix"]
        for page in paginator.paginate(
            Bucket=S3_BUCKET,
            Prefix=QUARANTINE_PREFIX,
            Delimiter="/",
        )
        for item in page.get("CommonPrefixes", [])
        if _is_table_folder(item["Prefix"])
    ]

    logger.info(
        "Quarantine table folders discovered. "
        "DiscoveredTables=%s, Tables=%s",
        len(folders),
        ", ".join(
            _extract_table_name(folder)
            for folder in folders
        ) or "none",
    )

    report_base_filename = (
        f"report_quarantine_"
        f"{reference_date}_"
        f"{generation_time}"
    )

    json_filename = f"{report_base_filename}.json"
    csv_filename = f"{report_base_filename}.csv"

    # Reports are partitioned using the reference date:
    # reporting/cdcTos3/cdc-preproc/quarantine/YYYY/MM/DD/
    report_day_prefix = (
        f"{REPORT_PREFIX}"
        f"{day_path}"
    )

    json_report_key = (
        f"{report_day_prefix}"
        f"{json_filename}"
    )

    csv_report_key = (
        f"{report_day_prefix}"
        f"{csv_filename}"
    )

    csv_path = f"/tmp/{csv_filename}"

    tables = []
    csv_file = None
    csv_writer = None

    try:
        for folder in folders:
            table_name = _extract_table_name(folder)
            day_prefix = f"{folder}{day_path}"

            # Open the CSV only when processing starts.
            # The file is removed later if no records are found.
            if csv_file is None:
                csv_file = open(
                    csv_path,
                    "w",
                    newline="",
                    encoding="utf-8",
                )

                csv_writer = csv.writer(csv_file)
                csv_writer.writerow(CSV_HEADER)

            record_count = _write_daily_records(
                day_prefix,
                csv_writer,
            )

            # Tables without quarantine records for the
            # reference day are excluded from the report.
            if record_count == 0:
                logger.info(
                    "NO quarantine records found for table: "
                    "TableName=%s, ReferenceDate=%s",
                    table_name,
                    reference_date,
                )
                continue

            tables.append(
                {
                    "tableName": table_name,
                    "recordCount": record_count,
                }
            )

            logger.info(
                "Quarantine records found for table: "
                "TableName=%s, "
                "RecordCount=%s, "
                "ReferenceDate=%s",
                table_name,
                record_count,
                reference_date,
            )

    finally:
        if csv_file is not None:
            csv_file.close()

    tables.sort(
        key=lambda table: table["tableName"]
    )

    total_records = sum(
        table["recordCount"]
        for table in tables
    )

    # Remove the temporary CSV when no records were found.
    if total_records == 0 and os.path.exists(csv_path):
        os.remove(csv_path)

    report = {
        "generatedAt": now.strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        ),
        "referenceDate": reference_date,
        "tables": tables,
    }

    json_report_bytes = (
        json.dumps(
            report,
            ensure_ascii=False,
            indent=2,
        ) + "\n"
    ).encode("utf-8")

    # Store the JSON summary.
    s3.put_object(
        Bucket=S3_BUCKET,
        Key=json_report_key,
        Body=json_report_bytes,
        ContentType="application/json",
    )

    attachment = None

    if total_records > 0:
        # Store the tabular CSV only when the reference day
        # contains quarantine records.
        s3.upload_file(
            csv_path,
            S3_BUCKET,
            csv_report_key,
            ExtraArgs={
                "ContentType": "text/csv",
            },
        )

        csv_size = os.path.getsize(csv_path)

        attachment = {
            "bucket": S3_BUCKET,
            "key": csv_report_key,
            "filename": csv_filename,
            "size": csv_size,
        }

        logger.info(
            "Quarantine reports stored in S3. "
            "ReferenceDate=%s, "
            "TablesWithQuarantine=%s, "
            "Records=%s, "
            "CsvSizeBytes=%s\n"
            "CSV report generated successfully! You can find it at:\n"
            "CsvReportPath=s3://%s/%s",
            reference_date,
            len(tables),
            total_records,
            csv_size,
            S3_BUCKET,
            csv_report_key,
        )

    else:
        logger.info(
            "NO quarantine records found for the reference date. "
            "ReferenceDate=%s.\n"
            "Attention! Only the JSON report was generated with no CSV attachment.\n"
            "JsonReportPath=s3://%s/%s",
            reference_date,
            S3_BUCKET,
            json_report_key,
        )

    # Publish the application report only when notifications
    # are explicitly enabled.
    if REPORT_NOTIFICATIONS_ENABLED and SNS_TOPIC_ARN:
        metrics = {
            "Reference date": reference_date,
            "Tables in quarantine": len(tables),
            "Records in quarantine": total_records,
        }

        details = {
            table["tableName"]: table["recordCount"]
            for table in tables
        }

        publish_warning_report(
            sns_client=sns,
            s3_client=s3,
            topic_arn=SNS_TOPIC_ARN,
            event_id=context.aws_request_id,
            producer=REPORT_PRODUCER,
            event_name=REPORT_EVENT_NAME,
            occurred_at=now,
            environment=ENVIRONMENT,
            title=REPORT_TITLE,
            metrics=metrics,
            details=details,
            links={},
            attachment=attachment,
        )

        logger.info(
            "Quarantine report notification published successfully! "
            "Producer=%s, CsvAttachmentIncluded=%s",
            REPORT_PRODUCER,
            attachment is not None,
        )

    logger.info(
        "CDC quarantine daily report completed successfully! "
        "ReferenceDate=%s, "
        "DiscoveredTables=%s, "
        "TablesWithQuarantine=%s, "
        "Records=%s",
        reference_date,
        len(folders),
        len(tables),
        total_records,
    )

    return {
        "status": "ok",
        "referenceDate": reference_date,
        "tablesCount": len(tables),
        "recordCount": total_records,
        "jsonReportKey": json_report_key,
        "csvReportKey": (
            csv_report_key
            if total_records > 0
            else None
        ),
    }