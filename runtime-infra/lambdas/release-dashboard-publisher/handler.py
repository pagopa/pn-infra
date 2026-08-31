import json
import logging
import os
from datetime import datetime, timedelta, timezone

import boto3

from athena import ENVIRONMENTS, build_query, query_results
from manifest import (
    MAX_MANIFEST_BYTES,
    SCHEMA_VERSION,
    format_timestamp,
    load_manifest,
    merge_records,
    parse_timestamp,
    put_manifest,
    sanitize_record,
)


LOGGER = logging.getLogger()
LOGGER.setLevel(logging.INFO)
S3_CLIENT = boto3.client("s3")
ATHENA_CLIENT = boto3.client("athena")


def lambda_handler(event, context):
    environment = os.environ["ENVIRONMENT"]
    if environment not in ENVIRONMENTS:
        raise ValueError("invalid configured environment")

    bucket = os.environ["DASHBOARD_BUCKET"]
    key = os.environ["MANIFEST_KEY"]
    database = os.environ["ATHENA_DATABASE"]
    table = os.environ["ATHENA_TABLE"]
    workgroup = os.environ["ATHENA_WORKGROUP"]
    retention_days = int(os.environ["RETENTION_DAYS"])
    overlap_hours = int(os.environ["OVERLAP_HOURS"])
    timeout_seconds = int(os.environ["QUERY_TIMEOUT_SECONDS"])
    query_end = datetime.now(timezone.utc).replace(microsecond=0)
    retention_cutoff = query_end - timedelta(days=retention_days)

    previous, etag = load_manifest(S3_CLIENT, bucket, key, MAX_MANIFEST_BYTES)
    existing = previous["records"] if previous else []
    if previous:
        if previous.get("environment") != environment:
            raise ValueError("manifest environment does not match publisher environment")
        source_data_through = parse_timestamp(previous.get("sourceDataThrough"))
        if source_data_through > query_end + timedelta(minutes=5):
            raise ValueError("manifest sourceDataThrough is in the future")
        query_start = max(retention_cutoff, source_data_through - timedelta(hours=overlap_hours))
    else:
        query_start = retention_cutoff

    query = build_query(database, table, environment, query_start, query_end)
    LOGGER.info(
        "Publishing release dashboard environment=%s from=%s through=%s",
        environment,
        format_timestamp(query_start),
        format_timestamp(query_end),
    )
    rows = query_results(ATHENA_CLIENT, query, database, workgroup, timeout_seconds)
    incoming = [record for row in rows if (record := sanitize_record(row, environment))]
    records = merge_records(existing, incoming, environment, retention_cutoff)

    manifest = {
        "schemaVersion": SCHEMA_VERSION,
        "environment": environment,
        "generatedAt": format_timestamp(datetime.now(timezone.utc)),
        "sourceDataThrough": format_timestamp(query_end),
        "records": records,
    }
    payload = json.dumps(manifest, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if len(payload) > MAX_MANIFEST_BYTES:
        raise ValueError(f"manifest exceeds size limit: {len(payload)} bytes")

    put_manifest(S3_CLIENT, bucket, key, payload, etag)
    LOGGER.info(
        "Release dashboard published environment=%s queried=%d retained=%d bytes=%d",
        environment,
        len(rows),
        len(records),
        len(payload),
    )
    return {"environment": environment, "records": len(records)}
