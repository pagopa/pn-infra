import bunyan from "bunyan";

export function auditLog(
  message = "",
  aud_type,
  aud_orig,
  uid
) {
  const logEntry = {
    aud_type: aud_type,
    aud_orig: aud_orig,
    uid: uid,
    message: `[${aud_type}] - ${message}`,
    tags: ["AUDIT10Y"]
  };
  console.log(JSON.stringify(logEntry));
}
