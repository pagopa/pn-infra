const NON_FORWARDABLE_HEADERS = new Set([
  "connection",
  "transfer-encoding",
  "keep-alive",
  "upgrade",
  "te",
  "trailer",
  "content-length"
]);

const BASE_URL_HEADER = "x-pagopa-pn-base-url";
const LAMBDA_TRACE_ENV_NAME = "_X_AMZN_TRACE_ID";
const TRACE_HEADER_NAME = "x-amzn-trace-id";
const RETRYABLE_BACKEND_STATUS_CODES = new Set([500, 502, 503, 504]);
const RETRYABLE_BACKEND_ERROR_CODES = new Set([
  "ECONNABORTED",
  "ECONNREFUSED",
  "ECONNRESET",
  "ENOTFOUND",
  "ETIMEDOUT",
  "EAI_AGAIN",
  "UND_ERR_CONNECT_TIMEOUT",
  "UND_ERR_HEADERS_TIMEOUT",
  "UND_ERR_SOCKET"
]);

let defaultHandler;

function parseCsv(rawValue) {
  if (rawValue === undefined || rawValue === null) {
    return [];
  }

  return String(rawValue)
    .split(",")
    .map((value) => value.trim())
    .filter(Boolean);
}

function parseTrustedHeaders(rawTrustedHeaders) {
  if (!rawTrustedHeaders) {
    return {};
  }

  const parsed = JSON.parse(rawTrustedHeaders);
  if (!parsed || Array.isArray(parsed) || typeof parsed !== "object") {
    throw new Error("Trusted headers configuration must be a JSON object");
  }

  return Object.entries(parsed).reduce((acc, [name, value]) => {
    if (!name || value === undefined || value === null || value === "") {
      return acc;
    }
    acc[name.toLowerCase()] = String(value);
    return acc;
  }, {});
}

function parseBooleanFlag(rawFlag, defaultValue = false) {
  if (rawFlag === undefined || rawFlag === null || String(rawFlag).trim() === "") {
    return defaultValue;
  }

  const normalizedFlag = String(rawFlag).trim().toLowerCase();
  if (normalizedFlag === "true") {
    return true;
  }
  if (normalizedFlag === "false") {
    return false;
  }

  throw new Error("Boolean flag must be true or false");
}

function parseNonNegativeIntegerFlag(rawValue, defaultValue, flagName, minimum = 0) {
  if (rawValue === undefined || rawValue === null || String(rawValue).trim() === "") {
    return defaultValue;
  }

  const normalizedValue = String(rawValue).trim();
  if (!/^\d+$/.test(normalizedValue)) {
    throw new Error(`${flagName} must be a non-negative integer`);
  }

  const numericValue = Number(normalizedValue);
  if (numericValue < minimum) {
    throw new Error(`${flagName} must be greater than or equal to ${minimum}`);
  }

  return numericValue;
}

function parseBaseUrlProtocol(rawProtocol) {
  const protocol = String(rawProtocol || "").trim().toLowerCase();
  if (protocol !== "https" && protocol !== "http") {
    throw new Error("External protocol must be http or https");
  }
  return protocol;
}

function parseBaseUrlPort(rawPort) {
  const port = String(rawPort || "").trim();
  if (!/^\d+$/.test(port)) {
    throw new Error("External port must be numeric");
  }

  const numericPort = Number(port);
  if (numericPort < 1 || numericPort > 65535) {
    throw new Error("External port is out of range");
  }

  return port;
}

