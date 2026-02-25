const { LambdaClient, GetEventSourceMappingCommand } = require("@aws-sdk/client-lambda");

const lambdaClient = new LambdaClient();

async function getEventSourceMapping(uuid){
  const input = { // GetEventSourceMappingRequest
    UUID: uuid, // required
  };
  const command = new GetEventSourceMappingCommand(input);
  const response = await lambdaClient.send(command);
  return response
}

module.exports = {
  getEventSourceMapping
};

