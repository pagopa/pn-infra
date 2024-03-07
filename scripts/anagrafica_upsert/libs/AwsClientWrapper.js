
const { fromIni } = require("@aws-sdk/credential-provider-ini");
const { DynamoDBClient, BatchWriteItemCommand, UpdateItemCommand, ScanCommand } = require("@aws-sdk/client-dynamodb");

function awsClientCfg( profile ) {
  const self = this;
  if(profile==='default') return {}

  return { 
    region: "eu-south-1", 
    credentials: fromIni({ 
      profile: profile,
    })
  }
}

class AwsClientsWrapper {

  constructor( envName ) {
    const ssoProfile = `${envName}`
    this._dynamoClient = new DynamoDBClient( awsClientCfg( ssoProfile ));
  }

  async _scanRequest(tableName, lastEvaluatedKey){
    const input = { // ScanInputno
      TableName: tableName, // required
    };
    lastEvaluatedKey ? input['ExclusiveStartKey'] = lastEvaluatedKey : null
    const command = new ScanCommand(input);
    const response = await this._dynamoClient.send(command);
    return response
  }

  async _batchWriteItems(tableName, items) {
    const content = []
    items.forEach(element => {
      content.push({ // WriteRequest
        PutRequest: { // PutRequest
          Item: element,
        },
      })
    });
    const input = { // BatchWriteItemInput
      RequestItems: { // BatchWriteItemRequestMap // required
        [tableName] : content,
      },
      ReturnConsumedCapacity: "TOTAL",
      ReturnItemCollectionMetrics: "SIZE",
    };
    var response = {}
    try {
      const command = new BatchWriteItemCommand(input);
      response = await this._dynamoClient.send(command);
    }
    catch (error) {
      console.error("Problem during BatchWriteItemCommand cause=", error)
      process.exit(1)
    }
    return response;
  }

  async _batchWriteItemsWithUpdate(tableName, tableConfig, items) {

    const keys = tableConfig.Keys

    for(let i=0; i<items.length; i++){  
      // update Item
      const item = items[i]
      const Key = {}
      let updateExpressionAccordingToItemProperties = ''
      let expressionAttributeNames = {}
      let expressionAttributeValues = {}
      for (const key in item) {
        if (keys.indexOf(key)>=0) {
          Key[key] = item[key]
          continue;
        }
        updateExpressionAccordingToItemProperties += `#${key} = :${key},`
        expressionAttributeNames[`#${key}`] = key
        expressionAttributeValues[`:${key}`] = item[key]
      }
      
      const input = {
        TableName: tableName,
        Key: Key,
        UpdateExpression: "SET "+updateExpressionAccordingToItemProperties.slice(0, -1),
        ExpressionAttributeNames: expressionAttributeNames,
        ExpressionAttributeValues: expressionAttributeValues,
        ReturnValues: "ALL_NEW"
      };

      try {
        const command = new UpdateItemCommand(input);
        const response = await this._dynamoClient.send(command);
      }
      catch (error) {
        console.error("Problem during UpdateItemCommand cause=", error)
        process.exit(1)
      }
    }
  }
}

exports.AwsClientsWrapper = AwsClientsWrapper;

