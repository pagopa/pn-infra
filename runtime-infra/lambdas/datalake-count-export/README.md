# Data Lake Count Export Lambda

Lambda function for exporting daily data counts to enable Data Lake reconciliation and validation.

## Overview

The Lambda performs automated daily counts on Athena tables containing CDC (Change Data Capture) data from DynamoDB streams and incremental exports. It generates a JSON report that the Data Lake team uses to validate quantitative consistency of ingested data through end-to-end comparison (Solution 1: Athena-DL from requirements).

The Lambda processes data for the previous day (T-1) in UTC timezone.

## Logic and Workflow

### Execution Flow

1. **Logger Setup**: Configures custom log format required by CloudWatch metric filters for alarm integration
2. **Reference Date Calculation**: Determines T-1 date and formats partition parameters
3. **Configuration Retrieval**: Loads custom query configurations with cascading fallback (Git → SSM → default)
4. **Table Processing**: Verifies existence, extracts source names from S3 locations, builds queries, executes counts
5. **Parallel Execution**: Processes up to 15 tables concurrently
6. **Report Generation**: Aggregates counts with execution timestamp
7. **S3 Storage**: Saves report to date-partitioned path

### Source Name Extraction

Table names in the output report correspond to the actual DynamoDB table names or S3 folder names, extracted automatically from Glue table locations:

**CDC Tables** (DynamoDB exports):
- Pattern: `s3://bucket/cdcTos3/TABLE_NAME_{DynamoDBName}/`
- Example: `TABLE_NAME_pn-Timelines/` → Output: `pn-Timelines`

**Incremental Exports**:
- Pattern: `s3://bucket/flussi/{folder_name}/`
- Example: `pad26_asseverazione/` → Output: `pad26_asseverazione`

This ensures output names match exactly with source data locations for clear traceability.

### Configuration Source Logic

**Primary - Git Repository** (when `CONFIG_GIT_URL` is configured):
- Fetches from Git raw content URL
- File not found → Lambda fails
- File empty → Uses default queries
- Valid JSON → Uses custom queries

**Fallback - SSM Parameter Store** (when `CONFIG_GIT_URL` is empty):
- Retrieves from SSM parameter
- Parameter not found → Lambda fails
- Parameter empty → Uses default queries
- Valid JSON → Uses custom queries

### Configuration Behavior Matrix

| CONFIG_GIT_URL | Config Status | Behavior |
|----------------|---------------|----------|
| Empty | SSM contains JSON | Uses SSM custom queries |
| Empty | SSM empty | Uses default queries |
| Empty | SSM not found | Lambda fails |
| Configured | Git file valid JSON | Uses Git custom queries |
| Configured | Git file empty | Uses default queries |
| Configured | Git file not found | Lambda fails |

### Query Types

**Default Query**: Counts all events for a specific date
```sql
SELECT COUNT(*) as total_count 
FROM "database"."table_name" 
WHERE p_year = 'YYYY' AND p_month = 'MM' AND p_day = 'DD'
```

**Custom Query**: Applies Data Lake ingestion filters for accurate comparison

Example:
```json
{
  "pn_timelines": {
    "query_template": "SELECT COUNT(*) FROM {TABLE_NAME} WHERE p_year = '{YEAR}' AND p_month = '{MONTH}' AND p_day = '{DAY}' AND dynamodb.newimage.category.s <> 'VALIDATE_NORMALIZE_ADDRESSES_REQUEST' AND eventname = 'INSERT'"
  }
}
```

### Custom Logging

Custom log formatter required by CloudWatch metric filter alarm system:

**Format**: `timestamp aws_request_id level message`

This format ensures the metric filter pattern `[w1, w2, w3="ERROR", w4]` correctly detects errors at position 3, enabling automated Slack notifications via the alarm infrastructure.

## Environment Variables

### Core Configuration

- `TABLE_LIST`: Comma-separated Athena table names
- `OUTPUT_S3_BUCKET`: Output bucket for reports
- `ATHENA_RESULTS_BUCKET`: Athena query results bucket
- `ATHENA_DATABASE`: Glue database name
- `ATHENA_WORKGROUP`: Athena workgroup
- `MAX_WORKERS`: Parallel execution limit (default: 15)

### Configuration Source

- `CONFIG_GIT_URL`: Git raw URL (if empty, uses SSM)
- `CONFIG_GIT_REF`: Git ref/branch/tag (default: 'main')
- `CONFIG_SSM_PARAMETER_NAME`: SSM parameter path

## Output

### Report Location

`s3://{OUTPUT_S3_BUCKET}/datalake_counts/YYYY/MM/DD/counts.json`

### Report Format

```json
{
  "tables": [
    {
      "table_name": "pn-Timelines",
      "send_count": 1329,
      "execution_timestamp": "2025-10-09T15:36:06.885000+00:00"
    },
    {
      "table_name": "pn-UserAttributes",
      "send_count": 542,
      "execution_timestamp": "2025-10-09T15:36:06.885000+00:00"
    },
    {
      "table_name": "pad26_asseverazione",
      "send_count": 1876,
      "execution_timestamp": "2025-10-09T15:36:06.885000+00:00"
    }
  ]
}
```

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
- **`re`**: Regular expressions for name extraction (Python standard library)

No external dependencies required.