function parseRuntimeConfig(env) {
  const backendBaseUrl = env.PRIVATE_CHANNEL_PROXY_BACKEND_BASE_URL;
  if (!backendBaseUrl) {
    throw new Error("Missing backend base URL configuration");
  }

  return {
    allowedPathPatterns: parseCsv(env.PRIVATE_CHANNEL_PROXY_ALLOWED_PATH_PATTERNS),
    backendBaseUrl: backendBaseUrl.replace(/\/$/, ""),
    backendRequestTimeoutMillis: parseNonNegativeIntegerFlag(
      env.PRIVATE_CHANNEL_PROXY_BACKEND_REQUEST_TIMEOUT_MILLIS,
      2000,
      "Backend request timeout flag",
      1
    ),
    backendRetryDelayMillis: parseNonNegativeIntegerFlag(
      env.PRIVATE_CHANNEL_PROXY_BACKEND_RETRY_DELAY_MILLIS,
      500,
      "Backend retry delay flag"
    ),
    backendRetryMaxAttempts: parseNonNegativeIntegerFlag(
      env.PRIVATE_CHANNEL_PROXY_BACKEND_RETRY_MAX_ATTEMPTS,
      3,
      "Backend retry max attempts flag",
      1
    ),
    baseUrlPort: parseBaseUrlPort(env.PRIVATE_CHANNEL_PROXY_EXTERNAL_PORT),
    baseUrlProtocol: parseBaseUrlProtocol(env.PRIVATE_CHANNEL_PROXY_EXTERNAL_PROTOCOL),
    requestPayloadLoggingEnabled: parseBooleanFlag(env.PRIVATE_CHANNEL_PROXY_REQUEST_PAYLOAD_LOGGING_ENABLED, false),
    responsePayloadLoggingEnabled: parseBooleanFlag(env.PRIVATE_CHANNEL_PROXY_RESPONSE_PAYLOAD_LOGGING_ENABLED, false),
    trustedHeaders: parseTrustedHeaders(env.PRIVATE_CHANNEL_PROXY_TRUSTED_HEADERS)
  };
}

function getLambdaTraceId(env) {
  const traceId = env[LAMBDA_TRACE_ENV_NAME];
  if (!traceId) {
    console.log("No _X_AMZN_TRACE_ID found in environment variables");
    return null;
  }

  return String(traceId);
}

function withLambdaTraceHeader(headers, traceId) {
  if (!traceId) {
    return headers;
  }

  return {
    ...headers,
    [TRACE_HEADER_NAME]: traceId
  };
}

function serializeHeaderValues(name, values) {
  const normalizedValues = values
    .filter((value) => value !== undefined && value !== null)
    .map(String);

  if (name.toLowerCase() === "cookie") {
    return normalizedValues.join("; ");
  }

  return normalizedValues.join(",");
}

function collectHeaders(event) {
  const headers = {};

  for (const [name, value] of Object.entries(event.headers || {})) {
    if (value !== undefined && value !== null) {
      headers[name.toLowerCase()] = String(value);
    }
  }

  for (const [name, values] of Object.entries(event.multiValueHeaders || {})) {
    if (Array.isArray(values) && values.length > 0) {
      headers[name.toLowerCase()] = serializeHeaderValues(name, values);
    }
  }

  return headers;
}

function buildForwardHeaders(incomingHeaders, config, baseUrl) {
  const trustedHeaderNames = new Set([...Object.keys(config.trustedHeaders), BASE_URL_HEADER]);
  const forwardHeaders = {};

  for (const [name, value] of Object.entries(incomingHeaders)) {
    const lowerName = name.toLowerCase();
    if (NON_FORWARDABLE_HEADERS.has(lowerName) || trustedHeaderNames.has(lowerName)) {
      continue;
    }
    forwardHeaders[lowerName] = value;
  }

  for (const [name, value] of Object.entries(config.trustedHeaders)) {
    forwardHeaders[name] = value;
  }
  forwardHeaders[BASE_URL_HEADER] = baseUrl;

  return forwardHeaders;
}

function buildQueryString(event) {
  const params = [];

  if (event.multiValueQueryStringParameters) {
    for (const [name, values] of Object.entries(event.multiValueQueryStringParameters)) {
      for (const value of values || []) {
        if (value !== undefined && value !== null) {
          params.push(`${String(name)}=${String(value)}`);
        }
      }
    }
  } else if (event.queryStringParameters) {
    for (const [name, value] of Object.entries(event.queryStringParameters)) {
      if (value !== undefined && value !== null) {
        params.push(`${String(name)}=${String(value)}`);
      }
    }
  }

  const serialized = params.join("&");
  return serialized ? `?${serialized}` : "";
}

