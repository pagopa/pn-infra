'use strict';

const zlib = require('zlib');
const { promisify } = require('util');
const { randomUUID } = require('crypto');
const { uploadFileToS3 } = require('./lib/s3');

const gunzip = promisify(zlib.gunzip);

// MONITORING_BUCKET_NAME is in the form "<bucket-name>/<prefix>"
const [BUCKET_NAME, ...prefixParts] = process.env.MONITORING_BUCKET_NAME.split('/');
const KEY_PREFIX = prefixParts.join('/');

/**
 * Decodes and decompresses the CloudWatch Logs subscription filter payload.
 * @param {string} data - base64-encoded, gzip-compressed JSON
 * @returns {Promise<object>} parsed CloudWatch Logs data
 */
async function decodeLogData(data) {
  const compressed = Buffer.from(data, 'base64');
  const decompressed = await gunzip(compressed);
  return JSON.parse(decompressed.toString('utf-8'));
}

/**
 * Builds the S3 key for the given timestamp.
 * Path: <prefix>/<year>/<MM>/<DD>/<HH>/<uuid>.json
 * @param {Date} date
 * @returns {string}
 */
function buildS3Key(date) {
  const year  = date.getUTCFullYear();
  const month = String(date.getUTCMonth() + 1).padStart(2, '0');
  const day   = String(date.getUTCDate()).padStart(2, '0');
  const hour  = String(date.getUTCHours()).padStart(2, '0');
  const prefix = KEY_PREFIX ? `${KEY_PREFIX}/` : '';
  return `${prefix}${year}/${month}/${day}/${hour}/${randomUUID()}.json`;
}

exports.handler = async (event) => {
  const logData = await decodeLogData(event.awslogs.data);

  console.log(`Processing log group: ${logData.logGroup}, stream: ${logData.logStream}, events: ${logData.logEvents.length}`);

  const records = [];
  for (const logEvent of logData.logEvents) {
    try {
      const parsed = JSON.parse(logEvent.message);
      records.push(JSON.parse(parsed.message));
    } catch (err) {
      console.error('Skipping non-JSON log event:', logEvent.message, err.message);
    }
  }

  if (records.length === 0) {
    console.log('No JSON records to write, skipping S3 upload.');
    return;
  }

  const partitionDate = logData.logEvents[0]?.timestamp
    ? new Date(logData.logEvents[0].timestamp)
    : new Date();

  const key  = buildS3Key(partitionDate);
  const body = records.map(r => JSON.stringify(r)).join('\n');

  await uploadFileToS3(BUCKET_NAME, key, body);
  console.log(`Written ${records.length} record(s) to s3://${BUCKET_NAME}/${key}`);
};
