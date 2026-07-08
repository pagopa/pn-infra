const { queryRequest } = require("./lib/dynamo");
const { uploadFileToS3 } = require("./lib/s3");
const { unmarshall } = require("@aws-sdk/util-dynamodb");
const { retrieveInfoFromDetails } = require("./lib/utils");
const { randomUUID } = require("crypto");

const PN_NOTIFICATION_TABLE_NAME = 'pn-Notifications';
const TIMELINE_DB_TABLE_NAME = 'pn-Timelines';
const S3_BUCKET_NAME = process.env.MONITORING_BUCKET_NAME;
const PENDING_PREFIX = "critical-monitoring/";
const TAXONOMY_CODES = process.env.TAXONOMY_CODES ? process.env.TAXONOMY_CODES.split(",").map(code => code.trim()) : [];
const WHITELISTED_PA = process.env.WHITELISTED_PA ? JSON.parse(process.env.WHITELISTED_PA) : [];

function isSqsEvent(event) {
  return Array.isArray(event?.Records) && event.Records.length > 0 && event.Records[0].eventSource === "aws:sqs";
}

function getRomePathParts(referenceDate = new Date()) {
  const parts = new Intl.DateTimeFormat("it-IT", {
    timeZone: "Europe/Rome",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    hour12: false,
  }).formatToParts(referenceDate);

  const values = Object.fromEntries(
    parts.filter((p) => p.type !== "literal").map((p) => [p.type, p.value])
  );
  return { year: values.year, month: values.month, day: values.day, hour: values.hour };
}

async function retrieveElementFromDynamoDB(tableName, keyName, keyValue, sKeyName, sKeyValue) {

  console.log(`Querying ${tableName} for ${keyName}: ${keyValue}`);
  const results = await queryRequest(tableName, keyName, keyValue, sKeyName, sKeyValue);
  if (results.Items.length === 0) {
    console.warn(`No data found in ${tableName} for ${keyName}: ${keyValue}`);
    return;
  }
  return unmarshall(results.Items[0]);
}

async function exportDataToS3(data, key) {
  console.log(`Uploading JSONL report to S3 bucket: ${S3_BUCKET_NAME}, key: ${key}`);
  try {
    await uploadFileToS3(S3_BUCKET_NAME, key, data);
    console.log(`Data successfully uploaded to S3 at ${key}`);
  } catch (error) {
    console.warn(`Failed to upload data to S3 at ${key}:`, error);
    throw error;
  }
}

async function processRecord(record) {
  console.log("Processing record ", record.messageId);
  const recordBody = JSON.parse(record.body);
  console.log("Record body: ", recordBody);

  const analogMailInfo = retrieveInfoFromDetails(recordBody.analogMail);

  const notification = await retrieveElementFromDynamoDB(PN_NOTIFICATION_TABLE_NAME, "iun", analogMailInfo.iun);
  const senderPaId = notification ? notification.senderPaId : 'undefined';

  if (WHITELISTED_PA.length > 0 && !WHITELISTED_PA.includes(senderPaId)) {
    console.log(`Notification pa ${senderPaId} is not in the whitelisted list, skipping.`);
    return;
  }

  if (!TAXONOMY_CODES.includes(notification.taxonomyCode)) {
    console.log(`Notification taxonomyCode ${notification ? notification.taxonomyCode : 'undefined'} is not in the monitored list, skipping.`);
    return;
  }

  const timelines = await retrieveElementFromDynamoDB(TIMELINE_DB_TABLE_NAME, "iun", analogMailInfo.iun, "timelineElementId", analogMailInfo.requestIdWithoutPCRETRY);
  analogMailInfo.zip = timelines ? timelines.details.physicalAddress.zip : 'undefined';

  return {
    requestId: analogMailInfo.requestId,
    codiceOggetto: analogMailInfo.registeredLetterCode,
    recapitista: analogMailInfo.courier,
    cap: analogMailInfo.zip,
    timestamp: analogMailInfo.clientRequestTimeStamp,
    paId: senderPaId
  };
}

function buildPartialJsonKey() {
  const { year, month, day, hour } = getRomePathParts();
  return `${PENDING_PREFIX}${year}/${month}/${day}/${hour}/${randomUUID()}.json`;
}

async function handleSqsEvent(event) {
  const rows = [];
  let foundRecords = false;
  const batchItemFailures = [];

  for (const record of event.Records) {
    let result;
    try {
      result = await processRecord(record);
    } catch (error) {
      console.log("Error processing record ", record, error);
      batchItemFailures.push({ itemIdentifier: record.messageId });
      continue;
    }

    if (result) {
      foundRecords = true;
      rows.push(result);
    }
  }

  if (foundRecords) {
    const s3Key = buildPartialJsonKey();
    const jsonlContent = rows.map((row) => JSON.stringify(row)).join("\n") + "\n";
    try {
      await exportDataToS3(jsonlContent, s3Key);
    } catch (error) {
      console.warn("Error uploading partial JSONL report to S3", error);
      batchItemFailures.splice(0, batchItemFailures.length);
      for (const record of event.Records) {
        batchItemFailures.push({ itemIdentifier: record.messageId });
      }
    }
  }

  if (batchItemFailures.length > 0) {
    return { batchItemFailures };
  }

  return { status: "ok", batchItemFailures: [] };
}

const handler = async (event) => {
  console.info("New event received ", event);
  if (isSqsEvent(event)) {
    return handleSqsEvent(event);
  }

  throw new Error("Unsupported trigger type. Expected SQS.");
};

module.exports = {
  handler
};