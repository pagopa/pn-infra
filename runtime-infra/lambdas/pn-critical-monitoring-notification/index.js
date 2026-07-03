const { queryRequest } = require("./lib/dynamo");
const {
  uploadFileToS3,
  listObjectsByPrefix,
  downloadFileFromS3,
  deleteObjectsFromS3,
  generatePresignedUrl,
} = require("./lib/s3");
const { publishMessageToSns } = require("./lib/sns");
const { unmarshall } = require("@aws-sdk/util-dynamodb");
const {
  retrieveInfoFromDetails,
  prepareAggregationMessageToSns,
} = require("./lib/utils");

const PN_NOTIFICATION_TABLE_NAME = 'pn-Notification';
const TIMELINE_DB_TABLE_NAME = 'pn-Timelines';
const S3_BUCKET_NAME = process.env.MONITORING_BUCKET_NAME;
const SNS_TOPIC_ARN = process.env.SNS_TOPIC_ARN;
const HEADER_CSV = "RequestId, CodiceOggetto, Recapitista, CAP\n";
const PENDING_PREFIX = "critical-monitoring/to_send/";
const TAXONOMY_CODES = process.env.TAXONOMY_CODES ? process.env.TAXONOMY_CODES.split(",").map(code => code.trim()) : [];
const WHITELISTED_PA = process.env.WHITELISTED_PA ? process.env.WHITELISTED_PA.split(",").map(pa => pa.trim()) : [];

function isSqsEvent(event) {
  return Array.isArray(event?.Records) && event.Records.length > 0 && event.Records[0].eventSource === "aws:sqs";
}

function isScheduledEvent(event) {
  return (
    event?.["detail-type"] === "Scheduled Event" &&
    (event?.source === "aws.events" || event?.source === "aws.scheduler")
  );
}

function getRomeIsoTimestamp(referenceDate = new Date()) {
  const formatter = new Intl.DateTimeFormat("sv-SE", {
    timeZone: "Europe/Rome",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  });

  return formatter.format(referenceDate).replace(" ", "T");
}

function extractCsvDataRows(csvContent) {
  const lines = csvContent
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => line.length > 0);

  if (lines.length === 0) {
    return [];
  }

  const normalizedHeader = HEADER_CSV.trim();
  if (lines[0] === normalizedHeader) {
    return lines.slice(1);
  }

  return lines;
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
  console.log(`Uploading CSV report to S3 bucket: ${S3_BUCKET_NAME}, key: ${key}`);
  try {
    await uploadFileToS3(S3_BUCKET_NAME, key, data);
    console.log(`Data successfully uploaded to S3 at ${key}`);
  } catch (error) {
    console.error(`Failed to upload data to S3 at ${key}:`, error);
    throw error;
  }
}

async function processRecord(record) {
  console.log("Processing record ", record.messageId);
  const recordBody = JSON.parse(record.body);
  console.log("Record body: ", recordBody);

  const analogMailInfo = retrieveInfoFromDetails(recordBody.analogMail);

  const notification = await retrieveElementFromDynamoDB(PN_NOTIFICATION_TABLE_NAME, "iun", analogMailInfo.iun);

  if (WHITELISTED_PA.length > 0 && !WHITELISTED_PA.includes(notification.pa)) {
    console.log(`Notification pa ${notification ? notification.pa : 'undefined'} is not in the whitelisted list, skipping.`);
    return;
  } 
  
  if (!TAXONOMY_CODES.includes(notification.taxonomyCode)) {
    console.log(`Notification taxonomyCode ${notification ? notification.taxonomyCode : 'undefined'} is not in the monitored list, skipping.`);
    return;
  }

  const timelines = await retrieveElementFromDynamoDB(TIMELINE_DB_TABLE_NAME, "iun", analogMailInfo.iun, "timelineElementId", analogMailInfo.requestIdWithoutPCRETRY);
  analogMailInfo.zip = timelines.details.physicalAddress.zip;

  return `${analogMailInfo.requestId}, ${analogMailInfo.registeredLetterCode}, ${analogMailInfo.courier}, ${analogMailInfo.zip}`;
}

function buildPartialCsvKey() {
  const timestamp = getRomeIsoTimestamp();
  return `${PENDING_PREFIX}to_send_${timestamp}_batch.csv`;
}

function buildAggregatedCsvKey() {
  const timestamp = getRomeIsoTimestamp();
  return `critical-monitoring/aggregate/${timestamp}.csv`;
}

async function handleSqsEvent(event) {
  let csvContent = HEADER_CSV;
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
      csvContent += `${result}\n`;
    }
  }

  if (foundRecords) {
    const s3Key = buildPartialCsvKey();
    try {
      await exportDataToS3(csvContent, s3Key);
    } catch (error) {
      console.error("Error uploading partial CSV report to S3", error);
      batchItemFailures.splice(0, batchItemFailures.length);
      for (const record of event.Records) {
        batchItemFailures.push({ itemIdentifier: record.messageId });
      }
    }
  }

  if (batchItemFailures.length > 0) {
    return { batchItemFailures };
  }

  return { status: "ok" };
}

async function handleScheduledEvent() {
  const pendingObjects = await listObjectsByPrefix(S3_BUCKET_NAME, PENDING_PREFIX);
  if (pendingObjects.length === 0) {
    console.log(`No pending files found under prefix ${PENDING_PREFIX}`);
    return { status: "ok", details: "No files to aggregate" };
  }

  const allRows = [];
  for (const object of pendingObjects) {
    if (!object.Key) {
      continue;
    }
    const csvContent = await downloadFileFromS3(S3_BUCKET_NAME, object.Key);
    allRows.push(...extractCsvDataRows(csvContent));
  }

  const aggregatedCsvContent = allRows.length > 0
    ? `${HEADER_CSV}${allRows.join("\n")}\n`
    : HEADER_CSV;
  const aggregatedKey = buildAggregatedCsvKey();

  await exportDataToS3(aggregatedCsvContent, aggregatedKey);
  await deleteObjectsFromS3(
    S3_BUCKET_NAME,
    pendingObjects.map((object) => object.Key).filter(Boolean)
  );

  const presignedUrl = await generatePresignedUrl(S3_BUCKET_NAME, aggregatedKey);
  const message = prepareAggregationMessageToSns({
    bucketName: S3_BUCKET_NAME,
    key: aggregatedKey,
    rowCount: allRows.length,
    sourceFilesCount: pendingObjects.length,
    presignedUrl,
  });

  await publishMessageToSns(SNS_TOPIC_ARN, "Critical monitoring batch ready", message);

  return {
    status: "ok",
    aggregatedKey,
    rowCount: allRows.length,
    sourceFilesCount: pendingObjects.length,
  };
}

const handler = async (event) => {
  console.info("New event received ", event);
  if (isSqsEvent(event)) {
    return handleSqsEvent(event);
  }

  if (isScheduledEvent(event)) {
    return handleScheduledEvent();
  }

  throw new Error("Unsupported trigger type. Expected SQS or Scheduled Event.");
};

module.exports = {
  handler
};