const assert = require("node:assert/strict");
const { test } = require("node:test");

const { parseRuntimeConfig } = require("../src/app/config");

test("parses runtime configuration with allowed paths and trusted headers", () => {
  const config = parseRuntimeConfig({
    PRIVATE_CHANNEL_PROXY_ALLOWED_PATH_PATTERNS: "/foo/*,/bar/*",
    PRIVATE_CHANNEL_PROXY_BACKEND_BASE_URL: "http://backend.internal:8080/",
    PRIVATE_CHANNEL_PROXY_BACKEND_REQUEST_TIMEOUT_MILLIS: "3000",
    PRIVATE_CHANNEL_PROXY_BACKEND_RETRY_DELAY_MILLIS: "250",
    PRIVATE_CHANNEL_PROXY_BACKEND_RETRY_MAX_ATTEMPTS: "2",
    PRIVATE_CHANNEL_PROXY_EXTERNAL_PROTOCOL: "https",
    PRIVATE_CHANNEL_PROXY_EXTERNAL_PORT: "443",
    PRIVATE_CHANNEL_PROXY_REQUEST_PAYLOAD_LOGGING_ENABLED: "true",
    PRIVATE_CHANNEL_PROXY_RESPONSE_PAYLOAD_LOGGING_ENABLED: "false",
    PRIVATE_CHANNEL_PROXY_TRUSTED_HEADERS: JSON.stringify({
      "x-pagopa-pn-cx-id": "trusted-cx-id",
      "x-pagopa-pn-cx-type": "PF"
    })
  });

  assert.deepEqual(config, {
    allowedPathPatterns: ["/foo/*", "/bar/*"],
    backendBaseUrl: "http://backend.internal:8080",
    backendRequestTimeoutMillis: 3000,
    backendRetryDelayMillis: 250,
    backendRetryMaxAttempts: 2,
    baseUrlPort: "443",
    baseUrlProtocol: "https",
    requestPayloadLoggingEnabled: true,
    responsePayloadLoggingEnabled: false,
    trustedHeaders: {
      "x-pagopa-pn-cx-id": "trusted-cx-id",
      "x-pagopa-pn-cx-type": "PF"
    }
  });
});

test("keeps default backend retry and logging configuration", () => {
  const config = parseRuntimeConfig({
    PRIVATE_CHANNEL_PROXY_BACKEND_BASE_URL: "http://backend.internal:8080",
    PRIVATE_CHANNEL_PROXY_EXTERNAL_PROTOCOL: "http",
    PRIVATE_CHANNEL_PROXY_EXTERNAL_PORT: "80"
  });

  assert.deepEqual(config.allowedPathPatterns, []);
  assert.equal(config.backendRequestTimeoutMillis, 2000);
  assert.equal(config.backendRetryDelayMillis, 500);
  assert.equal(config.backendRetryMaxAttempts, 3);
  assert.equal(config.requestPayloadLoggingEnabled, false);
  assert.equal(config.responsePayloadLoggingEnabled, false);
  assert.deepEqual(config.trustedHeaders, {});
});

test("rejects invalid runtime configuration", () => {
  assert.throws(
    () => parseRuntimeConfig({
      PRIVATE_CHANNEL_PROXY_EXTERNAL_PROTOCOL: "https",
      PRIVATE_CHANNEL_PROXY_EXTERNAL_PORT: "443"
    }),
    /Missing backend base URL configuration/
  );

  assert.throws(
    () => parseRuntimeConfig({
      PRIVATE_CHANNEL_PROXY_BACKEND_BASE_URL: "http://backend.internal:8080",
      PRIVATE_CHANNEL_PROXY_EXTERNAL_PROTOCOL: "ftp",
      PRIVATE_CHANNEL_PROXY_EXTERNAL_PORT: "443"
    }),
    /External protocol must be http or https/
  );

  assert.throws(
    () => parseRuntimeConfig({
      PRIVATE_CHANNEL_PROXY_BACKEND_BASE_URL: "http://backend.internal:8080",
      PRIVATE_CHANNEL_PROXY_EXTERNAL_PROTOCOL: "https",
      PRIVATE_CHANNEL_PROXY_EXTERNAL_PORT: "0"
    }),
    /External port is out of range/
  );
});
