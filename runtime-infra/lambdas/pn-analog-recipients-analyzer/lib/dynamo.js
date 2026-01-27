
const { DynamoDBClient, QueryCommand  } = require("@aws-sdk/client-dynamodb");

const dynamoDBClient = new DynamoDBClient();

async function queryRequest(tableName, key, value, sKey = undefined, sValue = undefined) {
    const input = { // QueryInput
      TableName: tableName, // required
      KeyConditionExpression: "#k = :k",
      ExpressionAttributeNames: { // ExpressionAttributeNameMap
        "#k": key,
      },
      ExpressionAttributeValues: {
        ":k": { "S": value }
      },
    };

    // Query with Partition and Sort key
    if (sKey) {
      input.KeyConditionExpression = "#k = :k AND #sk = :sk"
      input.ExpressionAttributeNames["#sk"] = sKey
      input.ExpressionAttributeValues[":sk"] = { "S": sValue }
    }
    console.log("DynamoDB Query Input: ", JSON.stringify(input));
    const command = new QueryCommand(input);
    return await dynamoDBClient.send(command);
  }

module.exports = {
  queryRequest
};

