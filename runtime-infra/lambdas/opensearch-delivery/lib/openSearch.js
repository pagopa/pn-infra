function failedSeqNumbers(bulkResponse, bulkBody) {
  const seqNumbers = [];

  if (bulkResponse.body.errors) {
    const items = bulkResponse.body.items;

    items.forEach((action, i) => {
      // In our case it will always be "index"
      const operationKey = Object.keys(action)[0];
      
      if (action[operationKey].error) {
        const offset = (i * 2) + 1;
        seqNumbers.push(bulkBody[offset].kinesisSeqNumber);
      }
    });
  }

  return [...new Set(seqNumbers)];
}

function prepareBulkBody(logs){
    const formattedLogs = []

    logs.forEach((doc) => {
        doc.logEvents.forEach((log) => {
            try {
                const jsonMessage = JSON.parse(log.message)
                if(jsonMessage){
                    jsonMessage.kinesisSeqNumber = doc.kinesisSeqNumber
                    jsonMessage.logGroup = doc.logGroup
                    jsonMessage.logStream = doc.logStream
                    formattedLogs.push(jsonMessage);
                }
            } catch(e){
                const timestamp = new Date(log.timestamp);

                const fakeLog = {
                    kinesisSeqNumber: doc.kinesisSeqNumber,
                    logGroup: doc.logGroup,
                    logStream: doc.logStream,
                    message: log.message,
                    '@timestamp': timestamp.toISOString(),
                    '@version': 1,
                    error_code: 'INVALID_JSON_MESSAGE',
                    level: 'FATAL',
                    logger_name: 'logs-to-opensearch-lambda'
                }

                formattedLogs.push(fakeLog);
            }
        })
    })

    if(formattedLogs.length>0){
        return formattedLogs.flatMap((doc) => [{ index: { _index: process.env.INDEX_NAME }}, doc]);
      } else {
        return [];
    }

}

export { prepareBulkBody, failedSeqNumbers };
