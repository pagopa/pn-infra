const assert = require("node:assert/strict");
const { test } = require("node:test");

const {
  buildAlbResponse,
  buildForwardHeaders,
  buildQueryString,
  buildRequestBody,
  collectHeaders,
  decodeQueryComponent,
  filterResponseHeaders,
  isTextualResponse
} = require("../src/app/http");

test("collects headers from single and multi-value ALB events", () => {
  const headers = collectHeaders({
    headers: {
      Host: "example.internal",
      Cookie: "a=1"
    },
    multiValueHeaders: {
      Cookie: ["a=1", "b=2"],
      "X-Custom": ["one", "two"]
    }
  });

  assert.deepEqual(headers, {
    host: "example.internal",
    cookie: "a=1; b=2",
    "x-custom": "one,two"
  });
});

test("builds forward headers by dropping non-forwardable and trusted caller headers", () => {
  const forwardHeaders = buildForwardHeaders(
    {
      host: "example.internal",
      connection: "close",
      "x-pagopa-pn-base-url": "https://caller.example",
      "x-pagopa-pn-cx-id": "caller-cx-id",
      "x-allowed": "value"
    },
    {
      trustedHeaders: {
        "x-pagopa-pn-cx-id": "trusted-cx-id",
        "x-pagopa-pn-cx-type": "PF"
      }
    },
    "https://example.internal"
  );

  assert.deepEqual(forwardHeaders, {
    host: "example.internal",
    "x-allowed": "value",
    "x-pagopa-pn-cx-id": "trusted-cx-id",
    "x-pagopa-pn-cx-type": "PF",
    "x-pagopa-pn-base-url": "https://example.internal"
  });
});

test("builds query string and request body from ALB event", () => {
  assert.equal(
    buildQueryString({
      multiValueQueryStringParameters: {
        foo: ["one", "two"],
        bar: ["three"]
      }
    }),
    "?foo=one&foo=two&bar=three"
  );

  assert.equal(buildRequestBody({ body: "plain" }, "POST"), "plain");
  assert.equal(buildRequestBody({ body: "plain" }, "GET"), undefined);
  assert.deepEqual(buildRequestBody({ body: Buffer.from("plain").toString("base64"), isBase64Encoded: true }, "POST"), Buffer.from("plain"));
});

test("encodes query string keys and values safely", () => {
  assert.equal(
    buildQueryString({
      queryStringParameters: {
        "a b": "hello world",
        filter: "x&y=z"
      }
    }),
    "?a+b=hello+world&filter=x%26y%3Dz"
  );
});

test("decodes ALB query string components before forwarding them", () => {
  assert.equal(decodeQueryComponent("hello+world"), "hello world");
  assert.equal(decodeQueryComponent("x%26y%3Dz"), "x&y=z");
  assert.equal(decodeQueryComponent("a%2Bb"), "a+b");

  assert.equal(
    buildQueryString({
      multiValueQueryStringParameters: {
        "a+b": ["hello+world"],
        filter: ["x%26y%3Dz", "a%2Bb"]
      }
    }),
    "?a+b=hello+world&filter=x%26y%3Dz&filter=a%2Bb"
  );
});

test("builds ALB responses with multi-value headers", () => {
  const response = buildAlbResponse(201, JSON.stringify({ ok: true }), {
    "content-type": "application/json",
    "set-cookie": ["a=1", "b=2"]
  }, false, "Created");

  assert.deepEqual(response, {
    statusCode: 201,
    statusDescription: "201 Created",
    isBase64Encoded: false,
    multiValueHeaders: {
      "content-type": ["application/json"],
      "set-cookie": ["a=1", "b=2"]
    },
    body: JSON.stringify({ ok: true })
  });
});

test("filters non-forwardable response headers", () => {
  const headers = filterResponseHeaders(new Headers({
    "content-type": "application/json",
    "content-length": "15",
    "x-custom": "value"
  }));

  assert.deepEqual(headers, {
    "content-type": ["application/json"],
    "x-custom": ["value"]
  });
});

test("detects textual response content types", () => {
  assert.equal(isTextualResponse("application/json"), true);
  assert.equal(isTextualResponse("text/plain"), true);
  assert.equal(isTextualResponse("application/octet-stream"), false);
});
