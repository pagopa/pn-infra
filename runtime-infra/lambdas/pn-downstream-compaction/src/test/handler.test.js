'use strict';

const { test, mock } = require('node:test');
const assert = require('node:assert/strict');
const { Readable } = require('node:stream');
const { mkdtemp, readFile, rm } = require('node:fs/promises');
const { join } = require('node:path');
const { tmpdir } = require('node:os');
const { createHash } = require('node:crypto');
const { AthenaClient } = require('@aws-sdk/client-athena');
const { S3Client } = require('@aws-sdk/client-s3');
const { ParquetReader, ParquetWriter } = require('@dsnp/parquetjs');
const { SCHEMA } = require('../../lib/parquet');
const { handler, configuration } = require('../../index');

const ENV = {
  OUTPUT_BUCKET: 'fixture-monitoring',
  ATHENA_DATABASE: 'monitoring_database',
  CORE_TABLE: 'downstream_monitoring_core',
  CONFINFO_TABLE: 'downstream_monitoring_confinfo',
  ATHENA_WORKGROUP: 'primary',
  OUTPUT_PREFIX: 'downstream-compacted',
  STAGING_PREFIX: 'downstream-staging',
  RESULTS_PREFIX: 'query-results',
  PARTITION_SETTLE_SECONDS: '120',
};
const EVENT = { mode: 'manual', partitionHour: '2026-01-01T10' };
const context = id => ({ awsRequestId: id, getRemainingTimeInMillis: () => 900000 });
const etag = buffer => `"${createHash('sha256').update(buffer).digest('hex')}"`;

async function fixture(t) {
  const directory = await mkdtemp(join(tmpdir(), 'downstream-handler-test-'));
  const originalEnv = Object.fromEntries(Object.keys(ENV).map(key => [key, process.env[key]]));
  Object.assign(process.env, ENV);
  t.after(async () => {
    mock.restoreAll();
    for (const [key, value] of Object.entries(originalEnv)) {
      if (value === undefined) delete process.env[key];
      else process.env[key] = value;
    }
    await rm(directory, { recursive: true, force: true });
  });
  const records = [
    { eventType: 'CORE', status: 200, durationMs: 9007199254740993n },
    { eventType: 'CONFINFO', status: 503, success: false, errorMessage: 'fixture error' },
  ];
  const buffers = [];
  for (const [index, record] of records.entries()) {
    const path = join(directory, `${index}.parquet`);
    const writer = await ParquetWriter.openFile(SCHEMA, path);
    await writer.appendRow(record);
    await writer.close();
    buffers.push(await readFile(path));
  }
  const state = { final: new Map(), queries: [], failure: undefined, empty: false, corrupt: false, puts: [] };
  mock.method(AthenaClient.prototype, 'send', async command => {
    const input = command.input;
    switch (command.constructor.name) {
      case 'StartQueryExecutionCommand': {
        assert.match(input.QueryString, /UNION ALL/);
        assert.match(input.QueryString, /"monitoring_database"."downstream_monitoring_core"/);
        assert.match(input.QueryString, /"monitoring_database"."downstream_monitoring_confinfo"/);
        assert.equal((input.QueryString.match(/"hour" = '10'/g) || []).length, 2);
        assert.equal(input.ClientRequestToken.length, 64);
        const prefix = input.QueryString.match(/TO 's3:\/\/fixture-monitoring\/([^']+)'/)[1];
        state.queries.push({ id: `query-${state.queries.length + 1}`, prefix });
        return { QueryExecutionId: state.queries.at(-1).id };
      }
      case 'GetQueryExecutionCommand':
        return { QueryExecution: { Status: { State: state.failure || 'SUCCEEDED', StateChangeReason: 'fixture' } } };
      case 'StopQueryExecutionCommand': return {};
      case 'GetQueryResultsCommand': {
        const query = state.queries.find(candidate => candidate.id === input.QueryExecutionId);
        const index = input.NextToken ? 1 : 0;
        const rows = state.empty ? [] : [{ Data: [{ VarCharValue: `s3://fixture-monitoring/${query.prefix}${index}.parquet` }] }];
        if (!input.NextToken) rows.unshift({ Data: [{ VarCharValue: 'file_path' }] });
        return {
          ResultSet: { ResultSetMetadata: { ColumnInfo: [{ Name: 'file_path' }] }, Rows: rows },
          ...(!state.empty && !input.NextToken ? { NextToken: 'second-file' } : {}),
        };
      }
      default: throw new Error(`Unexpected Athena command: ${command.constructor.name}`);
    }
  });
  mock.method(S3Client.prototype, 'send', async command => {
    const input = command.input;
    switch (command.constructor.name) {
      case 'HeadObjectCommand': {
        if (!state.final.has(input.Key)) throw Object.assign(new Error('missing'), { name: 'NotFound' });
        return { ETag: etag(state.final.get(input.Key)) };
      }
      case 'GetObjectCommand':
        return { Body: Readable.from(state.corrupt ? Buffer.from('not parquet') : buffers[Number(input.Key.at(-9))]) };
      case 'PutObjectCommand': {
        const previous = state.final.get(input.Key);
        assert.equal(input.IfMatch, previous ? etag(previous) : undefined);
        assert.equal(input.IfNoneMatch, previous ? undefined : '*');
        const chunks = [];
        for await (const chunk of input.Body) chunks.push(chunk);
        state.final.set(input.Key, Buffer.concat(chunks));
        state.puts.push(input);
        return { ETag: etag(state.final.get(input.Key)) };
      }
      default: throw new Error(`Unexpected S3 command: ${command.constructor.name}`);
    }
  });
  return state;
}

