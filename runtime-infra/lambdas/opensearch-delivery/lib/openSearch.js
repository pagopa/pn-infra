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

function chunk(arr, size) {
  return Array.from({ length: Math.ceil(arr.length / size) }, (v, i) =>
    arr.slice(i * size, i * size + size)
  );
}

function prepareBulkBody(logs){
    let formattedLogs = []

    logs.forEach((doc) => {
        doc.logEvents.forEach((log) => {
            try {
                const jsonMessage = JSON.parse(log.message)
                if(jsonMessage){
                    jsonMessage._id = log.id
                    jsonMessage.kinesisSeqNumber = doc.kinesisSeqNumber
                    jsonMessage.logGroup = doc.logGroup
                    jsonMessage.logStream = doc.logStream
                    formattedLogs.push(jsonMessage);
                }
            } catch(e){
                const timestamp = new Date(log.timestamp);

                const fakeLog = {
                    _id: log.id,
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
        formattedLogs = chunk(formattedLogs, 500)
        return formattedLogs.map((formattedLogBatch) => {
          return formattedLogBatch.flatMap((doc) => [{ index: { _index: process.env.INDEX_NAME, _id: doc._id }}, doc]
          
          );
        })
      } else {
        return [];
    }

}

export { prepareBulkBody, failedSeqNumbers };
