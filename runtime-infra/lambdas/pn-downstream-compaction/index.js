'use strict';

const { AthenaClient } = require('@aws-sdk/client-athena');
const { S3Client, HeadObjectCommand, GetObjectCommand } = require('@aws-sdk/client-s3');
const { createHash } = require('node:crypto');
const { createWriteStream } = require('node:fs');
const { mkdtemp, rm, stat } = require('node:fs/promises');
const { join } = require('node:path');
const { tmpdir } = require('node:os');
const { pipeline } = require('node:stream/promises');
const { selectPartition } = require('./lib/partition');
const { consolidate } = require('./lib/parquet');
const { buildQuery, executeQuery, identifier, manifestFiles } = require('./lib/athena');
const { publishFile } = require('./lib/s3');

const athena = new AthenaClient({});
const s3 = new S3Client({});

function configuration(env) {
  function required(name) {
    const value = env[name];
    if (typeof value !== 'string' || !value.trim()) {
      throw new Error(`Missing configuration: ${name}`);
    }
    return value;
  }
  function prefix(name) {
    const value = required(name);
    if (!/^[a-zA-Z0-9][a-zA-Z0-9/_-]*$/.test(value) || value.endsWith('/')) {
      throw new Error(`Invalid S3 prefix: ${name}`);
    }
    return value;
  }
  const config = {
    bucket: required('OUTPUT_BUCKET'),
    database: required('ATHENA_DATABASE'),
    coreTable: required('CORE_TABLE'),
    confinfoTable: required('CONFINFO_TABLE'),
    workgroup: required('ATHENA_WORKGROUP'),
    outputPrefix: prefix('OUTPUT_PREFIX'),
    stagingPrefix: prefix('STAGING_PREFIX'),
    resultsPrefix: prefix('RESULTS_PREFIX'),
    settleSeconds: Number(required('PARTITION_SETTLE_SECONDS')),
  };
  if (!/^[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$/.test(config.bucket)
      || !Number.isInteger(config.settleSeconds) || config.settleSeconds < 0) {
    throw new Error('Invalid output bucket or partition settling period');
  }
  [config.database, config.coreTable, config.confinfoTable].forEach(identifier);
  if (config.coreTable.toLowerCase() === config.confinfoTable.toLowerCase()) {
    throw new Error('CORE and CONFINFO tables must be distinct');
  }
  const prefixes = [config.outputPrefix, config.stagingPrefix, config.resultsPrefix];
  if (prefixes.some((value, i) => prefixes.some((other, j) =>
    i !== j && (value === other || value.startsWith(`${other}/`))))) {
    throw new Error('Published, staging and Athena result prefixes must not overlap');
  }
  if (prefixes.some(value => value === 'downstream-http-call'
      || value.startsWith('downstream-http-call/') || 'downstream-http-call'.startsWith(`${value}/`))) {
    throw new Error('Compaction prefixes must not overlap the downstream JSON source');
  }
  return config;
}

async function previousObject(bucket, key, signal) {
  try {
    const response = await s3.send(new HeadObjectCommand({ Bucket: bucket, Key: key }), { abortSignal: signal });
    if (!response.ETag) {
      throw new Error('S3 did not return the previous object ETag');
    }
    return response.ETag;
  } catch (error) {
    if (error.name === 'NotFound' || error.$metadata?.httpStatusCode === 404) {
      return undefined;
    }
    throw error;
  }
}

async function run(event, context, controller) {
  const config = configuration(process.env);
  const partition = selectPartition(event, new Date(), config.settleSeconds);
  if (!partition) {
    console.log('Skipping the first occurrence of the repeated DST partition: it is still open');
    return { status: 'partition_still_open' };
  }
  const identity = event.mode === 'manual' ? context.awsRequestId : `${event.scheduleArn}:${event.scheduledTime}`;
  if (typeof identity !== 'string' || !identity) {
    throw new Error('Missing execution identity');
  }
  const runId = createHash('sha256').update(`${identity}:${partition.hour}`).digest('hex');
  const stagingPrefix = `${config.stagingPrefix}/${partition.path}/${runId}/`;
  const key = `${config.outputPrefix}/${partition.path}/data.parquet`;
  const previousETag = await previousObject(config.bucket, key, controller.signal);
  const query = buildQuery(config, partition, stagingPrefix);
  const queryId = await executeQuery(athena, config, query, runId, controller.signal);
  const directory = await mkdtemp(join(tmpdir(), 'downstream-compaction-'));
  try {
    async function* inputs() {
      const inputPath = join(directory, 'input.parquet');
      for await (const inputKey of manifestFiles(
        athena, queryId, config.bucket, stagingPrefix, controller.signal,
      )) {
        const { Body: body } = await s3.send(new GetObjectCommand({
          Bucket: config.bucket, Key: inputKey,
        }), { abortSignal: controller.signal });
        if (!body) {
          throw new Error(`S3 returned no body for ${inputKey}`);
        }
        try {
          await pipeline(body, createWriteStream(inputPath), { signal: controller.signal });
          yield inputPath;
        } finally {
          await rm(inputPath, { force: true });
        }
      }
    }
    const outputPath = join(directory, 'data.parquet');
    const rows = await consolidate(inputs(), outputPath, () => controller.signal.throwIfAborted());
    controller.signal.throwIfAborted();
    const { size } = await stat(outputPath);
    await publishFile(s3, outputPath, size, {
      Bucket: config.bucket,
      Key: key,
      ContentType: 'application/vnd.apache.parquet',
      Metadata: { 'compaction-id': runId, 'row-count': String(rows), 'query-id': queryId },
      ...(previousETag ? { IfMatch: previousETag } : { IfNoneMatch: '*' }),
    }, controller.signal);
    console.log(`Published ${rows} rows (${size} bytes) for ${partition.hour}: s3://${config.bucket}/${key}, query ${queryId}`);
    return { status: 'published', partitionHour: partition.hour, key, rows, bytes: size, queryId };
  } finally {
    await rm(directory, { recursive: true, force: true });
  }
}

exports.handler = async (event, context) => {
  const controller = new AbortController();
  const budget = context.getRemainingTimeInMillis() - 10000;
  if (budget <= 0) {
    throw new Error('Insufficient Lambda time remaining');
  }
  const timer = setTimeout(() => controller.abort(new Error('Compaction execution budget exhausted')), budget);
  try {
    return await run(event, context, controller);
  } catch (error) {
    console.error('Downstream compaction failed', error);
    throw error;
  } finally {
    clearTimeout(timer);
  }
};

exports.configuration = configuration;
