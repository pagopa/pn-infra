'use strict';

const { createReadStream } = require('node:fs');
const {
  PutObjectCommand, CreateMultipartUploadCommand, UploadPartCommand,
  CompleteMultipartUploadCommand, AbortMultipartUploadCommand,
} = require('@aws-sdk/client-s3');

const PART_SIZE = 8 * 1024 * 1024;

async function publishFile(client, path, size, params, signal) {
  signal.throwIfAborted();
  if (size <= PART_SIZE) {
    const body = createReadStream(path);
    try {
      await client.send(new PutObjectCommand({
        ...params, Body: body, ContentLength: size,
      }), { abortSignal: signal });
    } finally {
      body.destroy();
    }
    return;
  }

  const { IfMatch: ifMatch, IfNoneMatch: ifNoneMatch, ...creation } = params;
  const { UploadId: uploadId } = await client.send(
    new CreateMultipartUploadCommand(creation), { abortSignal: signal },
  );
  if (!uploadId) {
    throw new Error('S3 did not return a multipart upload ID');
  }
  const target = { Bucket: params.Bucket, Key: params.Key, UploadId: uploadId };
  try {
    const parts = [];
    for await (const body of createReadStream(path, { highWaterMark: PART_SIZE })) {
      signal.throwIfAborted();
      const partNumber = parts.length + 1;
      const response = await client.send(new UploadPartCommand({
        ...target, PartNumber: partNumber, Body: body, ContentLength: body.length,
      }), { abortSignal: signal });
      if (!response.ETag) {
        throw new Error(`S3 did not return an ETag for part ${partNumber}`);
      }
      parts.push({ ETag: response.ETag, PartNumber: partNumber });
    }
    signal.throwIfAborted();
    await client.send(new CompleteMultipartUploadCommand({
      ...target, IfMatch: ifMatch, IfNoneMatch: ifNoneMatch, MultipartUpload: { Parts: parts },
    }), { abortSignal: signal });
  } catch (error) {
    try {
      await client.send(new AbortMultipartUploadCommand(target), {
        abortSignal: AbortSignal.timeout(3000),
      });
    } catch (abortError) {
      throw new AggregateError([error, abortError], 'Publishing failed and multipart upload could not be aborted');
    }
    throw error;
  }
}

module.exports = { publishFile };
