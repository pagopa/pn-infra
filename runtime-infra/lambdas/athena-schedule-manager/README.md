# Athena Schedule Manager Lambda

Lambda function that implements a reconciliation loop to manage EventBridge Schedules dynamically based on JSON configuration from Git.

## Overview

The Schedule Manager automatically creates, updates, and deletes EventBridge Schedules based on query definitions in a Git-hosted JSON configuration file. This enables self-service query scheduling without requiring infrastructure deployments.

## Architecture

```
EventBridge (rate 5 min) → Schedule Manager Lambda
                              ↓
                         1. Fetch config.json from Git
                         2. List existing Schedules
                         3. Calculate diff (create/update/delete)
                         4. Apply changes via boto3
                              ↓
                         EventBridge Schedules
                              ↓
                         Query Executor Lambda
```

## Reconciliation Logic

### Every 5 Minutes

1. **Fetch Desired State**: Download `query-executor-config.json` from Git (with SHA embedded in URL)
2. **Get Current State**: List all EventBridge Schedules in group `pn-athena-queries`
3. **Calculate Diff**:
   - **CREATE**: Query in JSON but no Schedule exists
   - **UPDATE**: Schedule exists but cron expression changed
   - **DELETE**: Schedule exists but query removed from JSON
4. **Apply Changes**: Use `boto3.client('scheduler')` to create/update/delete schedules

### Example Scenario

**Initial State**: No schedules

**Add query to JSON**:
```json
{
  "queries": {
    "daily-report": {
      "schedule": "cron(0 2 * * ? *)",
      "query": "SELECT..."
    }
  }
}
```

**After 5 minutes**:
- Schedule Manager detects new query
- Creates EventBridge Schedule `pn-daily-report`
- Schedule will trigger Query Executor at 02:00 UTC daily

**Change cron in JSON**:
```json
{
  "schedule": "cron(0 3 * * ? *)"
}
```

**After 5 minutes**:
- Schedule Manager detects cron change
- Updates existing Schedule to new cron

**Remove query from JSON**:

**After 5 minutes**:
- Schedule Manager detects missing query
- Deletes EventBridge Schedule `pn-daily-report`

## Environment Variables

- `CONFIG_GIT_URL`: Git raw content URL with embedded commit SHA (required)
- `QUERY_EXECUTOR_ARN`: ARN of Query Executor Lambda function (required)
- `SCHEDULE_ROLE_ARN`: IAM Role ARN for EventBridge Scheduler (required)
- `SCHEDULE_GROUP_NAME`: EventBridge Schedule Group name (default: `pn-athena-queries`)
- `PROJECT_NAME`: Project name prefix for schedule names (default: `pn`)

### Git URL Format

```
https://raw.githubusercontent.com/{org}/{repo}/{commit-sha}/{path-to-file}
```

Example:
```
https://raw.githubusercontent.com/pagopa/pn-infra/abc123def456.../runtime-infra/athena/query-executor-config.json
```

## Schedule Naming Convention

Schedules are named using the pattern: `{PROJECT_NAME}-{query_id}`

Examples:
- Query ID: `daily-report` → Schedule: `pn-daily-report`
- Query ID: `high-volume-alert` → Schedule: `pn-high-volume-alert`

## JSON Configuration Requirements

The Schedule Manager expects queries in the config to have:

- **`schedule`** (or `cron`): EventBridge cron expression (6 fields, UTC timezone)
- **`description`**: Optional description for the schedule

Example:
```json
{
  "queries": {
    "daily-notifications-report": {
      "schedule": "cron(0 2 * * ? *)",
      "description": "Daily report of notifications sent",
      "type": "export",
      "query": "SELECT..."
    }
  }
}
```

## IAM Permissions Required

### Schedule Manager Role

```yaml
Policies:
  - PolicyName: ManageSchedules
    Statement:
      - Effect: Allow
        Action:
          - scheduler:CreateSchedule
          - scheduler:UpdateSchedule
          - scheduler:DeleteSchedule
          - scheduler:GetSchedule
          - scheduler:ListSchedules
        Resource: 
          - arn:aws:scheduler:*:*:schedule/pn-athena-queries/*
      
      - Effect: Allow
        Action: iam:PassRole
        Resource: !Ref SchedulerExecutionRoleArn
```

## Monitoring

### CloudWatch Logs

Custom log format for lambda-alarms metric filter:
```
timestamp aws_request_id level message
```

### Key Log Messages

- `Fetching config from Git: {url}` - Config retrieval
- `Found {N} existing schedules` - Current state
- `CREATE: {name} (cron: {expr})` - New schedule
- `UPDATE: {name} (cron: {old} → {new})` - Changed cron
- `DELETE: {name} (removed from config)` - Obsolete schedule
- `Reconciliation complete: {results}` - Summary

### Reconciliation Results

```json
{
  "created": 2,
  "updated": 1,
  "deleted": 0,
  "failed": 0
}
```

## Testing

### Manual Invocation

```bash
aws lambda invoke \
  --function-name pn-AthenaScheduleManager \
  --region eu-south-1 \
  output.json
```

### Verify Schedules Created

```bash
aws scheduler list-schedules \
  --group-name pn-athena-queries \
  --region eu-south-1
```

### Check Schedule Details

```bash
aws scheduler get-schedule \
  --group-name pn-athena-queries \
  --name pn-daily-report \
  --region eu-south-1
```

## Error Handling

### Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| `Failed to fetch config from Git` | Invalid URL or 404 | Verify CONFIG_GIT_URL and commit SHA |
| `Failed to create schedule` | IAM permissions | Check Schedule Manager role has `scheduler:CreateSchedule` |
| `Failed to update schedule` | Schedule doesn't exist | Will auto-create on next reconciliation |
| `ResourceNotFoundException: Schedule group` | Group doesn't exist | Group created automatically on first schedule |

### Failure Behavior

- Individual schedule failures are logged but don't stop reconciliation
- Failed operations counted in `results.failed`
- Lambda succeeds even if some schedules fail (partial success)

## Best Practices

1. **Cron Expressions**: Always use 6-field UTC format: `cron(minute hour day month ? year)`
2. **Query IDs**: Use lowercase with hyphens: `daily-report`, not `Daily_Report`
3. **Git SHA**: Always embed commit SHA in URL for deterministic config fetching
4. **Testing**: Test cron changes in dev before prod deployment
5. **Schedule Limits**: AWS has quotas on schedules per account (check limits)

## Dependencies

- **`boto3`**: AWS SDK (included in Lambda runtime)
- **`urllib`**: HTTP client for Git (Python standard library)
- **`json`**: JSON processing (Python standard library)

No external dependencies required.

## File Structure

```
athena-schedule-manager/
├── __init__.py                 # Package marker
├── index.py                    # Lambda entry point
├── schedule_manager.py         # Reconciliation logic
├── requirements.txt            # Python dependencies (empty)
└── README.md                   # This file
```

## Related Resources

- Query Executor Lambda: [`athena-query-executor/`](../athena-query-executor/)
- CloudFormation Stack: [`pn-athena-query-executor.yaml`](../../pn-athena-query-executor.yaml)
- Query Config: [`athena/query-executor-config.json`](../../athena/query-executor-config.json)