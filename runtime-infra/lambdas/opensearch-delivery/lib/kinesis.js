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

const loggableLogGroups = ['/ecs/pn-delivery', 'pn-logsaver-be-logs'];

function mustLog(rec){
  const idx = loggableLogGroups.indexOf(rec.logGroup);
  if(idx<0){
    return false;
  }

  if(rec.logStream.indexOf('pn-')>0) return true;
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
