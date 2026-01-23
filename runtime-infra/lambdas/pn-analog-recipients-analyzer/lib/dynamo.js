
const { DynamoDBClient, QueryCommand  } = require("@aws-sdk/client-dynamodb");
const { fromIni } = require("@aws-sdk/credential-providers");
//const dynamoDBClient = new DynamoDBClient();

const dynamoDBClient = new DynamoDBClient({
    region: "eu-south-1",
    credentials: fromIni({
      profile: "sso_pn-core-prod",
    })
  });



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

