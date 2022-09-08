import { Buffer } from 'node:buffer';

function decodePayload(b64Str) {
  const payloadBuf = Buffer.from(b64Str, 'base64');
  return JSON.parse(payloadBuf.toString());
}

function extractKinesisData(kinesisEvent) {
  return kinesisEvent.Records.map((rec) => {
    return {
      kinesisSeqNumber: rec.kinesis.sequenceNumber,
      ...decodePayload(rec.kinesis.data)
    }
  });
}

export { extractKinesisData };
