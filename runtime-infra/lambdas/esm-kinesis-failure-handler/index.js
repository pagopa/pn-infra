const { Metrics, MetricUnits } = require("@aws-lambda-powertools/metrics");
const { getEventSourceMapping } = require("./lib/lambda");

const metrics = new Metrics({
  namespace: "ESM/Kinesis",
  serviceName: "esm-failure-tracker",
});

const handler = async (event) => {
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

    const functionName =
      eventSourceMapping?.FunctionArn?.split(":").pop();

    const streamName =
      eventSourceMapping?.EventSourceArn?.split(":")
        .pop()
        .split("/")
        .pop();

    // 👉 metriche
    metrics.addDimension("FunctionName", functionName || "unknown");
    metrics.addDimension("StreamName", streamName || "unknown");

    metrics.addMetric("ProcessingFailures", MetricUnits.Count, 1);

    return { statusCode: 200 };
  } catch (error) {
    console.error("Error handling Kinesis failure:", error);

    metrics.addMetric("ProcessingFailures", MetricUnits.Count, 1);

    return { statusCode: 500 };
  } finally {
    metrics.publishStoredMetrics();
  }
};

module.exports = { handler };