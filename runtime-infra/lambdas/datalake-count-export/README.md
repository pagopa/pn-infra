# Data Lake Count Export Lambda

Lambda function for exporting daily data counts to enable Data Lake reconciliation and validation.

## Overview

The Lambda performs automated daily counts on Athena tables containing CDC (Change Data Capture) data from DynamoDB streams and incremental exports. It generates a JSON report that the Data Lake team uses to validate quantitative consistency of ingested data through end-to-end comparison (Solution 1: Athena-DL from requirements).

The Lambda processes data for the previous day (T-1) in UTC timezone.

## Logic and Workflow

### Execution Flow

1. **Logger Setup**: Configures custom log format required by CloudWatch metric filters for alarm integration
2. **Reference Date Calculation**: Determines T-1 date and formats partition parameters
3. **Configuration Retrieval**: Loads query configurations from Git repository (required)
4. **Table Processing**: Formats queries with date parameters and executes counts on Athena
5. **Parallel Execution**: Processes up to 15 tables concurrently using ThreadPoolExecutor
6. **Report Generation**: Aggregates counts with execution timestamp
7. **S3 Storage**: Saves report to date-partitioned path

### Configuration Source

**Git Repository** (required):
- Fetches JSON configuration from Git raw content URL
- File not found → Lambda fails (Git source is mandatory)
- File empty → Lambda fails (configuration must contain table definitions)
- Valid JSON → Uses queries from configuration

The configuration JSON defines:
- **JSON Key**: Report name for Data Lake (e.g., `notification`, `timeline`)
- **Query Value**: Complete SQL query with date placeholders `{YEAR}`, `{MONTH}`, `{DAY}`


```json
{
  "notification": {
    "query": "SELECT COUNT(*) FROM pn_notifications WHERE p_year = '{YEAR}' AND p_month = '{MONTH}' AND p_day = '{DAY}' AND eventname = 'INSERT'"
  },
  "timeline": {
    "query": "SELECT COUNT(*) FROM pn_timelines WHERE p_year = '{YEAR}' AND p_month = '{MONTH}' AND p_day = '{DAY}' AND eventname = 'INSERT' AND dynamodb.newimage.category.s <> 'VALIDATE_NORMALIZE_ADDRESSES_REQUEST'"
  }
}
```

### Report Name Mapping

Output report names are controlled entirely by the JSON configuration keys:
- **JSON Key**: `notification` → **Report Field**: `"table_name": "notification"`
- **JSON Key**: `timeline` → **Report Field**: `"table_name": "timeline"`
- **JSON Key**: `user_attributes` → **Report Field**: `"table_name": "user_attributes"`

This ensures output names match exactly what Data Lake expects for validation.

### Custom Logging

Custom log formatter required by CloudWatch metric filter alarm system:

**Format**: `timestamp aws_request_id level message`

This format ensures the metric filter pattern `[w1, w2, w3="ERROR", w4]` correctly detects errors at position 3, enabling automated Slack notifications via the alarm infrastructure.

## Environment Variables

### Core Configuration

- `CONFIG_GIT_URL`: Git raw content URL with embedded commit SHA or tag (required)
- `OUTPUT_S3_BUCKET`: Output bucket for reports
- `ATHENA_RESULTS_BUCKET`: Athena query results bucket
- `ATHENA_DATABASE`: Glue database name
- `ATHENA_WORKGROUP`: Athena workgroup
- `MAX_WORKERS`: Parallel execution limit (default: 15)

### Git Configuration

The Lambda expects a complete Git raw content URL with an embedded commit SHA or tag.

**Format**:
```
https://raw.githubusercontent.com/{org}/{repo}/{commit-sha-or-tag}/{path-to-file}
```

**Examples** (same repository):
```yaml
# Using commit SHA (deterministic)
CONFIG_GIT_URL: "https://raw.githubusercontent.com/pagopa/pn-infra/1234567890abcdef1234567890abcdef12345678/runtime-infra/datalake/ingestion-count-queries.json"

# Using tag (version)
CONFIG_GIT_URL: "https://raw.githubusercontent.com/pagopa/pn-infra/v1.0.0/runtime-infra/datalake/ingestion-count-queries.json"
```

**How to get commit SHA**:
1. GitHub UI: Navigate to commit page and copy full SHA from URL
2. Git CLI: Run `git rev-parse HEAD` on your branch
3. GitHub API: `curl -s https://api.github.com/repos/pagopa/pn-infra/branches/main | jq -r '.commit.sha'`

## Output

### Report Location

`s3://{OUTPUT_S3_BUCKET}/datalake_counts/YYYY/MM/DD/counts.json`

### Report Format

```json
{
  "tables": [
    {
      "table_name": "notification",
      "send_count": 1205,
      "execution_timestamp": "2025-10-13T15:36:06.885000+00:00"
    },
    {
      "table_name": "timeline",
      "send_count": 1329,
      "execution_timestamp": "2025-10-13T15:36:06.885000+00:00"
    },
    {
      "table_name": "mandate",
      "send_count": 89,
      "execution_timestamp": "2025-10-13T15:36:06.885000+00:00"
    },
    {
      "table_name": "user_attributes",
      "send_count": 542,
      "execution_timestamp": "2025-10-13T15:36:06.885000+00:00"
    },
    {
      "table_name": "radd",
      "send_count": 45,
      "execution_timestamp": "2025-10-13T15:36:06.885000+00:00"
    },
    {
      "table_name": "flusso_asseverazione",
      "send_count": 1876,
      "execution_timestamp": "2025-10-13T15:36:06.885000+00:00"
    }
  ]
}
```

Table names in the report correspond exactly to the JSON configuration keys, ensuring consistency with Data Lake expectations.

## Testing

Manual invocation (processes T-1 data):

```bash
aws lambda invoke --function-name pn-DataLakeCountExportLambda output.json
```

## Dependencies

- **`boto3`**: AWS SDK (included in Lambda runtime)
- **`urllib`**: HTTP client for Git config retrieval (Python standard library)
- **`json`**: JSON processing (Python standard library)
- **`concurrent.futures`**: Parallel execution (Python standard library)

No external dependencies required.

## Architecture Changes

### Version 2.0 (Current)

- **Configuration**: Git-only (no SSM fallback)
- **Table Discovery**: JSON keys define report names
- **Query Source**: Complete queries in configuration (no default queries)
- **Processing**: Direct iteration over JSON configuration
- **Removed**: Glue table existence checks, S3 location parsing, default query builder

### Benefits

- Simpler codebase (~70 lines removed)
- Deterministic output names (controlled by Data Lake)
- No Glue API dependencies
- Faster execution (no table metadata lookups)
- Clear configuration ownership