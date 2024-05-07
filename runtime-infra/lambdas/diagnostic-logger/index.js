const { S3Client, GetObjectCommand } = require("@aws-sdk/client-s3");
const zlib = require('zlib');
const auditLog = require("./lib/log.js");
const client = new S3Client();

exports.handler = async (event) => {
    console.log( JSON.stringify(event, null, 2) );

    for( const record of event.Records ) {

        const msgBodyStr = record.body;
        const msgRec = JSON.parse( msgBodyStr );

        if(!msgRec.s3) {
            console.log("The message is not a lambda invocation event.")
            continue;
        }

        const bucketName = msgRec.s3.bucket.name;
        const fileKey = msgRec.s3.object.key;

        console.log("bucketName=", bucketName, "fileKey=", fileKey)

        // Recupero del file
        console.log("bucketName=", bucketName, "fileKey=", fileKey)
        const params = {Bucket: bucketName, Key: fileKey}
        const dataS3 = await client.send(new GetObjectCommand(params))

        // Unzip del file
        const unzippedStream = dataS3.Body.pipe(zlib.createGunzip());

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


function filterAndPrintElement(unzippedBody) {
    const body = JSON.parse(unzippedBody);

    // Filtra gli oggetti che hanno il valore della chiave "eventName" uguale a "GetObject"
    const filteredRecords = body.Records.filter(record => {
        return record.eventName === "Invoke" && record.eventSource === "lambda.amazonaws.com"; 
    });
    filteredRecords.forEach(record => {
        const logData = {
            requestID: record.requestID,
            eventID: record.eventID,
            eventTime: record.eventTime,
            eventName: record.eventName,
            eventSource: record.eventSource,
            awsRegion: record.awsRegion,
            functionArn: record.additionalEventData?.functionVersion,
            userIdentity: {
                type: record.userIdentity.type,
                arn: record.userIdentity.arn,
                sessionArn: userIdentity.sessionContext?.sessionIssuer?.arn,
                sessionCreationDate: userIdentity.sessionContext?.attributes?.creationDate
            }
        }

        auditLog(logData, 'Diagnostic lambda invoked', 'DIAGNOSTIC_INVOKE', 'OK').info('info');
    });
}


