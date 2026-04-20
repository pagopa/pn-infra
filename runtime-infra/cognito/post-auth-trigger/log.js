import { hostname } from "os";

export function auditLog(
  message = "",
  aud_type,
  aud_orig,
  uid
) {
  const logEntry = {
    name: "AUDIT_LOG",
    message: `[${aud_type}] - INFO - ${message}`,
    aud_type: aud_type,
    aud_orig: aud_orig,
    uid: uid,
    level_value: 20000,
    logger_name: "authService",
    tags: ["AUDIT10Y"],
    hostname: hostname(),
    pid: process.pid,
    level: 30,
    msg: "info",
    time: new Date().toISOString(),
    v: 0
  };
  process.stdout.write(JSON.stringify(logEntry) + "\n");
}
