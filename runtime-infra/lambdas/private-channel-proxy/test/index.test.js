const assert = require("node:assert/strict");
const { test } = require("node:test");

const { createHandler } = require("../index");

const traceId = "Root=1-67891233-abcdef012345678912345678;Parent=53995c3f42cd8ad8;Sampled=1";

const baseEnv = {
  PRIVATE_CHANNEL_PROXY_ALLOWED_PATH_PATTERNS: "/foo/*,/bar/*",
  PRIVATE_CHANNEL_PROXY_BACKEND_BASE_URL: "http://backend.internal:8080",
  PRIVATE_CHANNEL_PROXY_EXTERNAL_PROTOCOL: "https",
  PRIVATE_CHANNEL_PROXY_EXTERNAL_PORT: "443",
  PRIVATE_CHANNEL_PROXY_TRUSTED_HEADERS: JSON.stringify({
    "x-pagopa-pn-cx-id": "trusted-cx-id",
    "x-pagopa-pn-cx-type": "PF"
  }),
  PRIVATE_CHANNEL_PROXY_REQUEST_PAYLOAD_LOGGING_ENABLED: "false",
  PRIVATE_CHANNEL_PROXY_RESPONSE_PAYLOAD_LOGGING_ENABLED: "false",
  _X_AMZN_TRACE_ID: traceId
};

function buildEvent(overrides = {}) {
  return {
    httpMethod: "POST",
    path: "/bar/resource",
    headers: {
      host: "example.internal",
      connection: "close",
      "x-pagopa-pn-cx-id": "caller-cx-id",
      "x-pagopa-pn-base-url": "https://caller.example"
    },
    multiValueHeaders: null,
    queryStringParameters: null,
    multiValueQueryStringParameters: null,
    body: JSON.stringify({ ok: true }),
    isBase64Encoded: false,
    ...overrides
  };
}

test("forwards requests with trusted header enforcement and runtime trace propagation", async () => {
  let capturedUrl;
  let capturedOptions;
  const handler = createHandler({
    env: baseEnv,
    fetchImpl: async (url, options) => {
      capturedUrl = url;
      capturedOptions = options;

      return new Response(JSON.stringify({ ok: true }), {
        status: 201,
        statusText: "Created",
        headers: {
          "content-type": "application/json"
        }
      });
    }
  });

  const response = await handler(buildEvent());

  assert.equal(capturedUrl, "http://backend.internal:8080/bar/resource");
  assert.equal(capturedOptions.method, "POST");
  assert.equal(capturedOptions.headers["x-pagopa-pn-cx-id"], "trusted-cx-id");
  assert.equal(capturedOptions.headers["x-pagopa-pn-cx-type"], "PF");
  assert.equal(capturedOptions.headers["x-pagopa-pn-base-url"], "https://example.internal");
  assert.equal(capturedOptions.headers["x-amzn-trace-id"], traceId);
  assert.equal(capturedOptions.headers.connection, undefined);

  assert.equal(response.statusCode, 201);
  assert.deepEqual(response.multiValueHeaders["content-type"], ["application/json"]);
  assert.deepEqual(response.multiValueHeaders["x-amzn-trace-id"], [traceId]);
});

test("rejects paths outside the configured multi-path allowlist", async () => {
  let fetchCalled = false;
  const handler = createHandler({
    env: baseEnv,
    fetchImpl: async () => {
      fetchCalled = true;
      return new Response(JSON.stringify({ ok: true }));
    }
  });

  const response = await handler(buildEvent({ path: "/baz/resource" }));

  assert.equal(fetchCalled, false);
  assert.equal(response.statusCode, 403);
  assert.deepEqual(response.multiValueHeaders["content-type"], ["application/json"]);
  assert.deepEqual(response.multiValueHeaders["x-amzn-trace-id"], [traceId]);
  assert.deepEqual(JSON.parse(response.body), { message: "Forbidden" });
});

test("leaves trusted header enforcement disabled when the configuration is empty", async () => {
  let capturedOptions;
  const handler = createHandler({
    env: {
      ...baseEnv,
      PRIVATE_CHANNEL_PROXY_ALLOWED_PATH_PATTERNS: "/foo/*",
      PRIVATE_CHANNEL_PROXY_TRUSTED_HEADERS: "{}"
    },
    fetchImpl: async (url, options) => {
      capturedOptions = options;

      return new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: {
          "content-type": "application/json"
        }
      });
    }
  });

  await handler(buildEvent({
    path: "/foo/resource",
    headers: {
      host: "example.internal",
      "x-pagopa-pn-cx-id": "caller-cx-id"
    }
  }));

  assert.equal(capturedOptions.headers["x-pagopa-pn-cx-id"], "caller-cx-id");
  assert.equal(capturedOptions.headers["x-amzn-trace-id"], traceId);
});
