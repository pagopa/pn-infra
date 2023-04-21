const AWS = require('aws-sdk')
const zlib = require('zlib');
const stream = require('stream');

exports.handler = async (event) => { 
    console.log( JSON.stringify(event, null, 2) );

    for( const record of event.Records ) {
        
        const msgBodyStr = record.body;
        const msg = JSON.parse( msgBodyStr );

        for ( const msgRec of msg.Records ) {
        
            const bucketName = msgRec.s3.bucket.name;
            const fileKey = msgRec.s3.object.key;
            
            console.log("bucketName=", bucketName, "fileKey=", fileKey)
            
            var s3 = new AWS.S3();
            var params = {Bucket: bucketName, Key: fileKey}
            var dataS3 = await readOne( s3, params )
            console.log("dataS3= ", dataS3)

            // Crea uno stream di lettura dal campo Body
            const readStream = new stream.PassThrough();
            readStream.end(Buffer.from(dataS3.Body, 'base64'));

            // Unzip del file
            const unzippedStream = readStream.pipe(zlib.createGunzip());

            // Legge il contenuto del file unzippato
            let unzippedBody = '';
            unzippedStream.on('data', (data) => {
                unzippedBody += data.toString();
            });

            // Ritorna una Promise che si risolve dopo che il processo di unzip è completato
            return new Promise((resolve, reject) => {
                unzippedStream.on('end', () => {
                    console.log('Processo di unzip completato.');
                    console.log('Contenuto del file unzippato:', unzippedBody);
                    filterAndPrintElement(unzippedBody);
                    resolve();
                });
                unzippedStream.on('error', (error) => {
                    console.error('Errore durante il processo di unzip:', error);
                    reject(error);
                });
            });
        }
    }
}


function readOne(s3, params) {
    return new Promise( (acc, rec) => {
        s3.getObject(params, function(err, data) {
            if (err) { rec(err) } else { acc(data) }
        });  
    })
}

function filterAndPrintElement(unzippedBody) {
    const body = JSON.parse(unzippedBody);

    // Filtra gli oggetti che hanno il valore della chiave "eventName" uguale a "GetObject"
    const filteredRecords = body.Records.filter(record => record.eventName === "GetObject");
    filteredRecords.forEach(record => {
        if(record.requestParameters.hasOwnProperty('x-amzn-trace-id')) {
            createAuditLog(record, '', 'AUD_DOWNLOAD', 'OK')
        }
        else {
            const userIdentity = record.userIdentity;
            if(userIdentity.hasOwnProperty('arn') && userIdentity.arn.includes('assumed-role/pn-safe-storage-TaskRole')) {
                createAuditLog(record, 'Amazon headers are not present!', 'AUD_DOWNLOAD', 'KO')
            }
            else {
                // ignoro l'evento
            }
        }


    });
}

function createAuditLog(record, message = '', aud_type, status) {
    let statusMessage = `INFO - ${message}`;
    if (status === 'OK') {
        statusMessage = `OK - SUCCESS - ${message}`;
    }
    if (status === 'KO') {
        statusMessage = `KO - FAILURE - ${message}`;
    }
    const auditLogRecord = {
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
        requstDate: record.requestParameters && record.requestParameters.hasOwnProperty('X-Amz-Date') ? record.requestParameters['X-Amz-Date'] : null,
        trace_id: record.requestParameters && record.requestParameters.hasOwnProperty('x-amzn-trace-id') ? record.requestParameters['x-amzn-trace-id'] : null,
    };
    if(status === 'KO') {
        console.error(JSON.stringify(auditLogRecord));
    }
    else {
        console.log(JSON.stringify(auditLogRecord));
    }

}
