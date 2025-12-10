# Athena Reporting and Alerts Lambda

Lambda function for executing scheduled Athena reporting and alerts queries with CSV export and Slack notifications.

## Overview

Executes Athena queries with two operational modes:
- **Export mode**: Always exports results to CSV and sends Slack notification
- **Alerts mode**: Evaluates threshold conditions and conditionally notifies

Processes queries configured in a JSON file stored in Git repository.

## Architecture

```
EventBridge Schedule → Lambda → Athena Query → CSV Export → SNS → Slack
                         ↓
                    Git Config (JSON)
```

## Execution Flow

1. Triggered by EventBridge Schedule with `query_id` parameter
2. Fetch configuration from Git repository (with SHA embedded in URL)
3. Build query with date variable substitution (T-1 by default)
4. Execute Athena query and wait for completion
5. Process results based on mode (export or alerts)
6. Send Slack notification via SNS email-to-Slack pattern

## Environment Variables

- `CONFIG_GIT_URL`: Git raw content URL with embedded commit SHA (required)
- `OUTPUT_S3_BUCKET`: Output bucket for CSV reports (required)
- `CSV_S3_PREFIX`: S3 key prefix for CSV files (default: `athena_query_results`)
- `ATHENA_RESULTS_BUCKET`: Athena query results bucket (required)
- `ATHENA_DATABASE`: Glue database name (required)
- `ATHENA_WORKGROUP`: Athena workgroup (required)
- `SNS_TOPIC_ARN`: SNS topic ARN for Slack notifications (required)
- `MAX_WORKERS`: Parallel execution limit (default: 10)

## CSV Export Structure

```
s3://{OUTPUT_S3_BUCKET}/{CSV_S3_PREFIX}/{query_id}/{YYYY}/{MM}/{DD}/{filename}
```

Example:
```
s3://pn-logs-bucket/athena_query_results/daily-notifications-report/2025/11/04/notifications-report-2025-11-04.csv
```

## Operational Modes

### Export Mode

1. Execute query
2. Always export CSV to S3
3. Always send Slack notification
4. Include S3 URL in notification

### Alerts Mode

1. Execute query
2. Count result rows
3. For each alert: evaluate threshold condition
4. If condition met: export CSV (optional) + send notification
5. If not met: log only

Supported operators: `>`, `<`, `>=`, `<=`, `==`, `!=`

## Testing

Manual invocation:
```bash
aws lambda invoke \
  --function-name pn-AthenaReportingAlerts \
  --payload '{"query_id": "daily-notifications-report"}' \
  --region eu-south-1 \
  output.json
```

Check logs:
```bash
aws logs tail /aws/lambda/pn-AthenaReportingAlerts --follow --region eu-south-1
```

## File Structure

```
athena-reporting-alerts/
├── index.py                    # Lambda entry point
├── handler.py                  # Main orchestration logic
├── config.py                   # Configuration module
└── services/                   # AWS SDK service layer
    ├── athena_client.py       # Athena query execution
    ├── s3_client.py           # CSV export to S3
    └── slack_client.py        # SNS notifications
```

## Related Resources

- CloudFormation Stack: `pn-cdc-analytics.yaml`
- Query Config: `athena/reporting-alerts-config.json`
- Scheduler Lambda: `athena-reporting-alerts-scheduler/`