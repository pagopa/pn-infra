# Downstream hourly compaction

The CORE Lambda queries the distinct CORE and CONFINFO downstream source tables,
consolidates their records, and publishes **one Parquet object per source hour**:

```text
s3://<CORE DataMonitoringBucket>/<OUTPUT_PREFIX>/YYYY/MM/DD/HH/data.parquet
```

The default published prefix is `downstream-compacted`. Source JSON, intermediate
Athena files and Athena query metadata use separate prefixes. A rerun replaces the
same final key; it does not append another file or update a Glue output partition.
PN-22249 defines the output table and reader permissions independently.

## Runtime and resources

Use Node.js **24.18.0 or newer**, required by the pinned Parquet dependency.
The infrastructure reuses `LambdaJSRuntime` (default `nodejs24.x`); verify that the
runtime available in the target environment satisfies this minimum before activation.

Thrift 0.24.0 loads `uuid` with CommonJS `require()`, but its declared uuid 14
dependency is ESM-only. A scoped npm override pins Thrift's uuid to 11.1.1,
which provides the required APIs through a CommonJS entry point. Keep the override
until the upstream dependency supports loading without experimental ESM interop.
Tests disable `require(esm)` to catch Lambda initialization failures locally.

The complete query, download, consolidation and upload must fit within the Lambda
timeout. A deadline ten seconds before termination reserves time for cancellation
and cleanup. The implementation downloads one input file at a time and writes a
local output file with bounded output row groups. The configured temporary storage
must accommodate the final file and the largest intermediate file; input row groups
must also fit in memory. Resource exhaustion fails the invocation instead of
truncating records or publishing multiple files.

Defaults are 1024 MB memory, 4096 MB temporary storage and 900 seconds timeout.
These are initial configuration values, not verified production sizing. Validate
peak hourly data, including the repeated autumn hour, before enabling the schedule.
No live AWS workload has been certified by local tests.

## Invocation

The EventBridge Scheduler schedule is **DISABLED by default**, including the development cfg.
Choose an hourly Europe/Rome cron expression and state separately for each environment.
The illustrative default is `cron(5 * * * ? *)`; no deployment or activation is
performed by building this function.

Scheduled invocations use Scheduler's `<aws.scheduler.scheduled-time>` to select the
previous closed source partition. They do not automatically recover skipped or
failed hours. Error retries are disabled both on Scheduler and on asynchronous
Lambda invocations. Delivery delays/throttling can still defer an invocation
within its configured event age; this does not change the selected hour.
The schedule uses Europe/Rome with its flexible time window OFF and a dedicated execution
role restricted to invoking this Lambda. Its trust policy is scoped to the current
account and default Scheduler schedule group. Schedule ARN plus nominal time form
the stable request identity, rather than the per-attempt execution ID.

Scheduled mode only creates missing hourly outputs. If the final object already
exists, it logs a skip and returns `status: already_published` without querying
Athena or uploading. Only manual mode can replace an existing hourly output.
This prevents delayed or duplicate scheduled deliveries from republishing an old
Athena result over a manually refreshed file.

To reprocess an hour, invoke with an explicit local partition hour:

```json
{
  "mode": "manual",
  "partitionHour": "2026-11-04T10"
}
```

This identifies the source directory `2026/11/04/10` in **Europe/Rome**, not an
event timestamp and not UTC. Missing, invalid or open manual hours are errors.
Old events received later are read with their actual ingestion-hour partition.

`DownstreamCompactionPartitionSettleSeconds` (default 120) is the minimum wait
after a partition closes. Configure it for the maximum producer upload duration in
**both** domains and choose the cron minute accordingly. An invocation before this
period expires fails explicitly. Producers currently partition before uploading,
so changing the partition at the hour boundary does not by itself prove every
previous-hour upload has finished.

At the autumn DST transition, both occurrences of a repeated civil hour share a
source directory. Scheduler invokes only once in the repeated local hour; that
invocation processes the preceding partition. The invocation in the following
local hour processes the repeated directory after both occurrences close.
The missing spring hour is never synthesized.

## Publication and recovery

1. Athena `UNLOAD` combines source records using `UNION ALL` and explicit columns.
2. The query manifest identifies only the intermediate files belonging to this
   attempt, including paginated manifests.
3. The consolidator preserves all twelve application fields, nulls, duplicate
   records and exact signed INT64 durations. It validates input schemas and the
   consolidated row count. Zero records produces a valid empty Parquet.
4. Only a completed local file is uploaded to the deterministic final key.
   Small files use `PutObject`; larger files use multipart upload completed only
   after every part succeeds. The previous file is not deleted first.

Reserved concurrency is one. Scheduled writes always require object absence
(`IfNoneMatch: '*'`), including at multipart completion. Manual replacements compare
the previous ETag, or require absence for initial publication. If an object appears
or changes after the initial check, the conditional write fails explicitly instead
of overwriting it; this conflict is not reported as a successful skip.

Failures are logged with `ERROR` and rethrown, allowing the existing Lambda alarm
fragment to observe invocation errors. Investigate the query ID and error before
manually retrying the affected hour. A timeout attempts to stop the query; failure
to stop it is also reported. Any query that finishes later writes only to staging.
Multipart failures attempt abort, and abort failures remain explicit.

If S3 commits the upload but its response is lost, the invocation may fail while
the new complete file is already present. Inspect its `compaction-id`, `query-id`
and `row-count` metadata before retrying; no partial final object is published.
Successful overwrites do not retain the old object unless the bucket already has
versioning. No new versioning, retention or lifecycle rules are introduced.
Athena intermediate files and manifests remain in their separate prefixes;
historical cleanup/backfill is outside this task.

Disabling the schedule stops new automatic invocations, not in-flight work or manual
invocations. Re-enabling does not replay the disabled interval.

## Deployment contract

The common data monitoring template creates runtime resources only in CORE.
The CONFINFO source table must point to `ConfinfoDynamoDbExportBucketName`,
not the CORE bucket. The CONFINFO bucket policy permits Athena-mediated reads and bucket-location lookup
from CORE; validate that policy together with the Lambda's scoped source permissions
in the target environment. Deploy the bucket-location permission update in CONFINFO
before the first real query from the new runtime role.

The Lambda needs source Glue metadata, Athena workgroup operations, source reads,
and S3 staging/result/final-object access. It does not need the PN-22249 output
table to generate or replace files, nor any Glue write permission. Workgroup
enforced result locations must agree with the configured results prefix and IAM
permissions; a mismatch is an error, not a fallback location.

For promoted environments, apply schedule/configuration through the existing
`pn-configuration` release process with separate authorization. Keep schema and
the stable final path aligned with PN-22249; its table must not scan staging or
query-result prefixes.

## Local checks and packaging

```sh
npm ci --ignore-scripts
npm run test-build
```

Tests use the native Node runner and mocked AWS clients; they do not query AWS.
`test-build` runs tests then builds `function.zip`, including runtime dependencies
but not tests or documentation. The existing multilambda builder discovers the
directory automatically. Environment checks are still required to establish
cross-account access, Athena-produced Parquet compatibility and peak throughput.
