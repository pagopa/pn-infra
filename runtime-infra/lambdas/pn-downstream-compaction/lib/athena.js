'use strict';

const {
  StartQueryExecutionCommand, GetQueryExecutionCommand, StopQueryExecutionCommand, GetQueryResultsCommand,
} = require('@aws-sdk/client-athena');
const { setTimeout: sleep } = require('node:timers/promises');
const { COLUMNS } = require('./parquet');

function identifier(value) {
  if (typeof value !== 'string' || !/^[a-zA-Z_][a-zA-Z0-9_]*$/.test(value)) {
    throw new Error(`Invalid Athena identifier: ${value}`);
  }
  return `"${value}"`;
}

function buildQuery(config, partition, stagingPrefix) {
  const columns = Object.keys(COLUMNS).map(identifier).join(', ');
  const predicate = ['year', 'month', 'day', 'hour']
    .map((key, index) => `${identifier(key)} = '${partition.values[index]}'`).join(' AND ');
  const sources = [config.coreTable, config.confinfoTable].map(table =>
    `SELECT ${columns} FROM ${identifier(config.database)}.${identifier(table)} WHERE ${predicate}`);
  return `UNLOAD (${sources.join(' UNION ALL ')}) TO 's3://${config.bucket}/${stagingPrefix}' `
    + "WITH (format = 'PARQUET', compression = 'SNAPPY')";
}

async function executeQuery(client, config, query, token, signal) {
  const response = await client.send(new StartQueryExecutionCommand({
    QueryString: query,
    ClientRequestToken: token,
    WorkGroup: config.workgroup,
    QueryExecutionContext: { Database: config.database },
    ResultConfiguration: { OutputLocation: `s3://${config.bucket}/${config.resultsPrefix}/` },
  }), { abortSignal: signal });
  const queryId = response.QueryExecutionId;
  if (!queryId) {
    throw new Error('Athena did not return a QueryExecutionId');
  }
  console.log(`Athena query ${queryId} started`);
  try {
    while (true) {
      const { QueryExecution: execution } = await client.send(
        new GetQueryExecutionCommand({ QueryExecutionId: queryId }), { abortSignal: signal },
      );
      const state = execution?.Status?.State;
      if (state === 'SUCCEEDED') {
        return queryId;
      }
      if (state === 'FAILED' || state === 'CANCELLED') {
        throw new Error(`Athena ${queryId} ${state}: ${execution.Status.StateChangeReason || 'no reason supplied'}`);
      }
      if (state !== 'RUNNING' && state !== 'QUEUED') {
        throw new Error(`Unexpected Athena state for ${queryId}: ${state}`);
      }
      await sleep(2000, undefined, { signal });
    }
  } catch (error) {
    try {
      await client.send(new StopQueryExecutionCommand({ QueryExecutionId: queryId }), {
        abortSignal: AbortSignal.timeout(3000),
      });
    } catch (stopError) {
      throw new AggregateError([error, stopError], `Query ${queryId} failed and could not be stopped`);
    }
    throw error;
  }
}

async function* manifestFiles(client, queryId, bucket, prefix, signal) {
  let token;
  let firstRow = true;
  const seen = new Set();
  do {
    const response = await client.send(new GetQueryResultsCommand({
      QueryExecutionId: queryId, QueryResultType: 'DATA_MANIFEST', MaxResults: 1000, NextToken: token,
    }), { abortSignal: signal });
    const rows = response.ResultSet?.Rows;
    if (!Array.isArray(rows)) {
      throw new Error('Athena did not return a data manifest');
    }
    const columnName = response.ResultSet.ResultSetMetadata?.ColumnInfo?.[0]?.Name;
    for (const row of rows) {
      const value = row.Data?.[0]?.VarCharValue;
      if (firstRow && columnName && value === columnName) {
        firstRow = false;
        continue;
      }
      firstRow = false;
      const expected = `s3://${bucket}/${prefix}`;
      if (row.Data?.length !== 1 || typeof value !== 'string' || !value.startsWith(expected)
          || value.length === expected.length || seen.has(value)) {
        throw new Error(`Invalid or duplicate file in Athena manifest for ${queryId}`);
      }
      seen.add(value);
      yield value.slice(`s3://${bucket}/`.length);
    }
    token = response.NextToken;
  } while (token);
}

module.exports = { buildQuery, executeQuery, identifier, manifestFiles };
