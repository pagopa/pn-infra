# Athena Query Executor Lambda

Lambda function for executing scheduled Athena queries with CSV export and Slack notifications.

## Overview

The Lambda performs automated execution of Athena queries with two operational modes:
- **Export mode**: Always exports results to CSV and sends Slack notification
- **Alerts mode**: Evaluates threshold conditions and conditionally notifies

The Lambda processes queries configured in a JSON file stored in Git repository.

## Architecture

```
EventBridge Schedule → Lambda → Athena Query → CSV Export → SNS → Slack
                         ↓
                    Git Config (JSON)
```

## Logic and Workflow

### Execution Flow

1. **Triggered by EventBridge Schedule** with `query_id` parameter
2. **Fetch Configuration** from Git repository (with SHA embedded in URL)
3. **Build Query** with date variable substitution (T-1 by default)
4. **Execute Athena Query** and wait for completion
5. **Process Results** based on mode:
   - **Export mode**: Always export CSV + notify
   - **Alerts mode**: Evaluate threshold → export/notify if condition met
6. **Send Slack Notification** via SNS email-to-Slack pattern

### Configuration Source

**Git Repository** (required):
- Fetches JSON configuration from Git raw content URL
- URL must include embedded commit SHA for versioning
- File not found → Lambda fails
- Valid JSON → Uses query configurations

**Git URL Format**:
```
https://raw.githubusercontent.com/{org}/{repo}/{commit-sha}/{path-to-file}
```

**Example**:
```
https://raw.githubusercontent.com/pagopa/pn-infra/abc123def456.../runtime-infra/athena/query-executor-config.json
```

## JSON Configuration Schema

### Structure

```json
{
  "global_config": {
    "athena_database": "cdc_analytics_database",
    "athena_workgroup": "cdc_analytics_workgroup"
  },
  "queries": {
    "query-id": {
      "type": "export" | "alerts",
      "description": "Query description",
      "schedule": "cron(0 2 * * ? *)",
      "query": "SELECT ... WHERE p_year = '{YEAR}' AND p_month = '{MONTH}' AND p_day = '{DAY}'",
      "csv_export": true,
      "csv_filename_template": "report-{date}.csv",
      "slack": {
        "enabled": true,
        "message_template": "Report: {total_rows} records\nS3: {s3_url}"
      },
      "alerts": [
        {
          "name": "high-volume",
          "threshold": {
            "operator": ">",
            "value": 10000
          },
          "csv_export": true
        }
      ]
    }
  }
}
```

### Supported Variables

| Variable | Source | Example |
|----------|--------|---------|
| `{YEAR}` | T-1 day UTC | 2025 |
| `{MONTH}` | T-1 day UTC | 11 |
| `{DAY}` | T-1 day UTC | 04 |
| `{DATE}` | T-1 formatted | 2025-11-04 |
| `{THRESHOLD}` | `alert_threshold` config | 10000 |

### Message Template Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `{date}` | Execution date | 2025-11-04 |
| `{total_rows}` | Query result count | 1523 |
| `{s3_url}` | CSV S3 location | s3://bucket/path/file.csv |
| `{alert_count}` | Records count (alerts mode) | 5 |
| `{alert_name}` | Alert name | high-volume |
| `{threshold}` | Threshold value | 10000 |
| `{operator}` | Comparison operator | > |
| `{query_id}` | Query identifier | daily-report |
| `{description}` | Query description | Daily notifications report |
| `{timestamp}` | Execution timestamp ISO | 2025-11-04T02:00:15Z |

## Environment Variables

### Core Configuration

- `CONFIG_GIT_URL`: Git raw content URL with embedded commit SHA (required)
- `OUTPUT_S3_BUCKET`: Output bucket for CSV reports (required)
- `CSV_S3_PREFIX`: S3 key prefix for CSV files (default: `athena_query_results`)
- `ATHENA_RESULTS_BUCKET`: Athena query results bucket (required)
- `ATHENA_DATABASE`: Glue database name (required)
- `ATHENA_WORKGROUP`: Athena workgroup (required)
- `SNS_TOPIC_ARN`: SNS topic ARN for Slack notifications (required)
- `MAX_WORKERS`: Parallel execution limit (default: 10)

### Slack Notification Pattern

Uses SNS email-to-Slack pattern (from pn-data-monitoring):
- SNS Topic with email subscription to Slack channel
- Lambda publishes to SNS
- SNS forwards to Slack channel email
- No webhook URL or SSM parameters needed

## CSV Export

### S3 Path Structure

```
s3://{OUTPUT_S3_BUCKET}/{CSV_S3_PREFIX}/{query_id}/{YYYY}/{MM}/{DD}/{filename}
```

### Example

```
s3://pn-logs-bucket/athena_query_results/
  └── daily-notifications-report/
      └── 2025/
          └── 11/
              └── 04/
                  └── notifications-report-2025-11-04.csv
```

### CSV Format

- **Encoding**: UTF-8
- **Delimiter**: Comma (`,`)
- **Header**: First row with column names
- **Quote**: Double quotes (`"`) for fields containing commas

## Operational Modes

