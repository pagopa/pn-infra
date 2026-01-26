const { queryRequest } = require("./lib/dynamo");
const { uploadFileToS3 } = require("./lib/s3");
const { publishMessageToSns } = require("./lib/sns");
const { unmarshall } = require("@aws-sdk/util-dynamodb");
const { trasformPrepareToSendAnalogTimelineKey, retrieveIunFromRequestId, prepareMessageToSns, retrieveInfoFromDetails} = require("./lib/utils");


const TIMELINE_DB_TABLE_NAME = 'pn-Timelines';
const PAPER_REQUEST_DELIVERY_DB_TABLE_NAME = 'pn-PaperRequestDelivery';
const PAPER_CHANNEL_DELIVERY_DRIVER_DB_TABLE_NAME = 'pn-PaperChannelDeliveryDriver';
const S3_BUCKET_NAME = process.env.MONITORING_BUCKET_NAME;
const SNS_TOPIC_ARN = process.env.SNS_TOPIC_ARN;
const HEADER_CSV = "RequestId, CAP, ExpectedRecipientID, ActualRecipientID, Courier, Code, ProductType\n";

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

  console.log(`Extracted requestId: ${analogMailInfo.requestId}, courier: ${analogMailInfo.courier}, registeredLetterCode: ${analogMailInfo.registeredLetterCode}`);

  const paperRequestData = await retrieveElementFromDynamoDB(PAPER_REQUEST_DELIVERY_DB_TABLE_NAME, "requestId", analogMailInfo.requestId);
  const productType = paperRequestData.productType;
  const driverCode = paperRequestData.driverCode;
  console.log(`Retrieved productType: ${productType}, driverCode: ${driverCode} from ${PAPER_REQUEST_DELIVERY_DB_TABLE_NAME}`);

  const driverData = await retrieveElementFromDynamoDB(PAPER_CHANNEL_DELIVERY_DRIVER_DB_TABLE_NAME, "deliveryDriverId", driverCode);
  const expectedRecipientId = driverData.unifiedDeliveryDriver;

  const timelineElement = await retrieveElementFromDynamoDB(TIMELINE_DB_TABLE_NAME, "iun", retrieveIunFromRequestId(analogMailInfo.requestId), "timelineElementId", trasformPrepareToSendAnalogTimelineKey(analogMailInfo.requestId));
  const recipientZip = timelineElement.details.physicalAddress.zip;
  if(expectedRecipientId !== analogMailInfo.courier) {
    console.warn(`RequestId ${analogMailInfo.requestId} mismatch between expected recipient ID: ${expectedRecipientId} and retrieved zip: ${recipientZip}`);
    
    return `${analogMailInfo.requestId}, ${recipientZip}, ${expectedRecipientId}, ${analogMailInfo.courier}, ${analogMailInfo.registeredLetterCode}, ${productType}`;
  } else {
    console.log(`RequestId ${analogMailInfo.requestId} recipient ID matches the retrieved zip code.`);
    return;
  }
}

const handler = async (event) => {
  console.info("New event received ", event);
  let csvContent = HEADER_CSV;
  const batchItemFailures = [];
  let foundMismatches = false;
  // Processa tutti i record, collezionando i fallimenti
  for (const record of event.Records) {
    let result;
    try {
      result = await processRecord(record);
    } catch (error) {
      console.log("Error processing record ", record, error);
      batchItemFailures.push({ itemIdentifier: record.messageId});
    }
    // Aggiungi la riga al contenuto del file CSV
    if (result) {
      foundMismatches = true;
      csvContent += `${result}\n`;
    }
  }
  // Se ci sono righe di dati, carica il file CSV su S3)
  if (foundMismatches) {
    //key name con path yyyyy/mm/dd/hh/mm/<timestamp>_mismatches.csv
    const s3Key = `analog-zip-mismatches/${new Date().toISOString().slice(0,16).replace(/[-:T]/g, "/")}/${Date.now()}_mismatches.csv`;

    try { 
      await exportDataToS3(csvContent, s3Key);
      for(const element of csvContent.split("\n").slice(1,-1)) {
        console.log("Publishing SNS message for element: ", element);
        const message = prepareMessageToSns(element)
        await publishMessageToSns(SNS_TOPIC_ARN, "Mismatch detection", message);
      }
    } catch (error) {
      console.error("Error uploading CSV report to S3", error);
      // In caso di errore di upload, segnala tutti i record come falliti
      batchItemFailures.splice(0, batchItemFailures.length); // Pulisce l'array
      for (const record of event.Records) {
        batchItemFailures.push({ itemIdentifier: record.messageId});
      }
    }
  }
  else {
    console.log("No mismatches found, skipping S3 upload and SNS notification.");
  }

  if (batchItemFailures.length > 0) {
    return {
      batchItemFailures: batchItemFailures
    };
  }
  return { status: "ok" };
};

module.exports = {
  handler
};