'use strict';

const { test } = require('node:test');
const assert = require('node:assert/strict');
const { manifestFiles, executeQuery } = require('../../lib/athena');

test('rejects manifest paths outside the current attempt and duplicate paths', async () => {
  for (const files of [
    ['s3://other-bucket/staging/run/file.parquet'],
    ['s3://bucket/staging/other-run/file.parquet'],
    ['s3://bucket/staging/run/file.parquet', 's3://bucket/staging/run/file.parquet'],
  ]) {
    const client = {
      async send() {
        return { ResultSet: { Rows: files.map(value => ({ Data: [{ VarCharValue: value }] })) } };
      },
    };
    await assert.rejects(async () => {
      for await (const key of manifestFiles(client, 'query', 'bucket', 'staging/run/', new AbortController().signal)) {
        assert.ok(key);
      }
    }, /Invalid or duplicate/);
  }
});

test('a cancelled query is an error and attempts to stop the query', async () => {
  const commands = [];
  const client = {
    async send(command) {
      commands.push(command.constructor.name);
      if (command.constructor.name === 'StartQueryExecutionCommand') return { QueryExecutionId: 'query' };
      if (command.constructor.name === 'GetQueryExecutionCommand') {
        return { QueryExecution: { Status: { State: 'CANCELLED', StateChangeReason: 'fixture' } } };
      }
      return {};
    },
  };
  await assert.rejects(executeQuery(client, { bucket: 'bucket', resultsPrefix: 'results' }, 'query', 'token',
    new AbortController().signal), /CANCELLED/);
  assert.equal(commands.at(-1), 'StopQueryExecutionCommand');
});

test('deadline during polling cancels Athena and surfaces cancellation errors', async () => {
  const controller = new AbortController();
  const client = {
    async send(command) {
      if (command.constructor.name === 'StartQueryExecutionCommand') return { QueryExecutionId: 'query' };
      if (command.constructor.name === 'GetQueryExecutionCommand') {
        controller.abort();
        return { QueryExecution: { Status: { State: 'RUNNING' } } };
      }
      throw new Error('stop failed');
    },
  };
  await assert.rejects(executeQuery(client, { bucket: 'bucket', resultsPrefix: 'results' }, 'query', 'token',
    controller.signal), error => error instanceof AggregateError && error.errors.length === 2);
});
