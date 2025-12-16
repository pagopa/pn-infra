const { uploadFileToS3 } = require("./lib/s3");
const { scanRequest } = require("./lib/dynamo");
const fs = require('fs');
const { unmarshall } = require("@aws-sdk/util-dynamodb");
const path = require('path');

async function writeInFile(result, filename ) {
  fs.mkdirSync("result", { recursive: true });
  const delimiter = ';' // Using semicolon as delimiter
  const headers = Object.keys(unmarshall(result[0]))
  let str = ''
  str += headers.join(delimiter) + '\n'
  for (const item of result) {
    const unmarshalledItem = unmarshall(item)
    let row = []
    for (const header of headers) {
      row.push(unmarshalledItem[header])
    }
    str += row.join(delimiter) + '\n'
  }
  fs.writeFileSync(`result/${filename}.json`, str, 'utf-8')
  return `result/${filename}.json`
}

async function _exportDynamoTableData(tableName, json = true) {
  let first = true;
  var results = []
  var lastEvaluatedKey = null
  while (first || lastEvaluatedKey != null) {
    var res = await scanRequest(tableName, lastEvaluatedKey);
    if (res.LastEvaluatedKey) {
      lastEvaluatedKey = res.LastEvaluatedKey
    }
    else {
      lastEvaluatedKey = null;
      first = false;
    }
    results = results.concat(res.Items);
  }
  const filePath = await writeInFile(results, `${tableName}`)
  console.log('Sono stati memorizzati n° ' + results.length + ' elementi.');
  return filePath;
}

const handler = async (event) => {
  console.info("New event received ", event);
  const inputTableNames = process.env.DYNAMODB_TABLE_NAMES;
  const bucketName = process.env.MONITORING_BUCKET_NAME;
  if (!inputTableNames) {
    throw new Error("DYNAMODB_TABLE_NAMES environment variable is not set.");
  }
  if (!bucketName) {
    throw new Error("MONITORING_BUCKET_NAME environment variable is not set.");
  }
  const tableNames = inputTableNames.split(",");

  for (const tableName of tableNames) {
    console.log("Esportazione dati tabella DynamoDB: " + tableName);
    const filePath = await _exportDynamoTableData(tableName.trim(), false);
    await uploadFileToS3(bucketName, `QuickSightDataImport/${tableName}/${tableName}.json`, filePath)
    console.log("Esportazione dati tabella DynamoDB completata: " + tableName);
  }

  return {
    statusCode: 200,
    body: JSON.stringify({
      message: 'DynamoDB tables exported successfully',
    }),
  };
};

module.exports = {
  handler
}