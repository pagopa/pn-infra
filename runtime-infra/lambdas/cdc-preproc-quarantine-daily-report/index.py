import json
import os
from datetime import datetime, timedelta, timezone

import boto3
from botocore.config import Config

from reporting import publish_warning_report


QUARANTINE_PREFIX = "cdcTos3/cdc-preproc/quarantine/"
REPORT_PREFIX = "reporting/cdcTos3/cdc-preproc/quarantine/"
TABLE_FOLDER_PREFIX = "TABLE_NAME_"

REPORT_PRODUCER = "pn-cdc-quarantine-daily-report"
REPORT_EVENT_NAME = "cdc-quarantine-daily-report"
REPORT_TITLE = "CDC Preproc quarantine daily report"

S3_BUCKET = os.environ["S3_BUCKET"]
ENVIRONMENT = os.environ["ENVIRONMENT"]
SNS_TOPIC_ARN = os.environ.get("SNS_TOPIC_ARN", "")
AWS_REGION = os.environ.get("AWS_REGION", "eu-south-1")
REPORT_NOTIFICATIONS_ENABLED = (
    os.environ.get("REPORT_NOTIFICATIONS_ENABLED", "false").lower() == "true"
)

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


def _write_daily_records(
    day_prefix,
    csv_file,
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

                csv_file.write(line)
                csv_file.write(b"\n")

                record_count += 1

    return record_count


def lambda_handler(event, context):
    now = datetime.now(timezone.utc)

    # The report processes the complete previous UTC day.
    reference_datetime = now - timedelta(days=1)

    reference_date = reference_datetime.strftime("%Y-%m-%d")
    day_path = reference_datetime.strftime("%Y/%m/%d/")
    generation_time = now.strftime("%Y%m%dT%H%M%SZ")

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

    # Read all records from the reference day and write them
    # progressively to /tmp to avoid keeping the entire daily
    # dataset in Lambda memory.
    with open(csv_path, "wb") as csv_file:
        for folder in folders:
            table_name = _extract_table_name(folder)
            day_prefix = f"{folder}{day_path}"

            record_count = _write_daily_records(
                day_prefix,
                csv_file,
            )

            # Tables without quarantine records for the
            # reference day are excluded from the report.
            if record_count == 0:
                continue

            tables.append(
                {
                    "tableName": table_name,
                    "recordCount": record_count,
                }
            )

    tables.sort(
        key=lambda table: table["tableName"]
    )

    total_records = sum(
        table["recordCount"]
        for table in tables
    )

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

    # Store the original quarantine records.
    s3.upload_file(
        csv_path,
        S3_BUCKET,
        csv_report_key,
        ExtraArgs={
            "ContentType": "text/csv",
        },
    )

    csv_size = os.path.getsize(csv_path)

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
            attachment={
                "bucket": S3_BUCKET,
                "key": csv_report_key,
                "filename": csv_filename,
                "size": csv_size,
            },
        )

    return {
        "status": "ok",
        "referenceDate": reference_date,
        "tablesCount": len(tables),
        "recordCount": total_records,
        "jsonReportKey": json_report_key,
        "csvReportKey": csv_report_key,
    }