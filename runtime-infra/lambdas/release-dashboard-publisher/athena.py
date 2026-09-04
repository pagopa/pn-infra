import re
import time
from datetime import timedelta, timezone

from manifest import format_timestamp


ENVIRONMENTS = {"dev", "test", "uat", "hotfix", "prod"}
IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z0-9_]+$")


def partition_predicate(start, end):
    start = start.astimezone(timezone.utc)
    end = end.astimezone(timezone.utc)
    if start > end:
        raise ValueError("invalid query interval")

    days_by_month = {}
    current_day = start.date()
    while current_day <= end.date():
        days_by_month.setdefault((current_day.year, current_day.month), []).append(current_day.day)
        current_day += timedelta(days=1)

    clauses = []
    for (year, month), days in days_by_month.items():
        day_values = ", ".join(f"'{day:02d}'" for day in days)
        clauses.append(
            f"(p_year = '{year}' AND p_month = '{month:02d}' AND p_day IN ({day_values}))"
        )

    hour_values = ", ".join(f"'{hour:02d}'" for hour in range(24))
    return f"({' OR '.join(clauses)})\n  AND p_hour IN ({hour_values})"


def build_query(database, table, environment, start, end):
    if environment not in ENVIRONMENTS:
        raise ValueError("invalid environment")
    if not IDENTIFIER_PATTERN.fullmatch(database) or not IDENTIFIER_PATTERN.fullmatch(table):
        raise ValueError("invalid Athena identifier")

    start_timestamp = format_timestamp(start)
    end_timestamp = format_timestamp(end)
    partitions = partition_predicate(start, end)

    return f'''SELECT
  event_id, timestamp, start_timestamp, duration_seconds, execution_user,
  project, component, environment, phase, requested_version, commit_id, tag,
  config_version, infra_version, cicd_version, pipeline_name,
  pipeline_execution_id, build_id, build_url, release_label, error_message,
  source_system
FROM "{database}"."{table}"
WHERE {partitions}
  AND environment = '{environment}'
  AND TRY(from_iso8601_timestamp(timestamp)) BETWEEN
    from_iso8601_timestamp('{start_timestamp}') AND from_iso8601_timestamp('{end_timestamp}')'''


def query_results(athena, query, database, workgroup, timeout_seconds):
    execution_id = athena.start_query_execution(
        QueryString=query,
        QueryExecutionContext={"Database": database},
        WorkGroup=workgroup,
    )["QueryExecutionId"]

    started = time.monotonic()
    while True:
        execution = athena.get_query_execution(QueryExecutionId=execution_id)["QueryExecution"]
        state = execution["Status"]["State"]
        if state in {"SUCCEEDED", "FAILED", "CANCELLED"}:
            break
        if time.monotonic() - started >= timeout_seconds:
            athena.stop_query_execution(QueryExecutionId=execution_id)
            raise TimeoutError(f"Athena query {execution_id} timed out")
        time.sleep(2)

    if state != "SUCCEEDED":
        reason = execution["Status"].get("StateChangeReason", "unknown")
        raise RuntimeError(f"Athena query {execution_id} ended in {state}: {reason}")

    rows = []
    next_token = None
    first_page = True
    while True:
        request = {"QueryExecutionId": execution_id}
        if next_token:
            request["NextToken"] = next_token
        response = athena.get_query_results(**request)
        result_set = response["ResultSet"]
        columns = [column["Name"] for column in result_set["ResultSetMetadata"]["ColumnInfo"]]
        page_rows = result_set.get("Rows", [])
        if first_page and page_rows:
            page_rows = page_rows[1:]
        first_page = False

        for row in page_rows:
            data = row.get("Data", [])
            rows.append({
                column: data[index].get("VarCharValue", "") if index < len(data) else ""
                for index, column in enumerate(columns)
            })

        next_token = response.get("NextToken")
        if not next_token:
            return rows
