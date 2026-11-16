'use strict';

const { test } = require('node:test');
const assert = require('node:assert/strict');
const { mkdtemp, rm } = require('node:fs/promises');
const { tmpdir } = require('node:os');
const { join } = require('node:path');
const { ParquetReader, ParquetWriter } = require('@dsnp/parquetjs');
const { SCHEMA, consolidate } = require('../../lib/parquet');

test('consolidates multiple files preserving duplicates, nulls and exact INT64 values', async () => {
  const directory = await mkdtemp(join(tmpdir(), 'downstream-test-'));
  try {
    const inputs = [join(directory, 'core.parquet'), join(directory, 'confinfo.parquet')];
    const record = {
      eventType: 'HTTP_CALL',
      timestamp: '2026-11-04T10:01:00+01:00',
      clientName: 'fixture',
      method: 'GET',
      url: '/fixture',
      host: 'fixture.invalid',
      status: 200,
      success: false,
      outcome: null,
      durationMs: 9007199254740993n,
      errorType: null,
      errorMessage: null,
    };
    for (const path of inputs) {
      const writer = await ParquetWriter.openFile(SCHEMA, path);
      await writer.appendRow(record);
      await writer.close();
    }

    const output = join(directory, 'output.parquet');
    assert.equal(await consolidate(inputs, output), 2);
    const reader = await ParquetReader.openFile(output);
    try {
      const cursor = reader.getCursor();
      assert.deepEqual(await cursor.next(), record);
      assert.deepEqual(await cursor.next(), record);
      assert.equal(await cursor.next(), null);
    } finally {
      await reader.close();
    }
  } finally {
    await rm(directory, { recursive: true, force: true });
  }
});

test('writes a valid empty Parquet with the downstream schema', async () => {
  const directory = await mkdtemp(join(tmpdir(), 'downstream-test-'));
  try {
    const output = join(directory, 'empty.parquet');
    assert.equal(await consolidate([], output), 0);
    const reader = await ParquetReader.openFile(output);
    try {
      assert.deepEqual(Object.keys(reader.schema.fields), Object.keys(SCHEMA.fields));
      assert.equal(await reader.getCursor().next(), null);
    } finally {
      await reader.close();
    }
  } finally {
    await rm(directory, { recursive: true, force: true });
  }
});
