const { uploadFileToS3 } = require("./lib/s3");
const { scanRequest } = require("./lib/dynamo");
const { unmarshall } = require("@aws-sdk/util-dynamodb");


async function prepareDataObject(result ) {
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
  return str
}

async function _exportDynamoTableData(tableName) {
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
  const data = await prepareDataObject(results);
  console.log('Sono stati recuperati n° ' + results.length + ' elementi.');
  return data;
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
    const results = await _exportDynamoTableData(tableName.trim());
    await uploadFileToS3(bucketName, `QuickSightDataImport/${tableName}/${tableName}.csv`, results)
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