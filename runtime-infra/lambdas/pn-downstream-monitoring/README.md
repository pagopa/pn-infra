   # Downstream monitoring

The CloudWatch Logs subscription invokes this Lambda asynchronously. Each non-empty
batch produces one NDJSON object under
`downstream-http-call/<year>/<MM>/<DD>/<HH>/<uuid>.json`.
Partitions use the processing time in Europe/Rome. The client is reused between
invocations; neither the object layout nor the record schema changes with retries.

## Upload configuration

The parent [template](../../pn-data-monitoring.yaml) provides:

| Parameter | Environment variable | Default |
| --- | --- | --- |
| `LambdaDownstreamMonitoringS3MaxRetries` | `S3_MAX_RETRIES` | 3 |
| `LambdaDownstreamMonitoringS3UploadBudgetSeconds` | `S3_UPLOAD_BUDGET_SECONDS` | 45 |

Retry count accepts integers from 0 to 3, **in addition to the initial attempt**.
The SDK uses standard exponential backoff with jitter. Zero disables retries.
The upload budget includes requests and retry waits; it is capped at the Lambda
remaining time minus a five-second margin. Invalid settings or insufficient
remaining time fail explicitly. The deadline aborts the SDK operation, but cannot
undo a PUT that S3 has already committed.

An upload may fail before all attempts are used if the budget or SDK retry quota
is exhausted. Logs report duration and available SDK attempt/delay/error metadata.
Upload failures and skipped non-JSON records are logged at WARN, not ERROR.
Upload errors are still thrown: Lambda can emit its own invocation error log and
increment the native Errors metric. This change does not disable those signals.
The Lambda log envelope supplies the invocation ID. No additional payload logging
is introduced.

These settings absorb transient `SlowDown/503` errors; they do not reduce the
normal PUT count or guarantee sufficient throughput for sustained overload.
Measure production peaks, S3 failures, Lambda duration/concurrency and async event
age before changing concurrency or promoting tuning.

## Failure handling and alarms

CORE and CONFINFO each use a local, standalone SQS standard DLQ configured on the
Lambda. It has SQS-managed encryption, configurable retention (14 days by default)
and a visible-message alarm (threshold 1 by default). The role may only send to
that queue. The nested stack and queue are retained on removal/replacement;
messages still expire according to retention.

Existing Lambda Errors/log alarms remain in place. Skipped non-JSON records no
longer feed the ERROR-log metric; their warning logs remain available for
investigation. A separate `DeadLetterErrors` alarm reports failure to deliver to
the DLQ, independently of log severity. Both paths use the existing standard
alarm topic. The parent exposes the delivery alarm's threshold, period, evaluation
periods and datapoints to alarm; datapoints must not exceed evaluation periods.

The three retry layers are independent:

1. CloudWatch Logs retries retryable delivery failures to the Lambda service.
2. After acceptance, Lambda manages asynchronous function retries and event age.
   This change does not override those existing settings.
3. During each execution, the SDK retries S3 uploads within the configured budget.

After asynchronous retries are exhausted or an accepted event expires, Lambda
can send the original event to the DLQ, with error details in message attributes.
Delivery requires the payload plus attributes to fit the queue's actual message
size limit. Permission, size or other delivery failures raise `DeadLetterErrors`;
the DLQ is not a guarantee of zero data loss. It does not cover events never
accepted by Lambda or individual malformed records currently skipped by parsing.

## Controlled manual replay

Replay requires separate operational authorization and operator permissions for
SQS receive/delete, Lambda invoke and S3 verification. No automatic replay
consumer is configured. Normal SQS redrive cannot directly invoke this Lambda.

1. Confirm S3 has recovered. Receive one DLQ message without deleting it, retaining
   its receipt handle and error attributes. Set/extend visibility to cover the
   recovery operation.
2. Extract the SQS **body** as JSON. It is the original event:
   `{"awslogs":{"data":"<base64-encoded gzip payload>"}}`.
   Do not pass an SQS `Records` envelope to the existing handler.
3. Invoke the same-domain Lambda synchronously (`RequestResponse`) with that
   event. An accepted API call is not proof of successful function execution:
   inspect `FunctionError`, the returned error payload and the invocation logs.
4. Verify the expected records were written to the object identified by the
   invocation's `Written ...` log. Only then delete the SQS message with its
   current receipt handle.
5. On error or uncertain completion, do not delete the message or blindly repeat
   it. Check the S3 outcome first. Stop replay if `SlowDown` recurs; start with
   one batch at a time and monitor the original producer as well.

The same key/body is reused for SDK retries within one invocation. Distinct Lambda
invocations and manual replay generate new UUIDs, so at-least-once delivery or a
lost success response can create duplicates. This change does not provide
exactly-once ingestion.

Replay uses the **recovery hour**, not the original log hour, for S3 partitioning.
Late recovery can require a manual re-run of affected downstream compaction hours
and checks of Athena/QuickSight ingestion windows. Do not silently change record
timestamps or assume an already compacted hour will be updated automatically.

## Verification and release

Run `npm ci --ignore-scripts` followed by `npm test` for handler tests and real SDK retry/deadline tests against an
in-process HTTP endpoint using dummy credentials, without AWS access. The existing
`npm run build` packages production dependencies and excludes `src/test`.
The AWS client is a development dependency for local tests, not included in the
production ZIP. The deployed Lambda uses AWS SDK v3 provided by its Node.js
runtime. Local checks must supply an external SDK when loading the extracted ZIP,
and confirm it is not bundled. The runtime's SDK version can differ from the
locally locked version; verify retry behavior in dev before promotion.

With separate deployment authorization, test both domains in dev: controlled
asynchronous failure, DLQ delivery, alarm notification and manual recovery.
Verify message-size limits and effective async retry settings. Before promotion,
reconcile a representative load peak across S3, in-flight work and DLQ, check zero
unexpected losses/DeadLetterErrors and that backlog drains after the peak.
If sustained load does not converge, revisit buffering/batching instead of merely
increasing retries.

Rollback may restore code/tuning without removing the DLQ. Keep retained messages
available for recovery; rollback cannot undo successful PUTs, duplicates or expiry.

AWS references:
[S3 scaling](https://docs.aws.amazon.com/AmazonS3/latest/userguide/optimizing-performance.html),
[asynchronous retries](https://docs.aws.amazon.com/lambda/latest/dg/invocation-async-error-handling.html),
[DLQ delivery](https://docs.aws.amazon.com/lambda/latest/dg/invocation-async-retain-records.html).
