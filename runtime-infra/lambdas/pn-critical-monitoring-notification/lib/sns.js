const { SNSClient, PublishCommand } = require("@aws-sdk/client-sns");

const snsClient = new SNSClient();

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