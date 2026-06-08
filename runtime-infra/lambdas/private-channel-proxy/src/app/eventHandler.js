const { parseRuntimeConfig } = require("./config");
const {
  buildAlbResponse,
  buildForwardHeaders,
  buildQueryString,
  buildRequestBody,
  collectHeaders,
  filterResponseHeaders,
  isTextualResponse
} = require("./http");

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

async function handleEvent(event, context) {
  if (!defaultHandler) {
    defaultHandler = createHandler();
  }
  return defaultHandler(event, context);
}

module.exports = {
  createHandler,
  deriveBaseUrlFromHost,
  handleEvent,
  isAllowedPath,
  isRetryableBackendError,
  isRetryableBackendResponse,
  validatePathForForward
};
