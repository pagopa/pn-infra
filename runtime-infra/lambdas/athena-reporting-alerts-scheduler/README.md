# Athena Reporting Alerts Scheduler Lambda

Lambda function that implements a reconciliation loop to manage EventBridge Schedules dynamically for Athena reporting and alerts queries.

## Overview

Automatically creates, updates, and deletes EventBridge Schedules based on query definitions in a Git-hosted JSON configuration file. Enables self-service query scheduling without infrastructure deployments.

## Architecture

```
EventBridge (rate 5 min) → Scheduler Lambda
                              ↓
                         1. Fetch reporting-alerts-config.json
                         2. List existing Schedules
                         3. Calculate diff
                         4. Apply changes
                              ↓
                         EventBridge Schedules
                              ↓
                         Reporting Alerts Lambda
```

## Reconciliation Logic

Every 5 minutes:
1. Fetch desired state from Git (with SHA embedded in URL)
2. Get current state from EventBridge Schedule Group
3. Calculate diff: CREATE, UPDATE, DELETE
4. Apply changes via boto3 scheduler client

## Environment Variables

- `CONFIG_GIT_URL`: Git raw content URL with embedded commit SHA (required)
- `REPORTING_ALERTS_ARN`: ARN of Reporting Alerts Lambda (required)
- `SCHEDULE_ROLE_ARN`: IAM Role ARN for EventBridge Scheduler (required)
- `SCHEDULE_GROUP_NAME`: EventBridge Schedule Group name (default: `pn-athena-reporting-alerts`)
- `PROJECT_NAME`: Project name prefix for schedule names (default: `pn`)

## Schedule Naming

Pattern: `{PROJECT_NAME}-{query_id}`

Examples:
- Query ID: `daily-report` → Schedule: `pn-daily-report`
- Query ID: `high-volume-alert` → Schedule: `pn-high-volume-alert`

## Testing

Manual invocation:
```bash
aws lambda invoke \
  --function-name pn-AthenaReportingAlertsScheduler \
  --region eu-south-1 \
  output.json
```

Verify schedules created:
```bash
aws scheduler list-schedules \
  --group-name pn-athena-reporting-alerts \
  --region eu-south-1
```

Check schedule details:
```bash
aws scheduler get-schedule \
  --group-name pn-athena-reporting-alerts \
  --name pn-daily-report \
  --region eu-south-1
```

## Monitoring

### CloudWatch Logs

Log format for lambda-alarms metric filter:
```
timestamp aws_request_id level message
```

Key messages:
- `Found {N} existing schedules`
- `CREATE: {name} (cron: {expr})`
- `UPDATE: {name} (cron: {old} → {new})`
- `DELETE: {name}`
- `Reconciliation complete: {results}`

### Reconciliation Results

```json
{
  "created": 2,
  "updated": 1,
  "deleted": 0,
  "failed": 0
}
```

## File Structure

```
athena-reporting-alerts-scheduler/
├── index.py                    # Lambda entry point
├── schedule_manager.py         # Reconciliation logic
└── requirements.txt            # Python dependencies (empty)
```

## Related Resources

- Reporting Alerts Lambda: `athena-reporting-alerts/`
- CloudFormation Stack: `pn-cdc-analytics.yaml`
- Query Config: `athena/reporting-alerts-config.json`