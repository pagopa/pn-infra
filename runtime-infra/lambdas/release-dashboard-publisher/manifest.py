import json
from datetime import datetime, timezone


SCHEMA_VERSION = 1
MAX_MANIFEST_BYTES = 5_000_000


def parse_timestamp(value):
    if not isinstance(value, str) or not value:
        raise ValueError("invalid timestamp")
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def format_timestamp(value):
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def clean_text(value, limit=256):
    if value in (None, ""):
        return None
    cleaned = " ".join(str(value).split())
    return cleaned[:limit] or None


def first(record, *names):
    for name in names:
        if record.get(name) not in (None, ""):
            return record[name]
    return None


def actor_from(value):
    value = clean_text(value, 512)
    if not value:
        return {"type": "unknown", "role": None}

    resource = value.split(":", 5)[-1]
    if resource.startswith("assumed-role/"):
        role = resource.split("/", 2)[1]
        if role.startswith("AWSReservedSSO_"):
            role = role.removeprefix("AWSReservedSSO_").rsplit("_", 1)[0]
            return {"type": "human", "role": clean_text(role, 128)}
        return {"type": "automation", "role": clean_text(role, 128)}

    if resource.startswith("user/"):
        return {"type": "human", "role": "IAMUser"}

    if resource.startswith("role/"):
        return {"type": "automation", "role": clean_text(resource.split("/", 1)[1], 128)}

    lowered = value.lower()
    if any(marker in lowered for marker in ("codebuild", "codepipeline", "eventbridge", "scheduler")):
        return {"type": "automation", "role": "PipelineTrigger"}

    return {"type": "unknown", "role": None}


def sanitize_record(record, environment):
    event_id = clean_text(first(record, "eventId", "event_id"), 128)
    timestamp_value = first(record, "timestamp")
    if not event_id or not timestamp_value:
        return None

    try:
        timestamp = format_timestamp(parse_timestamp(timestamp_value))
    except (TypeError, ValueError):
        return None

    record_environment = clean_text(first(record, "environment"), 16) or environment
    if record_environment.lower() != environment:
        return None

    start_timestamp = None
    raw_start_timestamp = first(record, "startTimestamp", "start_timestamp")
    if raw_start_timestamp:
        try:
            start_timestamp = format_timestamp(parse_timestamp(raw_start_timestamp))
        except (TypeError, ValueError):
            pass

    duration = first(record, "durationSeconds", "duration_seconds")
    try:
        duration = max(0, int(duration)) if duration not in (None, "") else None
    except (TypeError, ValueError):
        duration = None

    execution_user = record.get("executionUser")
    if isinstance(execution_user, dict):
        actor_type = execution_user.get("type")
        execution_user = {
            "type": actor_type if actor_type in {"human", "automation", "unknown"} else "unknown",
            "role": clean_text(execution_user.get("role"), 128),
        }
    else:
        execution_user = actor_from(record.get("execution_user"))

    status = clean_text(first(record, "status", "phase"), 32)
    source_system = clean_text(first(record, "sourceSystem", "source_system"), 16)

    return {
        "eventId": event_id,
        "timestamp": timestamp,
        "startTimestamp": start_timestamp,
        "durationSeconds": duration,
        "executionUser": execution_user,
        "project": clean_text(first(record, "project"), 128),
        "component": clean_text(first(record, "component"), 128),
        "environment": environment,
        "status": status.upper() if status else "UNKNOWN",
        "requestedVersion": clean_text(first(record, "requestedVersion", "requested_version"), 256),
        "commitId": clean_text(first(record, "commitId", "commit_id"), 128),
        "tag": clean_text(first(record, "tag"), 128),
        "configVersion": clean_text(first(record, "configVersion", "config_version"), 128),
        "infraVersion": clean_text(first(record, "infraVersion", "infra_version"), 128),
        "cicdVersion": clean_text(first(record, "cicdVersion", "cicd_version"), 128),
        "pipeline": clean_text(first(record, "pipeline", "pipeline_name"), 256),
        "pipelineExecutionId": clean_text(
            first(record, "pipelineExecutionId", "pipeline_execution_id"), 128
        ),
        "buildId": clean_text(first(record, "buildId", "build_id"), 256),
        "buildUrl": clean_text(first(record, "buildUrl", "build_url"), 2048),
        "releaseLabel": clean_text(first(record, "releaseLabel", "release_label"), 128),
        "errorMessage": clean_text(first(record, "errorMessage", "error_message"), 512),
        "sourceSystem": source_system.upper() if source_system else "UNKNOWN",
    }


def load_manifest(s3, bucket, key, max_bytes):
    try:
        response = s3.get_object(Bucket=bucket, Key=key)
    except s3.exceptions.NoSuchKey:
        return None, None

    if response.get("ContentLength", 0) > max_bytes:
        raise ValueError("existing manifest exceeds size limit")
    payload = response["Body"].read(max_bytes + 1)
    if len(payload) > max_bytes:
        raise ValueError("existing manifest exceeds size limit")

    manifest = json.loads(payload)
    if manifest.get("schemaVersion") != SCHEMA_VERSION:
        raise ValueError("unsupported manifest schema")
    if not isinstance(manifest.get("records"), list):
        raise ValueError("manifest records must be an array")
    return manifest, response.get("ETag")


def merge_records(existing, incoming, environment, cutoff):
    merged = {}
    for record in [*existing, *incoming]:
        sanitized = sanitize_record(record, environment)
        if sanitized and parse_timestamp(sanitized["timestamp"]) >= cutoff:
            merged[sanitized["eventId"]] = sanitized
    return sorted(merged.values(), key=lambda record: record["timestamp"], reverse=True)


def put_manifest(s3, bucket, key, payload, etag):
    request = {
        "Bucket": bucket,
        "Key": key,
        "Body": payload,
        "ContentType": "application/json",
        "CacheControl": "no-store",
    }
    request["IfMatch" if etag else "IfNoneMatch"] = etag or "*"
    s3.put_object(**request)
