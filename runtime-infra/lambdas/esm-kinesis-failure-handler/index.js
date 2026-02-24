const { getEventSourceMapping } = require("./lib/lambda");

const handler = async (event) => {
  console.log("Received event:", JSON.stringify(event, null, 2));

  try {
    const objectKey = event?.detail?.object?.key;

    if (!objectKey) {
      console.error("Object key not found in event");
      return;
    }

    const esmUuidMatch = objectKey.match(
      /\/([0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[0-9a-f]{4}-[0-9a-f]{12})\//i
    );

    if (!esmUuidMatch) {
      console.error("ESM-UUID not found in object key:", objectKey);
      return;
    }

    const esmUuid = esmUuidMatch[1];

    const eventSourceMapping = await getEventSourceMapping(esmUuid);

    const functionName = eventSourceMapping?.FunctionArn?.split(":").pop();
    
    const streamName = eventSourceMapping?.EventSourceArn?.split(":").pop().split("/").pop();


    const metricData = {
      _aws: {
        Timestamp: Date.now(),
        CloudWatchMetrics: [
          {
            Namespace: "ESM/Kinesis",
            Dimensions: [["FunctionName", "StreamName"]],
            Metrics: [{ Name: "ProcessingFailures", Unit: "Count" }],
          },
        ],
      },
      FunctionName: functionName,
      StreamName: streamName,
      ProcessingFailures: 1,
    };

    console.log(JSON.stringify(metricData));

    return { statusCode: 200 };
  } catch (error) {
    console.error("Error handling Kinesis failure:", error);
    return { statusCode: 500 };
  }
};

module.exports = { handler };