### Export Mode (`type: "export"`)

**Behavior**:
1. Execute query
2. **Always** export CSV to S3
3. **Always** send Slack notification via SNS
4. Include S3 URL in notification

**Use Cases**:
- Daily reports
- Scheduled data exports
- Regular analytics snapshots

### Alerts Mode (`type: "alerts"`)

**Behavior**:
1. Execute query
2. Count result rows
3. **For each alert**:
   - Evaluate: `COUNT(rows) {operator} {threshold}`
   - **If TRUE**:
     - Export CSV (if `csv_export: true`)
     - Send Slack notification via SNS
   - **If FALSE**: Log only, no action

**Supported Operators**:
- `>` Greater than
- `<` Less than
- `>=` Greater or equal
- `<=` Less or equal
- `==` Equal
- `!=` Not equal

**Use Cases**:
- Volume anomaly detection
- SLA violation monitoring
- Threshold-based alerting

## Testing

### Manual Invocation

Process T-1 data:
```bash
aws lambda invoke \
  --function-name pn-AthenaQueryExecutor \
  --payload '{"query_id": "daily-notifications-report"}' \
  --region eu-south-1 \
  output.json
```

Custom date:
```bash
aws lambda invoke \
  --function-name pn-AthenaQueryExecutor \
  --payload '{"query_id": "daily-notifications-report", "execution_date": "2025-11-03"}' \
  --region eu-south-1 \
  output.json
```

### Verify Results

**Check Logs**:
```bash
aws logs tail /aws/lambda/pn-AthenaQueryExecutor \
  --follow \
  --filter-pattern "query_id" \
  --region eu-south-1
```

**Check CSV Export**:
```bash
aws s3 ls s3://pn-logs-bucket/athena_query_results/daily-notifications-report/2025/11/04/
```

## Error Handling

### Custom Logging

Log format required by `lambda-alarms` metric filter:
```
timestamp aws_request_id level message
```

This ensures metric filter pattern `[w1, w2, w3="ERROR", w4]` correctly detects errors at position 3 for automated Slack notifications via alarm infrastructure.

### Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| `Missing required parameter: query_id` | Event missing query_id | Check EventBridge Schedule Input |
| `Query 'X' not found in config` | Query not in JSON | Add query to config or fix query_id |
| `Failed to fetch config from Git` | Invalid URL or 404 | Verify CONFIG_GIT_URL and commit SHA |
| `Query execution timeout` | Query too slow | Optimize query or increase timeout |
| `Failed to send SNS notification` | Invalid topic ARN | Check SNS_TOPIC_ARN environment variable |

## Dependencies

- **`boto3`**: AWS SDK (included in Lambda runtime)
- **`urllib`**: HTTP client for Git config (Python standard library)
- **`json`**: JSON processing (Python standard library)
- **`csv`**: CSV generation (Python standard library)

No external dependencies required.

## Deployment

### Package Lambda

```bash
cd pn-infra/runtime-infra/lambdas/athena-query-executor
zip -r ../athena-query-executor.zip .
```

### Upload to S3

```bash
aws s3 cp athena-query-executor.zip \
  s3://cd-pipeline-artifacts/pn-infra/${COMMIT_SHA}/lambdas/
```

### Deploy via CloudFormation

Stack deployment handled by `deployInfra.sh` with:
- Lambda package from S3
- Environment variables from cfg.json
- SNS Topic created in stack

## Monitoring

### CloudWatch Metrics

- Lambda invocations
- Duration
- Errors
- Iterator age

### CloudWatch Alarms

- Lambda errors → SNS notification
- Iterator age → SNS notification

### Custom Metrics (Future)

```python
cloudwatch.put_metric_data(
    Namespace='PN/AthenaQueryExecutor',
    MetricData=[
        {'MetricName': 'QueryExecutionTime', 'Value': duration, 'Unit': 'Seconds'},
        {'MetricName': 'RecordsProcessed', 'Value': count, 'Unit': 'Count'},
        {'MetricName': 'AlertsTriggered', 'Value': alerts, 'Unit': 'Count'}
    ]
)
```

## File Structure

```
athena-query-executor/
├── __init__.py                 # Package marker
├── index.py                    # Lambda entry point
├── handler.py                  # Main orchestration logic
├── config.py                   # Configuration module
├── requirements.txt            # Python dependencies (empty)
├── README.md                   # This file
└── services/                   # AWS SDK service layer
    ├── __init__.py
    ├── athena_client.py       # Athena query execution
    ├── s3_client.py           # CSV export to S3
    └── slack_client.py        # SNS notifications
```

## Related Resources

- CloudFormation Stack: `pn-athena-query-executor.yaml`
- Query Config: `athena/query-executor-config.json`
- Schedule Manager: `athena-schedule-manager/`
- Implementation Plan: `Athena/implementation-plan-final.md`

## Support

For issues or questions:
1. Check CloudWatch Logs for detailed execution traces
2. Verify Git config JSON is accessible and valid
3. Test Athena query manually in AWS Console
4. Verify SNS Topic subscription confirmed in Slack channel
5. Check IAM permissions for Lambda role