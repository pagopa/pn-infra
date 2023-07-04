import { Buffer } from 'node:buffer';
import { gunzipSync } from 'node:zlib';

function myGunzip( buffer ) {
  return gunzipSync(buffer);
}


function decodePayload(b64Str) {
  const payloadBuf = Buffer.from(b64Str, 'base64');
  
  let parsedJson;
  try {
    parsedJson = JSON.parse(payloadBuf.toString('utf8'));
  }
  catch ( err ) {
    const uncompressedBuf = myGunzip( payloadBuf );
    parsedJson =  JSON.parse(uncompressedBuf.toString('utf8'));
  }
  
  return parsedJson;
}

function isLogGroupDisallowed(logGroup, disallowedLogGroups){
  for(let i=0; i<disallowedLogGroups.length; i++){
    if(logGroup==disallowedLogGroups[i]) return true;
  }

  return false;
}

function isLogStreamAllowed(logStream, allowedLogStreamPatterns){
  for(let i=0; i<allowedLogStreamPatterns.length; i++){
    if(logStream.indexOf(allowedLogStreamPatterns[i])>=0) return true;
  }

  return false;
}

function isLogGroupAllowed(logGroup, allowedLogGroupPatterns){
  for(let i=0; i<allowedLogGroupPatterns.length; i++){
    if(logGroup.indexOf(allowedLogGroupPatterns[i])>=0) return true;
  }

  return false;
}

function mustLog(rec){
  const allowedLogGroupPatterns = [
    'pn-tokenExchangeLambda',
    'pn-safestorage-logger'
  ]

  const allowedLogStreamPatterns = [
    'pn-'
  ]

  const disallowedLogGroups = [
    'pn-logsaver-be-logs'
  ]

  return rec.logStream && !isLogGroupDisallowed(rec.logGroup, disallowedLogGroups) && (isLogStreamAllowed(rec.logStream, allowedLogStreamPatterns) || isLogGroupAllowed(rec.logGroup, allowedLogGroupPatterns)) && rec.messageType!=='CONTROL_MESSAGE';
}

function extractKinesisData(kinesisEvent) {
  return kinesisEvent.Records.map((rec) => {
    const decodedPayload = decodePayload(rec.kinesis.data);
    return {
      kinesisSeqNumber: rec.kinesis.sequenceNumber,
      ... decodedPayload
    }
  }).filter((rec) => {
    return mustLog(rec);
  });
}

export { extractKinesisData };
