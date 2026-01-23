const { SNSClient, PublishCommand } = require("@aws-sdk/client-sns");
const { fromIni } = require("@aws-sdk/credential-providers");
//const snsClient = new SNSClient({ region: process.env.AWS_REGION });

const snsClient = new SNSClient({
    region: "eu-south-1",
    credentials: fromIni({
      profile: "sso_pn-core-dev",
    })
  });
async function publishMessageToSns(snsTopicArn, subject, message) {
  const params = {
    Subject: subject,
    Message: message,
    TopicArn: snsTopicArn,
  };

  try {
    const data = await snsClient.send(new PublishCommand(params));
    console.log("Message sent to SNS topic:", data.MessageId);
  } catch (err) {
    console.error("Error sending message to SNS topic:", err);
    throw err;
  }
}

module.exports = {
  publishMessageToSns,
};