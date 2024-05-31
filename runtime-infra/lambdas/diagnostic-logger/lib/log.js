const bunyan = require("bunyan");

module.exports =
    function auditLog(record, message = '', aud_type, status) {
    let statusMessage = `INFO - ${message}`;
    if (status === 'OK') {
        statusMessage = `OK - SUCCESS - ${message}`;
    }
    if (status === 'KO') {
        statusMessage = `KO - FAILURE - ${message}`;
    }

    const auditRecord = Object.assign(record, {
        name: 'AUDIT_LOG',
        message: `[${aud_type}] - ${statusMessage}`,
        aud_type: aud_type,
        level: status === 'KO' ? 'ERROR' : 'INFO',
        level_value: status === 'KO' ? 40000 : 20000,
        logger_name: 'pn-diagnostic-logger',
        tags: [
            "AUDIT10Y"
        ]
    });

    return bunyan.createLogger(auditRecord);
}