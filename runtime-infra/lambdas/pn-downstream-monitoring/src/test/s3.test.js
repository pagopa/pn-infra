const assert = require('node:assert/strict');
const http = require('node:http');
const { before, after, beforeEach, test } = require('node:test');

process.env.AWS_REGION = 'eu-west-1';
process.env.AWS_ACCESS_KEY_ID = 'local-test';
process.env.AWS_SECRET_ACCESS_KEY = 'local-test';
process.env.AWS_EC2_METADATA_DISABLED = 'true';

let responses;
let requests;
const server = http.createServer(async (request, response) => {
    const chunks = [];
    for await (const chunk of request) {
        chunks.push(chunk);
    }
    requests.push({ path: request.url, body: Buffer.concat(chunks).toString() });
    const status = responses.shift() ?? 200;
    if (status === 'hang') {
        return;
    }
    response.setHeader('Connection', 'close');
    response.setHeader('x-amz-request-id', 'local-request');
    if (status === 200) {
        response.writeHead(200).end();
    } else {
        response.setHeader('Content-Type', 'application/xml');
        const code = status === 503 ? 'SlowDown' : 'AccessDenied';
        response.writeHead(status).end(`<Error><Code>${code}</Code><Message>${code}</Message></Error>`);
    }
});

before(async () => {
    await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
    process.env.AWS_ENDPOINT_URL_S3 = `http://127.0.0.1:${server.address().port}`;
});

after(async () => {
    server.closeAllConnections();
    await new Promise((resolve, reject) => server.close(error => error ? reject(error) : resolve()));
});

beforeEach(() => {
    responses = [];
    requests = [];
});

function loadUpload(settings = {}) {
    process.env.S3_MAX_RETRIES = '3';
    process.env.S3_UPLOAD_BUDGET_SECONDS = '45';
    Object.assign(process.env, settings);
    delete require.cache[require.resolve('../../lib/s3')];
    return require('../../lib/s3').uploadFileToS3;
}

test('three SlowDown responses are retried with identical key and body, then succeed', async () => {
    responses = [503, 503, 503, 200];
    const upload = loadUpload();
    const result = await upload('test-bucket', 'prefix/batch.json', '{"value":1}', 60000);
    assert.equal(result.$metadata.attempts, 4);
    assert.equal(requests.length, 4);
    assert.equal(typeof result.$metadata.totalRetryDelay, 'number');
    for (const request of requests) {
        assert.deepEqual(request, { path: '/test-bucket/prefix/batch.json?x-id=PutObject', body: '{"value":1}' });
    }
});

test('persistent SlowDown fails after one attempt and three retries', async () => {
    responses = [503, 503, 503, 503];
    const upload = loadUpload();
    await assert.rejects(upload('test-bucket', 'batch.json', 'data', 60000), error => {
        assert.equal(error.name, 'SlowDown');
        assert.equal(error.$metadata.attempts, 4);
        return true;
    });
    assert.equal(requests.length, 4);
});

test('zero retries makes exactly one attempt', async () => {
    responses = [503];
    const upload = loadUpload({ S3_MAX_RETRIES: '0' });
    await assert.rejects(upload('test-bucket', 'batch.json', 'data', 60000), error => {
        assert.equal(error.$metadata.attempts, 1);
        return true;
    });
    assert.equal(requests.length, 1);
});

test('non-retryable errors fail without additional attempts', async () => {
    responses = [403];
    const upload = loadUpload();
    await assert.rejects(upload('test-bucket', 'batch.json', 'data', 60000), error => {
        assert.equal(error.name, 'AccessDenied');
        assert.equal(error.$metadata.attempts, 1);
        return true;
    });
    assert.equal(requests.length, 1);
});

test('configured upload budget interrupts a stalled request', async () => {
    responses = ['hang'];
    const upload = loadUpload({ S3_UPLOAD_BUDGET_SECONDS: '1' });
    const started = Date.now();
    await assert.rejects(upload('test-bucket', 'batch.json', 'data', 60000), {
        name: 'UploadDeadlineExceededError',
    });
    assert.ok(Date.now() - started < 2000, 'request must not wait for the Lambda timeout');
    assert.equal(requests.length, 1);
});

test('remaining Lambda time shortens the budget and reserves five seconds', async () => {
    responses = ['hang'];
    const upload = loadUpload();
    const started = Date.now();
    await assert.rejects(upload('test-bucket', 'batch.json', 'data', 5100), {
        name: 'UploadDeadlineExceededError',
        message: 'S3 upload exceeded its 100 ms budget',
    });
    assert.ok(Date.now() - started < 1000);
});

test('deadline also bounds retry backoff', async t => {
    responses = [503, 503, 503, 503];
    t.mock.method(Math, 'random', () => 1);
    const upload = loadUpload();
    const started = Date.now();
    await assert.rejects(upload('test-bucket', 'batch.json', 'data', 5100), {
        name: 'UploadDeadlineExceededError',
    });
    assert.equal(requests.length, 1, 'the first 503 must arrive before the deadline during backoff');
    assert.ok(Date.now() - started >= 80);
    assert.ok(Date.now() - started < 1000);
});

test('insufficient or invalid remaining time fails without sending a PUT', async () => {
    const upload = loadUpload();
    for (const remaining of [0, 5000, -1, NaN, undefined]) {
        await assert.rejects(upload('test-bucket', 'batch.json', 'data', remaining), /Insufficient Lambda time/);
    }
    assert.equal(requests.length, 0);
});

test('invalid retry and budget configuration fails explicitly', () => {
    for (const value of ['', '-1', '1.5', '4', 'NaN']) {
        assert.throws(() => loadUpload({ S3_MAX_RETRIES: value }), /S3_MAX_RETRIES must be an integer/);
    }
    for (const value of ['', '0', '-1', '1.5', '901', 'NaN']) {
        assert.throws(() => loadUpload({ S3_UPLOAD_BUDGET_SECONDS: value }), /S3_UPLOAD_BUDGET_SECONDS must be an integer/);
    }
});
