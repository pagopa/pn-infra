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
    return bunyan.createLogger({
        name: 'AUDIT_LOG',
        message: `[${aud_type}] - ${statusMessage}`,
        aud_type: aud_type,
        level: status === 'KO' ? 'ERROR' : 'INFO',
        level_value: status === 'KO' ? 40000 : 20000,
        logger_name: 'pn-safestorage-logger',
        eventID: record.eventID,
        eventName: record.eventName,
        eventTime: record.eventTime,
        requestID: record.requestID,
        bucketFileKey: record.requestParameters ? record.requestParameters.key : null,
        requestSignedHeaders: record.requestParameters && record.requestParameters.hasOwnProperty('X-Amz-SignedHeaders') ? record.requestParameters['X-Amz-SignedHeaders'] : null,
        requestSigningAlgorithm: record.requestParameters && record.requestParameters.hasOwnProperty('X-Amz-Algorithm') ? record.requestParameters['X-Amz-Algorithm'] : null,
        requestDate: record.requestParameters && record.requestParameters.hasOwnProperty('X-Amz-Date') ? record.requestParameters['X-Amz-Date'] : null,
        trace_id: record.requestParameters && record.requestParameters.hasOwnProperty('x-amzn-trace-id') ? record.requestParameters['x-amzn-trace-id'] : null,
        tags: [
            "AUDIT10Y"
        ],
    })
}