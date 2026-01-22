
const { DynamoDBClient, ScanCommand  } = require("@aws-sdk/client-dynamodb");

const dynamoDBClient = new DynamoDBClient();

async function scanRequest(tableName, lastEvaluatedKey){
  const input = { // ScanInput
    TableName: tableName, // required
  };
  lastEvaluatedKey ? input['ExclusiveStartKey'] = lastEvaluatedKey : null
  const command = new ScanCommand(input);
  const response = await dynamoDBClient.send(command);
  return response
}

module.exports = {
  scanRequest
};

