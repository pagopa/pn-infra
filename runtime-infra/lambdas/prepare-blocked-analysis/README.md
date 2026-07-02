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
- `CloudWatchNamespace`: CloudWatch namespace for published metrics
- `MetricNameTotalOpenCases` / `MetricNameResolvedInLastRun` / `MetricNameNewInLastRun` / `MetricNameAffectedPrepare`: CloudWatch metric names
- `DeliveryMonitoringSnsTopicArn`: SNS topic ARN used to send the weekly email report (optional; if empty the report is skipped)
- `EnvironmentType`: environment name, used only in the weekly report subject (optional)

## Weekly report (email alerting)

Every Monday the handler publishes a weekly report to the `DeliveryMonitoringSnsTopicArn`
SNS topic (subscribed to the `DeliveryMonitoringSlackEmail` channel) listing the still
open/unresolved PREPARE cases. No CSV and no S3 links are included. The Lambda runs daily,
but the report is sent only on Mondays (`weekday == 0`, UTC); it can be forced for testing
with the event flag `{"force_weekly_report": true}`. The email is sent even when there are
no open cases, stating it explicitly, so it also confirms the monitoring is active.

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
