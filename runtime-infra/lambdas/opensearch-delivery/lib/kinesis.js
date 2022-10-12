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

function mustLog(rec){
  return rec.logStream && rec.logStream.indexOf('pn-')>=0;
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
