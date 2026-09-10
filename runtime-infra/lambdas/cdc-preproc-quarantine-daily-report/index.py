import json
import os
from datetime import datetime, timedelta, timezone

import boto3
from botocore.config import Config

from reporting import publish_warning_report


QUARANTINE_PREFIX = "cdcTos3/cdc-preproc/quarantine/"
REPORT_PREFIX = QUARANTINE_PREFIX + "report/"
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
        s3={"addressing_style": "virtual"}
    ),
)

sns = boto3.client("sns")


def _is_table_folder(prefix):
    folder_name = prefix[len(QUARANTINE_PREFIX):].rstrip("/")
    return folder_name.startswith(TABLE_FOLDER_PREFIX)


def _count_partition_files(partition_prefix):
    paginator = s3.get_paginator("list_objects_v2")

    return sum(
        1
        for page in paginator.paginate(
            Bucket=S3_BUCKET,
            Prefix=partition_prefix,
        )
        for obj in page.get("Contents", [])
        if obj.get("Size", 0) > 0
    )


def lambda_handler(event, context):
    now = datetime.now(timezone.utc)

    # The report processes the complete partitioning of the previous UTC day.
    reference_datetime = now - timedelta(days=1)

    reference_date = reference_datetime.strftime("%Y-%m-%d")
    day_path = reference_datetime.strftime("%Y/%m/%d/")
    generation_time = now.strftime("%Y%m%dT%H%M%SZ")

    paginator = s3.get_paginator("list_objects_v2")

    # Retrieve all quarantine folders associated with CDC tables.
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

    tables = []

    for folder in folders:
        table_name = (
            folder[len(QUARANTINE_PREFIX):]
            .rstrip("/")[len(TABLE_FOLDER_PREFIX):]
        )

        day_prefix = f"{folder}{day_path}"

        # Retrieve the hourly partitions available for the reference day.
        partition_prefixes = [
            item["Prefix"]
            for page in paginator.paginate(
                Bucket=S3_BUCKET,
                Prefix=day_prefix,
                Delimiter="/",
            )
            for item in page.get("CommonPrefixes", [])
        ]

        partitions = {}

        for partition_prefix in partition_prefixes:
            # Example:
            # 2026/08/13/09
            partition_path = (
                partition_prefix[len(folder):]
                .rstrip("/")
            )

            files_count = _count_partition_files(
                partition_prefix
            )

            if files_count > 0:
                partitions[partition_path] = files_count

        if not partitions:
            continue

        partitions = dict(
            sorted(partitions.items())
        )

        tables.append(
            {
                "tableName": table_name,
                "partitions": partitions,
            }
        )

    tables.sort(
        key=lambda table: table["tableName"]
    )

    total_files = sum(
        sum(table["partitions"].values())
        for table in tables
    )

    report = {
        "generatedAt": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "referenceDate": reference_date,
        "tables": tables,
    }

    if not tables:
        report["message"] = "No tables found in quarantine"

    report_key = (
        f"{REPORT_PREFIX}"
        f"report_quarantine_"
        f"{reference_date}_"
        f"{generation_time}.json"
    )

    report_bytes = json.dumps(
        report,
        ensure_ascii=False,
        indent=2,
    ).encode("utf-8")

    s3.put_object(
        Bucket=S3_BUCKET,
        Key=report_key,
        Body=report_bytes,
        ContentType="application/json",
    )

    if REPORT_NOTIFICATIONS_ENABLED and SNS_TOPIC_ARN:
        metrics = {
            "Reference date": reference_date,
            "Tables in quarantine": len(tables),
            "Files in quarantine": total_files,
        }

        if tables:
            details = {
                table["tableName"]: sum(
                    table["partitions"].values()
                )
                for table in tables
            }
        else:
            details = {
                "Result": "No tables found in quarantine"
            }

        publish_warning_report(
            sns_client=sns,
            topic_arn=SNS_TOPIC_ARN,
            event_id=context.aws_request_id,
            producer=REPORT_PRODUCER,
            event_name=REPORT_EVENT_NAME,
            occurred_at=now,
            environment=ENVIRONMENT,
            title=REPORT_TITLE,
            metrics=metrics,
            details=details,
            links={
                "report": f"s3://{S3_BUCKET}/{report_key}"
            },
        )

    return {
        "status": "ok",
        "referenceDate": reference_date,
        "tablesCount": len(tables),
        "filesCount": total_files,
        "reportKey": report_key,
    }