function buildRequestBody(event, method) {
  if (["GET", "HEAD"].includes(method.toUpperCase()) || event.body === undefined || event.body === null) {
    return undefined;
  }

  if (event.isBase64Encoded) {
    return Buffer.from(event.body, "base64");
  }

  return event.body;
}

function isTextualResponse(contentType) {
  const normalized = (Array.isArray(contentType) ? contentType[0] || "" : contentType || "").toLowerCase();
  return normalized.startsWith("text/") ||
    normalized.includes("json") ||
    normalized.includes("xml") ||
    normalized.includes("x-www-form-urlencoded");
}

function buildAlbResponse(statusCode, body, headers = {}, isBase64Encoded = false, statusText = "") {
  const multiValueHeaders = {};

  for (const [name, value] of Object.entries(headers)) {
    if (Array.isArray(value) && value.length > 0) {
      multiValueHeaders[name.toLowerCase()] = value.map(String);
    } else if (value !== undefined && value !== null) {
      multiValueHeaders[name.toLowerCase()] = [String(value)];
    }
  }

  return {
    statusCode,
    statusDescription: `${statusCode}${statusText ? ` ${statusText}` : ""}`,
    isBase64Encoded,
    multiValueHeaders,
    body
  };
}

function appendHeaderValue(headers, name, value) {
  if (value === undefined || value === null) {
    return;
  }

  const lowerName = name.toLowerCase();
  if (!headers[lowerName]) {
    headers[lowerName] = [];
  }
  headers[lowerName].push(String(value));
}

function filterResponseHeaders(responseHeaders) {
  const headers = {};
  const setCookieValues = typeof responseHeaders.getSetCookie === "function"
    ? responseHeaders.getSetCookie()
    : [];

  responseHeaders.forEach((value, name) => {
    const lowerName = name.toLowerCase();
    if (lowerName === "set-cookie" && setCookieValues.length > 0) {
      return;
    }

    if (!NON_FORWARDABLE_HEADERS.has(lowerName)) {
      appendHeaderValue(headers, lowerName, value);
    }
  });

  for (const value of setCookieValues) {
    appendHeaderValue(headers, "set-cookie", value);
  }

  return headers;
}

function matchesAllowedPathPattern(path, allowedPathPattern) {
  if (allowedPathPattern === "*") {
    return true;
  }

  if (allowedPathPattern.endsWith("*")) {
    return path.startsWith(allowedPathPattern.slice(0, -1));
  }

  return path === allowedPathPattern;
}

function isAllowedPath(path, allowedPathPatterns) {
  if (allowedPathPatterns.length === 0) {
    return true;
  }

  return allowedPathPatterns.some((allowedPathPattern) => matchesAllowedPathPattern(path, allowedPathPattern));
}

function validatePathForForward(path) {
  if (!path.startsWith("/")) {
    throw new Error("Invalid path");
  }

  for (const rawSegment of path.split("/")) {
    if (!rawSegment) {
      continue;
    }

    let decodedSegment;
    try {
      decodedSegment = decodeURIComponent(rawSegment);
    } catch (err) {
      throw new Error("Invalid encoded path segment");
    }

    if (decodedSegment === "." || decodedSegment === "..") {
      throw new Error("Dot segments are not allowed");
    }

    if (decodedSegment.includes("/") || decodedSegment.includes("\\")) {
      throw new Error("Encoded path separators are not allowed");
    }
  }
}

function deriveBaseUrlFromHost(hostHeader, config) {
  if (!hostHeader) {
    throw new Error("Missing Host header");
  }

  let parsedHost;
  try {
    parsedHost = new URL(`${config.baseUrlProtocol}://${hostHeader}`);
  } catch (err) {
    throw new Error("Invalid Host header");
  }

  const hostname = parsedHost.hostname.toLowerCase();

  if (config.baseUrlProtocol === "https" && config.baseUrlPort === "443") {
    return `${config.baseUrlProtocol}://${hostname}`;
  }

  if (config.baseUrlProtocol === "http" && config.baseUrlPort === "80") {
    return `${config.baseUrlProtocol}://${hostname}`;
  }

  return `${config.baseUrlProtocol}://${hostname}:${config.baseUrlPort}`;
}

