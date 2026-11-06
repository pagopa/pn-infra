const assert = require('node:assert/strict');
const { gzipSync } = require('node:zlib');
const { test } = require('node:test');

process.env.MONITORING_BUCKET_NAME = 'test-bucket/downstream-http-call';
const s3 = require('../../lib/s3');
const context = { getRemainingTimeInMillis: () => 60000 };

function event(messages) {
    const payload = {
        logGroup: 'test-group',
        logStream: 'test-stream',
        logEvents: messages.map(message => ({ message })),
    };
    return { awslogs: { data: gzipSync(JSON.stringify(payload)).toString('base64') } };
}

function loadHandler() {
    delete require.cache[require.resolve('../../index')];
    return require('../../index').handler;
}

test('valid records are uploaded together as NDJSON with the existing partition layout', async t => {
    const upload = t.mock.method(s3, 'uploadFileToS3', async () => {});
    const handler = loadHandler();
    const records = [{ destination: 'first', duration: 123 }, { destination: 'second', duration: 456 }];
    await handler(event(records.map(record => JSON.stringify({ message: JSON.stringify(record) }))), context);
    assert.equal(upload.mock.callCount(), 1);
    const [bucket, key, body, remaining] = upload.mock.calls[0].arguments;
    assert.equal(bucket, 'test-bucket');
    assert.match(key, /^downstream-http-call\/\d{4}\/\d{2}\/\d{2}\/\d{2}\/[a-f0-9-]+\.json$/);
    assert.equal(body, records.map(record => JSON.stringify(record)).join('\n'));
    assert.equal(remaining, 60000);
});

test('empty batches do not upload', async t => {
    const upload = t.mock.method(s3, 'uploadFileToS3', async () => {});
    await loadHandler()(event([]), context);
    assert.equal(upload.mock.callCount(), 0);
});

test('invalid JSON retains the existing skip behavior without discarding valid records', async t => {
    const upload = t.mock.method(s3, 'uploadFileToS3', async () => {});
    const valid = { destination: 'valid' };
    await loadHandler()(event(['not-json', JSON.stringify({ message: JSON.stringify(valid) })]), context);
    assert.equal(upload.mock.callCount(), 1);
    assert.equal(upload.mock.calls[0].arguments[2], JSON.stringify(valid));
});

test('upload failures propagate instead of returning success', async t => {
    const error = new Error('upload failed');
    t.mock.method(s3, 'uploadFileToS3', async () => { throw error; });
    const message = JSON.stringify({ message: JSON.stringify({ destination: 'test' }) });
    await assert.rejects(loadHandler()(event([message]), context), failure => failure === error);
});

test('invalid compressed data fails before uploading', async t => {
    const upload = t.mock.method(s3, 'uploadFileToS3', async () => {});
    await assert.rejects(loadHandler()({ awslogs: { data: 'invalid' } }, context));
    assert.equal(upload.mock.callCount(), 0);
});
