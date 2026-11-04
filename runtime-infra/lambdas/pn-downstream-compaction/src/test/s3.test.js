'use strict';

const { test } = require('node:test');
const assert = require('node:assert/strict');
const { mkdtemp, writeFile, rm } = require('node:fs/promises');
const { join } = require('node:path');
const { tmpdir } = require('node:os');
const { publishFile } = require('../../lib/s3');

async function largeFile(t) {
  const directory = await mkdtemp(join(tmpdir(), 'downstream-upload-test-'));
  t.after(() => rm(directory, { recursive: true, force: true }));
  const path = join(directory, 'file.parquet');
  const body = Buffer.alloc(8 * 1024 * 1024 + 1, 7);
  await writeFile(path, body);
  return { path, size: body.length };
}

test('multipart upload replaces the same key only on completion and retains the ETag precondition', async t => {
  const file = await largeFile(t);
  const commands = [];
  const client = {
    async send(command, options) {
      assert.ok(options.abortSignal);
      commands.push(command);
      if (command.constructor.name === 'CreateMultipartUploadCommand') return { UploadId: 'upload' };
      if (command.constructor.name === 'UploadPartCommand') return { ETag: `part-${command.input.PartNumber}` };
      assert.equal(command.constructor.name, 'CompleteMultipartUploadCommand');
      return {};
    },
  };
  await publishFile(client, file.path, file.size, { Bucket: 'bucket', Key: 'hour.parquet', IfMatch: '"previous"' },
    new AbortController().signal);
  assert.equal(commands.length, 4);
  const complete = commands.at(-1).input;
  assert.equal(complete.Key, 'hour.parquet');
  assert.equal(complete.IfMatch, '"previous"');
  assert.equal(complete.MultipartUpload.Parts.length, 2);
});

test('failed multipart upload is aborted without completing or deleting the previous object', async t => {
  const file = await largeFile(t);
  const commands = [];
  const client = {
    async send(command) {
      commands.push(command.constructor.name);
      if (command.constructor.name === 'CreateMultipartUploadCommand') return { UploadId: 'upload' };
      if (command.constructor.name === 'UploadPartCommand') throw new Error('upload failed');
      assert.equal(command.constructor.name, 'AbortMultipartUploadCommand');
      return {};
    },
  };
  await assert.rejects(publishFile(client, file.path, file.size, { Bucket: 'bucket', Key: 'hour.parquet' },
    new AbortController().signal), /upload failed/);
  assert.deepEqual(commands, ['CreateMultipartUploadCommand', 'UploadPartCommand', 'AbortMultipartUploadCommand']);
});

test('exposes multipart cleanup failures as well as the original error', async t => {
  const file = await largeFile(t);
  const client = {
    async send(command) {
      if (command.constructor.name === 'CreateMultipartUploadCommand') return { UploadId: 'upload' };
      throw new Error(command.constructor.name);
    },
  };
  await assert.rejects(publishFile(client, file.path, file.size, { Bucket: 'bucket', Key: 'hour.parquet' },
    new AbortController().signal), error => error instanceof AggregateError && error.errors.length === 2);
});