function logError(message, err, meta = {}) {
  console.error(message, {
    ...meta,
    message: err.message,
    stack: err.stack
  });
}

function sleep(delayMillis) {
  return new Promise((resolve) => setTimeout(resolve, delayMillis));
}

function isRetryableBackendResponse(statusCode) {
  return RETRYABLE_BACKEND_STATUS_CODES.has(statusCode);
}

function extractRetryableBackendErrorCode(err) {
  return err?.code || err?.cause?.code || null;
}

function isRetryableBackendError(err) {
  return err?.name === "AbortError" || RETRYABLE_BACKEND_ERROR_CODES.has(extractRetryableBackendErrorCode(err));
}

async function forwardBackendRequest({ fetchImpl, backendUrl, method, headers, body, config, path }) {
  let lastError;

  for (let attempt = 1; attempt <= config.backendRetryMaxAttempts; attempt++) {
    const abortController = new AbortController();
    const timeoutId = setTimeout(() => abortController.abort(), config.backendRequestTimeoutMillis);

    try {
      const backendResponse = await fetchImpl(backendUrl, {
        method,
        headers,
        body,
        signal: abortController.signal
      });
      clearTimeout(timeoutId);

      if (attempt < config.backendRetryMaxAttempts && isRetryableBackendResponse(backendResponse.status)) {
        try {
          await backendResponse.body?.cancel?.();
        } catch (cancelErr) {
          console.warn("Private channel proxy failed to cancel retryable backend response body", {
            method,
            path,
            attempt,
            statusCode: backendResponse.status,
            message: cancelErr.message
          });
        }

        console.warn("Private channel proxy backend retry scheduled", {
          method,
          path,
          attempt,
          maxAttempts: config.backendRetryMaxAttempts,
          statusCode: backendResponse.status
        });

        if (config.backendRetryDelayMillis > 0) {
          await sleep(config.backendRetryDelayMillis);
        }
        continue;
      }

      return {
        attempts: attempt,
        backendResponse
      };
    } catch (err) {
      clearTimeout(timeoutId);
      lastError = err;

      if (attempt < config.backendRetryMaxAttempts && isRetryableBackendError(err)) {
        console.warn("Private channel proxy backend retry scheduled", {
          method,
          path,
          attempt,
          maxAttempts: config.backendRetryMaxAttempts,
          errorCode: extractRetryableBackendErrorCode(err),
          errorName: err.name,
          message: err.message
        });

        if (config.backendRetryDelayMillis > 0) {
          await sleep(config.backendRetryDelayMillis);
        }
        continue;
      }

      throw err;
    }
  }

  throw lastError || new Error("Backend request failed without explicit error");
}

