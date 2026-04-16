export function auditLog(
  message = "",
  aud_type,
  aud_orig,
  uid
) {
  const logEntry = {
    message: `[${aud_type}] - ${message}`,
    aud_type: aud_type,
    aud_orig: aud_orig,
    uid: uid,
    tags: ["AUDIT10Y"]
  };
  console.log(JSON.stringify(logEntry));
  return {
    info: () => {},
    warn: () => {},
    error: () => {}
  };
}
