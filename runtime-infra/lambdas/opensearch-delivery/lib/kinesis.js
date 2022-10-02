import { Buffer } from 'node:buffer';
import { gunzipSync } from 'node:zlib';

function myGunzip( buffer ) {
  return gunzipSync(buffer) 
}


function decodePayload(b64Str) {
  const payloadBuf = Buffer.from(b64Str, 'base64');
  const uncompressedBuf = myGunzip( payloadBuf );
  return JSON.parse(uncompressedBuf.toString('utf8'));
}

function extractKinesisData(kinesisEvent) {
  return kinesisEvent.Records.map((rec) => {
    const decodedPayload = decodePayload(rec.kinesis.data);
    return {
      kinesisSeqNumber: rec.kinesis.sequenceNumber,
      ... decodedPayload
    }
  });
}

export { extractKinesisData };
