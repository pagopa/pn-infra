const { getEventSourceMapping } = require("./lib/lambda");

export const handler = async (event) => {
  console.log("Received event:", JSON.stringify(event, null, 2));

  
  // Extract ESM-UUID from the object key
  const esmUuidMatch = objectKey.match(/\/([a-f0-9-]{36})\//);
  if (!esmUuidMatch) {
    console.error("ESM-UUID not found in object key:", objectKey);
    return;
  }
  const esmUuid = esmUuidMatch[1];
  console.log("Extracted ESM-UUID:", esmUuid);

  const eventSourceMapping = await getEventSourceMapping(esmUuid);
  console.log("Retrieved Event Source Mapping:", eventSourceMapping);

  // Create metrics using EMF format
  const metricData = {
    "_aws": {
      "Timestamp": new Date().getTime(),
      "CloudWatchMetrics": [
        {
          "Namespace": "ESM/KinesisFailures",
          "Dimensions": [["FunctionName"]],
          "Metrics": [
            {
              "Name": "KinesisWriteFailures",
              "Unit": "Count"
            }
          ]
        }
      ]
    },
    "FunctionName": eventSourceMapping.FunctionArn.split(":").slice(-1)[0],
    "KinesisWriteFailures": 1
  };

  console.log("EMF Metric Data:", JSON.stringify(metricData, null, 2));

  // Here you would typically send the metricData to CloudWatch Logs, which will be automatically parsed by EMF
  // For example, you can use console.log to output the metric data, and it will be picked up by CloudWatch Logs
  console.log(JSON.stringify(metricData));
};