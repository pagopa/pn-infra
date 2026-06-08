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

module.exports = {
  parseBaseUrlPort,
  parseBaseUrlProtocol,
  parseBooleanFlag,
  parseCsv,
  parseNonNegativeIntegerFlag,
  parseRuntimeConfig,
  parseTrustedHeaders
};
