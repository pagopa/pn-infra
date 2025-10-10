# CDC Daily Count Lambda

Lambda function for generating daily CDC record counts to enable Data Lake reconciliation.

## Overview

The Lambda performs automated daily counts on Athena tables containing CDC (Change Data Capture) data from DynamoDB streams and other data sources. It generates a JSON report that the Data Lake team uses to validate quantitative consistency of ingested data.

The Lambda processes data for the previous day (T-1) in UTC timezone.

## Logic and Workflow

### Execution Flow

The Lambda orchestrates the following workflow:

1. **Reference Date Calculation**:
   - Calculates previous day (T-1) in UTC timezone
   - Formats date parameters for Athena partition filtering (YYYY, MM, DD)

2. **Configuration Retrieval**:
   - Loads custom query configurations using cascading source logic
   - Git repository (if `CONFIG_GIT_URL` is configured)
   - SSM Parameter Store (automatic fallback if Git URL is empty)
   - Default queries (if configuration source is empty)

3. **Table Processing**:
   - Parses comma-separated table list from environment variable
   - Verifies each table existence in Glue Catalog
   - Determines query type (custom or default) for each table
   - Executes Athena count query
   - Handles missing tables gracefully

4. **Parallel Execution**:
   - Processes up to 15 tables concurrently using ThreadPoolExecutor
   - Each table processing is independent
   - Collects all results regardless of individual failures

5. **Report Generation**:
   - Aggregates all counts into structured JSON
   - Adds execution timestamp to each table result
   - Includes status information for missing tables

6. **S3 Storage**:
   - Saves report to date-partitioned path
   - Format: `s3://{bucket}/datalake_counts/YYYY/MM/DD/counts.json`

### Configuration Source Logic

The Lambda uses a **cascading fallback strategy** for loading custom query configurations:

**Primary Source - Git Repository** (when `CONFIG_GIT_URL` is configured):
- Fetches configuration from specified Git raw content URL
- Supports branch/tag/commit selection via `CONFIG_GIT_REF`
- **If file not found**: Lambda fails with FileNotFoundError
- **If file is empty**: Uses default queries
- **If file contains valid JSON**: Uses custom queries

**Fallback Source - SSM Parameter Store** (when `CONFIG_GIT_URL` is empty or not set):
- Retrieves configuration from SSM parameter
- **If parameter not found**: Lambda fails with ParameterNotFound exception
- **If parameter is empty**: Uses default queries
- **If parameter contains valid JSON**: Uses custom queries

Configuration source logic:
```python
if CONFIG_GIT_URL:  # Non-empty string
    return fetch_config_from_git()
else:               # Empty string or not set
    return fetch_config_from_ssm()
```

### Configuration Source Behavior Matrix

| CONFIG_GIT_URL | Git File | SSM Parameter | Behavior |
|----------------|----------|---------------|----------|
| Empty | N/A | Contains JSON | Uses custom queries from SSM |
| Empty | N/A | Empty value | Uses default queries |
| Empty | N/A | Not found | Lambda fails |
| Configured | Exists + contains JSON | N/A | Uses custom queries from Git |
| Configured | Exists + empty | N/A | Uses default queries |
| Configured | Not found (404) | N/A | Lambda fails |

### Query Types

**Default Query**:
Standard count query for all CDC events on a specific date:
```sql
SELECT COUNT(*) as total_count 
FROM "database"."table_name" 
WHERE p_year = 'YYYY' 
  AND p_month = 'MM' 
  AND p_day = 'DD'
```

**Custom Query**:
Applies specific filters required by Data Lake to replicate exact ingestion conditions. Supports:
- Event type filtering (INSERT, MODIFY, REMOVE)
- Field-level filtering (e.g., exclude specific categories)
- Custom output table naming

