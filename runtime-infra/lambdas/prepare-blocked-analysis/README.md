# Prepare Blocked Analysis Lambda

Lambda function for executing scheduled Athena queries to identify blocked PREPARE_ANALOG_DOMICILE events and cross-reference with DynamoDB errors.

**Handler**: `prepare_blocked_analysis_handler.lambda_handler`

## Overview

Downloads the pn-troubleshooting repository, executes the prepare_blocked_analisys.py script which:
- Queries Athena for PREPARE_ANALOG_DOMICILE timeline events
- Cross-references with pn-PaperRequestError DynamoDB table
- Exports results to CSV format
- Uploads results to S3

## Architecture

```
EventBridge Schedule → Lambda → Download Repo → Execute Script → Athena Query → Export CSV → S3
```

## Environment Variables

- `Region`: AWS region (required)
- `AthenaDatabase`: Glue database name (default: `cdc_analytics_database`)
- `AthenaTable`: Table name (default: `pn_timelines_json_view`)
- `AthenaWorkgroup`: Athena workgroup (default: `primary`)
- `S3ResultBucket`: S3 path for result files (required)
- `AthenaResultsBucket`: Athena query results bucket (required)
- `RepoZipUrl`: GitHub ZIP URL for pn-troubleshooting repository (required)

## Execution Flow

1. Triggered by EventBridge Schedule (default: daily at 07:00 UTC)
2. Downloads pn-troubleshooting repository from GitHub
3. Extracts and locates prepare_blocked_analisys.py script
4. Executes script with configured parameters
5. Handles timeout gracefully (saves partial progress)
6. Uploads all result files to S3

## Error Handling

- Downloads and extraction errors are logged with ERROR prefix
- Script execution failures are caught and logged
- Timeout (exit code 2) is handled gracefully with partial result upload
- All errors trigger CloudWatch alarms via metric filter

## CSV Export Structure

```
s3://{S3ResultBucket}/prepare-blocked-analysis/{filename}
```

Example:
```
s3://pn-datamonitoring-eu-south-1-830192246553/prepare-blocked-analysis/blocked-analysis-2025-01-09.csv
```
