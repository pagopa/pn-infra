# CloudFormation Macro for CloudWatch Alarm Segmentation

  

## Overview

Lambda function for a CloudFormation Macro that creates segmented CloudWatch alarms. The segmentation is based on monitoring groups defined in the OpenAPI specification. These groups are extracted from custom OpenAPI extensions (`x-pagopa-monitoring-group`) or fallback tags.

  

## Logic and Workflow

The macro organizes alarms by grouping metrics related to individual API Gateway operations. The logic is primarily based on the value of the `x-pagopa-monitoring-group` extension in the OpenAPI specification. Here's how it works:

  
### Example
Consider the following operations in an OpenAPI specification:

```yaml
/v1/notifications/received/search:
  get:
    summary: "Example"
    operationId: searchReceivedNotifications
    tags:
      - NotificationReceived
    x-pagopa-monitoring-group: notification-notificationreceived
```
```yaml
/v1/notifications/sent/search:
  get:
    summary: "Example"
    operationId: getSentNotificationSearch
    tags:
      - NotificationSent
    x-pagopa-monitoring-group: notification-notificationsent
```
```yaml
/v1/notifications/failed/search:
  get:
    summary: "Example"
    operationId: getFailedNotificationSearch
    tags:
      - NotificationSent
```

  

### Grouping Logic:

  

Operation 1 (searchReceivedNotifications):

The x-pagopa-monitoring-group value is notification-notificationreceived.

This is split into:

Group: notification

Subgroup: notificationreceived.

  

Operation 2 (getSentNotificationSearch):

The x-pagopa-monitoring-group value is notification-notificationsent.

This is split into:

Group: notification-notificationsent

Subgroup: notificationsent.

  

Operation 3 (getFailedNotificationSearch):

The x-pagopa-monitoring-group extension is absent.

In this case:

Group: noextension

Subgroup: The first tag value from the tags array (NotificationSent).

  

### Composite Alarm:

  

Operation 1 and Operation 2:

Both operations are part of the same composite alarm group because they share the same group (notification).

Subgroups (notificationreceived and notificationsent) provide further differentiation within the group.

  

Operation 3:

This operation is not included in the same composite alarm group as the others.

It is placed in the noextension group with its subgroup derived from the first tag value (NotificationSent).

  

### Composite Alarm Grouping for `noextension`:

  

For operations without the x-pagopa-monitoring-group extension, the group is set to `noextension` followed by the first tag value.

Example:

If an operation has the tag `NotificationSent` but no extension, it is grouped into:

Group: noextension-notificationsent

Subgroup: NotificationSent.

These alarms are managed separately from alarms that have the extension defined.

Composite alarms for `noextension-$tag` ensure that operations without explicit extensions are still monitored effectively.

  

### Special Cases

  

**Missing Extension (x-pagopa-monitoring-group):**

If the extension is missing or null, the macro uses:

*Group:* noextension-$tag (The first tag value from the tags)

*Subgroup:* The first tag value from the tags list (e.g., NotificationSent).

  

**Explicit Skip (x-pagopa-monitoring-group: <none>):**

If the extension value is <none>, the operation is excluded from monitoring entirely.

  

### Key Considerations:

  

- Composite alarms respect AWS limits of 10 metrics per alarm.

- Operations with the same group are grouped together into a single composite alarm.

- Operations without the extension are handled separately in the `noextension-$Tag` group to avoid conflicts with explicitly defined groups.

  
  
  
  

---

  

## Features

- **Granular  Monitoring**:

- Creates CloudWatch alarms for API Gateway operations.

- Groups alarms based on `x-pagopa-monitoring-group` or fallback tags.

  

- **Customizable  Alarm Rules**:

- Supports configuration for standard and on-call alarms via input parameters.

  

- **Integration  with OpenAPI**:

- Parses OpenAPI specifications stored in S3.

- Dynamically adapts to changes in the specification.

  

---

  

## Templates involved in the process

### Template A: `pn-infra/runtime-infra/fragments/lambda-api-alarms-segmentation-transform.yaml`

This template deploys the Lambda function and registers it as a CloudFormation Macro. It includes:

- IAM Role for Lambda execution.

- CloudWatch Log Group for Lambda logs.

- Resources for the Lambda function.

  

### Template B: `pn-infra/runtime-infra/fragments/api-gw-alarms-segmentation.yaml`

Invokes the Macro to create CloudWatch alarms and outputps:

- Parameters for API Gateway, OpenAPI spec, and alarm configurations.

- Expand adding segmented alarms based on extracted monitoring groups.

  

### Template C: `pn-infra/runtime-infra/fragments/api-gw-expose-service-openapi.yaml`

This is the main interface for deploying and exposing APIs with monitoring, defines the API Gateway resource and and, conditionally, invokes Template B fragment as nested cloudformation resource.
The "Template B" invocation can be enabled trough the valorization of the AlarmSegmentation parameter with the "true" value. 

  

### Template D: `microservice.yaml`

Invoke the "Template C" as nested resource for the REst api creation. 

  

---

  

## Lambda Functionality

### Handler

The Lambda function's `handler` orchestrates the following steps:

1. **Parameter Parsing**:

- Retrieves and validates input parameters.

2. **OpenAPI Retrieval**:

- Downloads the OpenAPI specification from S3 using `get_openapi_from_s3`.

3. **Monitoring Group Extraction**:

- Extracts `x-pagopa-monitoring-group` values or fallback tags using `extract_monitoring_groups`.

4. **Alarm Generation**:

- Creates standard, on-call, and composite alarms using modular functions:

- `create_standard_base_alarms`

- `create_oncall_base_alarms`

- `create_composite_alarms`

5. **Output Generation**:

- Generates outputs for composite alarms with `create_outputs_for_composite_alarms`.

  

---

  

## Dependencies

The Lambda function relies on the following Python libraries:

- **`boto3`**:  Default library included in the Lambda runtime, used for interacting with AWS services.

- **`PyYAML`**:  For parsing YAML files, installed via `requirements.txt`.
