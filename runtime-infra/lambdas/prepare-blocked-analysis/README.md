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
- `LookbackHours`: look-back hours applied in incremental mode (`start_time = last_update - lookback`) to recover late-arriving PREPARE events; set `0` to disable overlap (default: `24`)
- `S3ResultBucket`: S3 path for result files (required)
- `AthenaResultsBucket`: Athena query results bucket (required)
- `RepoZipUrl`: GitHub ZIP URL for pn-troubleshooting repository (required)
- `DataAnalysisSnsTopicArn`: SNS topic ARN for the weekly email report (optional; if empty the report is skipped)
- `EnvironmentType`: environment name, shown in the weekly report subject (optional)

## Weekly report (email alerting)

The weekly report is driven by a **dedicated EventBridge schedule** separate from the daily
analysis. It invokes the Lambda with the payload `{"report_only": true}`: in this mode the
Lambda does **not** run the Athena analysis, it only reads the latest result files from S3
(`prepare_analog_domicile_latest.json`) and publishes an email to `DataAnalysisSnsTopicArn`
(subscribed to the `DataAnalysisSlackEmail` channel) listing the still open/unresolved
PREPARE cases (no CSV, no S3 links). The email is sent even with zero open cases, stating it
explicitly, to confirm the monitoring is active.

The schedule is an **`AWS::Scheduler::Schedule`** (EventBridge Scheduler) with
`ScheduleExpressionTimezone: Europe/Rome`, controlled by
`LambdaPrepareBlockedWeeklyReportCronExpression` (default `cron(0 10 ? * MON *)` = Monday
10:00 Italy) and `LambdaPrepareBlockedWeeklyReportEnableCronExpression` (ENABLED/DISABLED).
Being timezone-aware, it follows DST automatically (always 10:00 Italy). The Scheduler
invokes the Lambda through a dedicated IAM role (`pn-prepare-blocked-scheduler-role-*`).

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