async function readRecords(buffer) {
  const reader = await ParquetReader.openBuffer(buffer);
  try {
    const rows = [];
    const cursor = reader.getCursor();
    for (let row = await cursor.next(); row !== null; row = await cursor.next()) rows.push(row);
    return rows;
  } finally {
    await reader.close();
  }
}

test('publishes exactly one file combining both domains and replaces the same key on manual rerun', async t => {
  const state = await fixture(t);
  const first = await handler(EVENT, context('first-request'));
  const second = await handler(EVENT, context('manual-rerun'));
  assert.equal(first.key, 'downstream-compacted/2026/01/01/10/data.parquet');
  assert.equal(second.key, first.key);
  assert.equal(state.final.size, 1);
  const records = await readRecords(state.final.get(first.key));
  assert.deepEqual(records.map(row => row.eventType), ['CORE', 'CONFINFO']);
  assert.equal(records[0].durationMs, 9007199254740993n);
  assert.equal(records[1].success, false);
  assert.equal(first.rows, 2);
  assert.equal(second.rows, 2);
  assert.equal(state.puts.length, 2);
  assert.notEqual(state.puts[0].Metadata['compaction-id'], state.puts[1].Metadata['compaction-id']);
});

test('Athena failure or corrupt intermediate file does not replace the previous result', async t => {
  const state = await fixture(t);
  const first = await handler(EVENT, context('first'));
  const previous = state.final.get(first.key);
  state.failure = 'FAILED';
  await assert.rejects(handler(EVENT, context('query-fails')), /FAILED/);
  assert.equal(state.final.get(first.key), previous);
  state.failure = undefined;
  state.corrupt = true;
  await assert.rejects(handler(EVENT, context('corrupt-input')));
  assert.equal(state.final.get(first.key), previous);
  assert.equal(state.puts.length, 1);
});

test('zero rows replaces an old nonempty file with a valid empty Parquet', async t => {
  const state = await fixture(t);
  const first = await handler(EVENT, context('nonempty'));
  state.empty = true;
  const second = await handler(EVENT, context('empty'));
  assert.equal(second.key, first.key);
  assert.equal(state.final.size, 1);
  assert.deepEqual(await readRecords(state.final.get(second.key)), []);
  assert.equal(second.rows, 0);
});

test('Scheduler context selects the nominal hour and keeps a stable identity across delivery attempts', async t => {
  const state = await fixture(t);
  const event = {
    mode: 'scheduled',
    scheduleArn: 'arn:aws:scheduler:eu-south-1:123456789012:schedule/default/pn-downstream-compaction',
    scheduledTime: '2026-01-01T10:05:00Z',
  };
  const first = await handler(event, context('delivery-1'));
  const second = await handler(event, context('delivery-2'));
  assert.equal(first.partitionHour, '2026-01-01T10');
  assert.equal(second.key, first.key);
  assert.equal(state.final.size, 1);
  assert.equal(state.puts[0].Metadata['compaction-id'], state.puts[1].Metadata['compaction-id']);
});

test('rejects invalid configuration, overlapping prefixes and implicit manual hours', async t => {
  await fixture(t);
  assert.throws(() => configuration({ ...ENV, CORE_TABLE: ENV.CONFINFO_TABLE }), /distinct/);
  assert.throws(() => configuration({ ...ENV, STAGING_PREFIX: `${ENV.OUTPUT_PREFIX}/staging` }), /overlap/);
  assert.throws(() => configuration({ ...ENV, OUTPUT_PREFIX: 'downstream-http-call/parquet' }), /JSON source/);
  assert.throws(() => configuration({ ...ENV, OUTPUT_BUCKET: "bad'bucket" }), /Invalid/);
  assert.throws(() => configuration({ ...ENV, ATHENA_DATABASE: 'bad-name' }), /identifier/);
  await assert.rejects(handler({ mode: 'manual' }, context('invalid')), /partitionHour/);
});