Example custom configuration:
```json
{
  "pn_timelines": {
    "query_template": "SELECT COUNT(*) as total_count FROM {TABLE_NAME} WHERE p_year = '{YEAR}' AND p_month = '{MONTH}' AND p_day = '{DAY}' AND dynamodb.newimage.category.s <> 'VALIDATE_NORMALIZE_ADDRESSES_REQUEST' AND eventname = 'INSERT'",
    "output_table_name": "timeline"
  },
  "pn_mandate": {
    "query_template": "SELECT COUNT(*) as total_count FROM {TABLE_NAME} WHERE p_year = '{YEAR}' AND p_month = '{MONTH}' AND p_day = '{DAY}' AND eventname IN ('INSERT', 'MODIFY') AND dynamodb.newimage.pk.s <> 'DELEGHETRIGGERHELPER'",
    "output_table_name": "mandate"
  }
}
```

### Missing Table Handling

When a table does not exist in the Glue Catalog:
- Lambda continues processing (does not fail)
- Report includes table entry with `send_count: null` and `status: "NOT_FOUND"`
- Remaining tables are processed normally
- Final report includes all configured tables regardless of existence

## Lambda Functionality

### Handler (`process_daily_count`)

The main handler function orchestrates:

1. **Date Preparation**: Calculates T-1 date and prepares partition parameters
2. **Configuration Loading**: Calls `fetch_custom_queries()` with automatic fallback
3. **Table List Parsing**: Extracts and trims table names from comma-separated environment variable
4. **Parallel Processing**: Submits all table processing tasks to ThreadPoolExecutor
5. **Result Aggregation**: Collects counts from all completed futures
6. **Report Construction**: Builds JSON structure with execution timestamp
7. **S3 Output**: Saves final report to date-partitioned path

### Helper Functions

- **`fetch_custom_queries()`**: Implements cascading config source logic with automatic fallback
- **`fetch_config_from_git()`**: Retrieves configuration from Git repository using urllib
- **`fetch_config_from_ssm()`**: Retrieves configuration from SSM Parameter Store using boto3
- **`check_table_exists()`**: Verifies table presence in Glue Catalog
- **`execute_count_query()`**: Executes Athena query with polling until completion or failure
- **`build_default_query()`**: Constructs standard partition-based count query
- **`build_custom_query()`**: Builds query from template with parameter substitution
- **`process_table()`**: Orchestrates single table processing workflow
- **`save_report()`**: Writes JSON report to S3 with date-partitioned key path

## Environment Variables

### Core Configuration

- `TABLE_LIST`: Comma-separated list of Athena table names to process
- `OUTPUT_S3_BUCKET`: S3 bucket name for final count reports
- `ATHENA_RESULTS_BUCKET`: S3 bucket for Athena query execution results
- `ATHENA_DATABASE`: Glue Catalog database name
- `ATHENA_WORKGROUP`: Athena workgroup for query execution
- `MAX_WORKERS`: Maximum concurrent table processing threads (default: 15)

### Configuration Source

- `CONFIG_GIT_URL`: Git raw content URL (if empty or unset, uses SSM fallback)
- `CONFIG_GIT_REF`: Git reference, branch, or tag (default: 'main')
- `CONFIG_SSM_PARAMETER_NAME`: SSM parameter path for configuration fallback

## Output

### Report Location

`s3://{OUTPUT_S3_BUCKET}/datalake_counts/YYYY/MM/DD/counts.json`

### Report Structure

```json
{
  "tables": [
    {
      "table_name": "timeline",
      "send_count": 1329,
      "execution_timestamp": "2025-10-09T15:36:06.885000+00:00"
    },
    {
      "table_name": "user_attributes",
      "send_count": 542,
      "execution_timestamp": "2025-10-09T15:36:06.885000+00:00"
    },
    {
      "table_name": "paper_notifications_cost",
      "send_count": null,
      "status": "NOT_FOUND",
      "execution_timestamp": "2025-10-09T15:36:06.885000+00:00"
    }
  ]
}
```

## Testing

### Manual Invocation

The Lambda processes the previous day (T-1) data:

```bash
aws lambda invoke --function-name pn-CdcDailyCountLambda output.json
```

## Dependencies

The Lambda relies on the following Python libraries:

- **`boto3`**: Default library included in AWS Lambda Python runtime, used for AWS service interactions
- **`urllib`**: Python standard library for HTTP requests to Git repositories
- **`json`**: Python standard library for JSON processing
- **`concurrent.futures`**: Python standard library for parallel execution

No external dependencies or `requirements.txt` file required.