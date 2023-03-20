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

function extractIun(message){
  if(!message){
    return null;
  }  

  const regex = /([A-Z]{4}\-[A-Z]{4}\-[A-Z]{4}\-[0-9]{6}\-[A-Z]{1}\-[0-9]{1})/g;
  const matches = message.match(regex);

  if(matches && matches.length>0){
    return matches[0]
  } else {
    return null;
  }
}

function truncateMessage(message, limit = 30000){
  if(message.length>limit){
    return message.slice(0, limit);
  } else {
    return message;
  }
}

function prepareBulkBody(logs){
    let formattedLogs = []

    for(const doc of logs) {
      for (const log of doc.logEvents){
        try {
          const jsonMessage = JSON.parse(log.message)
          if(jsonMessage){
            if(!jsonMessage.iun){
              const extractedIun = extractIun(jsonMessage.message)
              if(extractedIun){
                jsonMessage.iun = extractedIun;
              }
            }

            // fix to handle bunyan nodejs logger format
            if(jsonMessage.time && !jsonMessage['@timestamp']){
              jsonMessage['@timestamp'] = jsonMessage.time
            }
            
            jsonMessage.message = truncateMessage(jsonMessage.message, 30000)
            jsonMessage._id = log.id
            jsonMessage.kinesisSeqNumber = doc.kinesisSeqNumber
            jsonMessage.logGroup = doc.logGroup
            jsonMessage.logStream = doc.logStream

            if(jsonMessage.stack_trace) {
              jsonMessage.stack_trace = truncateMessage(jsonMessage.stack_trace, 20000)
            }
            
            formattedLogs.push(jsonMessage);
          }
        } catch(e){
          console.log(e)
          const timestamp = new Date(log.timestamp);

          
          const fakeLog = {
              _id: log.id,
              kinesisSeqNumber: doc.kinesisSeqNumber,
              logGroup: doc.logGroup,
              logStream: doc.logStream,
              message: truncateMessage(log.message, 30000),
              '@timestamp': timestamp.toISOString(),
              '@version': 1,
              error_code: 'INVALID_JSON_MESSAGE',
              level: 'FATAL',
              logger_name: 'logs-to-opensearch-lambda'
          }

          formattedLogs.push(fakeLog);
        }
      }
    }
    
    if(formattedLogs.length>0){
        formattedLogs = chunk(formattedLogs, 500)
        return formattedLogs.map((formattedLogBatch) => {
          return formattedLogBatch.flatMap((doc) => [{ index: { _index: process.env.INDEX_NAME, _id: doc._id }}, doc]);
        })
      } else {
        return [];
    }
}

export { prepareBulkBody, failedSeqNumbers };