function createHandler({ fetchImpl = globalThis.fetch, env = process.env } = {}) {
  if (!fetchImpl) {
    throw new Error("Missing fetch implementation");
  }

  const config = parseRuntimeConfig(env);

  return async function privateChannelProxyHandler(event) {
    const method = event.httpMethod || "GET";
    const path = event.path || "/";
    const incomingHeaders = collectHeaders(event);
    const lambdaTraceId = getLambdaTraceId(env);
    const withTrace = (headers) => withLambdaTraceHeader(headers, lambdaTraceId);
    const buildLocalAlbJsonResponse = (statusCode, message, statusText) => buildAlbResponse(
      statusCode,
      JSON.stringify({ message }),
      withTrace({
        "content-type": "application/json"
      }),
      false,
      statusText
    );

    console.log("Private channel proxy inbound headers", {
      method,
      path,
      headers: {
        host: incomingHeaders.host,
        "x-forwarded-for": incomingHeaders["x-forwarded-for"],
        "x-forwarded-port": incomingHeaders["x-forwarded-port"],
        "x-forwarded-proto": incomingHeaders["x-forwarded-proto"]
      }
    });

    if (config.requestPayloadLoggingEnabled) {
      console.log("Private channel proxy inbound request payload", {
        method,
        path,
        headers: incomingHeaders,
        queryStringParameters: event.queryStringParameters || null,
        body: event.body || null,
        isBase64Encoded: Boolean(event.isBase64Encoded)
      });
    }

    try {
      validatePathForForward(path);
    } catch (err) {
      console.warn("Private channel proxy rejected path", { method, path, reason: err.message });
      return buildLocalAlbJsonResponse(403, "Forbidden", "Forbidden");
    }

    if (!isAllowedPath(path, config.allowedPathPatterns)) {
      console.warn("Private channel proxy rejected path", { method, path, reason: "Path not allowed" });
      return buildLocalAlbJsonResponse(403, "Forbidden", "Forbidden");
    }

    let baseUrl;
    try {
      baseUrl = deriveBaseUrlFromHost(incomingHeaders.host, config);
    } catch (err) {
      logError("Private channel proxy failed Host validation", err, { path });
      return buildLocalAlbJsonResponse(400, "Invalid Host header", "Bad Request");
    }

    const queryString = buildQueryString(event);
    const backendUrl = `${config.backendBaseUrl}${path}${queryString}`;
    const forwardHeaders = withTrace(buildForwardHeaders(incomingHeaders, config, baseUrl));
    const requestBody = buildRequestBody(event, method);

    try {
      const backendRequestStartedAt = Date.now();
      const { backendResponse, attempts } = await forwardBackendRequest({
        fetchImpl,
        backendUrl,
        method,
        headers: forwardHeaders,
        body: requestBody,
        config,
        path
      });

      const responseHeaders = withTrace(filterResponseHeaders(backendResponse.headers));
      const responseBuffer = Buffer.from(await backendResponse.arrayBuffer());
      const contentType = responseHeaders["content-type"]?.[0] || "";
      const textualResponse = isTextualResponse(contentType);
      const responseDurationMs = Date.now() - backendRequestStartedAt;
      const responseStatusCode = backendResponse.status;
      const responseStatusText = backendResponse.statusText;
      const responseIsBase64Encoded = !textualResponse;
      const responseBody = textualResponse ? responseBuffer.toString("utf8") : responseBuffer.toString("base64");

      console.log("Private channel proxy forwarded request", {
        method,
        path,
        statusCode: responseStatusCode,
        durationMs: responseDurationMs,
        attempts
      });

      if (responseStatusCode >= 500) {
        console.error("Private channel proxy backend 5xx response", {
          method,
          path,
          statusCode: responseStatusCode,
          message: responseStatusText || null,
          durationMs: responseDurationMs,
          attempts
        });
      } else if (responseStatusCode >= 400) {
        console.warn("Private channel proxy backend 4xx response", {
          method,
          path,
          statusCode: responseStatusCode,
          message: responseStatusText || null,
          durationMs: responseDurationMs,
          attempts
        });
      }

      if (config.responsePayloadLoggingEnabled) {
        console.log("Private channel proxy outbound response payload", {
          method,
          path,
          statusCode: responseStatusCode,
          isBase64Encoded: responseIsBase64Encoded,
          body: textualResponse ? responseBody : null
        });
      }

      return buildAlbResponse(
        responseStatusCode,
        responseBody,
        responseHeaders,
        responseIsBase64Encoded,
        responseStatusText
      );
    } catch (err) {
      logError("Private channel proxy backend forward failed", err, { path });
      return buildLocalAlbJsonResponse(502, "Backend forward failed", "Bad Gateway");
    }
  };
}

async function handler(event, context) {
  if (!defaultHandler) {
    defaultHandler = createHandler();
  }
  return defaultHandler(event, context);
}

module.exports = {
  createHandler,
  handler
};
