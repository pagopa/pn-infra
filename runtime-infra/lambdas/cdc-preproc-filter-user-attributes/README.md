# CDC Preprocessing Filter User Attributes Lambda

Lambda function used as an Amazon Data Firehose processor to filter CDC records from the shared `pn-cdc-stream` and allow only records related to the `pn-UserAttributes` table to be delivered to S3.

## Overview

The Lambda is invoked by Amazon Data Firehose during record processing.
For each incoming CDC record, it reads the `tableName` field and returns a Firehose processing status:

* `Ok` for records where `tableName` matches the configured target table;
* `Dropped` for records belonging to other tables;
* `ProcessingFailed` for records that cannot be decoded or parsed.

This allows the preprocessing Firehose stream to read from the shared CDC Kinesis stream while delivering to S3 only the records related to `pn-UserAttributes`.

## Architecture

```
Kinesis Data Stream: pn-cdc-stream
        ↓
Amazon Data Firehose
        ↓
CDC Preprocessing Filter Lambda
        ↓
Keep only tableName = pn-UserAttributes
        ↓
S3 raw path:
poc/cdc-preproc/raw(parametro dinamico)/TABLE_NAME_pn-UserAttributes/yyyy/MM/dd/HH/
```

## Processing Logic

For each Firehose record:

1. Decode the base64 payload.
2. Parse the CDC record as JSON.
3. Read the `tableName` field.
4. Compare it with the configured `TARGET_TABLE_NAME`.
5. Return:

   * `Ok` if the record must be delivered to S3;
   * `Dropped` if the record must be discarded;
   * `ProcessingFailed` if the record cannot be processed.

## Environment Variables

* `TARGET_TABLE_NAME`: CDC table name to keep. Default: `pn-UserAttributes`.
* `ENVIRONMENT`: Environment/project identifier used only for logging. Default: `Missing`.

## Firehose Output Contract

The Lambda follows the Amazon Data Firehose processor response format:

```json
{
  "records": [
    {
      "recordId": "record-id",
      "result": "Ok",
      "data": "base64-encoded-record"
    }
  ]
}
```

Supported result values:

* `Ok`: the record is valid and will continue to S3 delivery;
* `Dropped`: the record is intentionally discarded and will not be delivered;
* `ProcessingFailed`: the record failed processing and will be routed to the Firehose error output path.

## Example

Input CDC record after base64 decoding:

```json
{
  "tableName": "pn-UserAttributes",
  "eventName": "MODIFY",
  "dynamodb": {
    "NewImage": {}
  }
}
```

If `TARGET_TABLE_NAME` is `pn-UserAttributes`, the Lambda returns:

```json
{
  "recordId": "...",
  "result": "Ok",
  "data": "..."
}
```

For any other `tableName`, the Lambda returns:

```json
{
  "recordId": "...",
  "result": "Dropped",
  "data": "..."
}
```

## File Structure

```
cdc-preproc-filter-user-attributes/
├── __init__.py          # Empty package marker
├── index.py             # Lambda entry point
├── README.md            # Lambda documentation
└── requirements.txt     # Python dependencies
```

## Dependencies

The Lambda uses only Python standard libraries:

* `base64`
* `json`
* `os`
* `datetime`

No external dependencies are required.

## Deployment Notes

The Lambda package must be built as:

```
cdc-preproc-filter-user-attributes.zip
```

The zip must contain `index.py` at the root level:

```
cdc-preproc-filter-user-attributes.zip
├── index.py
├── __init__.py
├── README.md
└── requirements.txt
```

The CloudFormation handler must be configured as:

```yaml
Handler: index.lambda_handler
```

The Lambda code is referenced from S3 using the standard repository deployment pattern:

```yaml
Code:
  S3Bucket: !Ref LambdasBucketName
  S3Key: !Sub '${LambdasBasePath}/cdc-preproc-filter-user-attributes.zip'
```

## Monitoring

The Lambda writes processing summaries to CloudWatch Logs.

Key log messages:

* `Initialization complete. TARGET_TABLE_NAME=...`
* `Starting Firehose preprocessing Lambda. Processing N records.`
* `Error processing Firehose recordId=...`
* `Batch processed at ... Kept=X, Dropped=Y, Failed=Z`

## Related Resources

* Source stream: `pn-cdc-stream`
* Firehose processor: preprocessing Firehose delivery stream
* Target table: `pn-UserAttributes`
* S3 raw prefix: `raw(parametro)/TABLE_NAME_pn-UserAttributes/`
