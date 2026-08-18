const path = require('path');
const { CloudWatchClient, PutMetricDataCommand } = require('@aws-sdk/client-cloudwatch');

const METRIC_NAMESPACE = 'SEND/BusinessMetrics';
const MAX_METRICS_PER_CALL = 20;
const cloudWatchClient = new CloudWatchClient();

function buildMetricNameFromQueryName(queryName) {
  const baseName = path.basename(String(queryName || '').trim(), '.sql');
  const withoutNumericPrefix = baseName.replace(/^\d+_/, '');
  const sanitized = withoutNumericPrefix.replace(/[^A-Za-z0-9_]/g, '_');
  return sanitized || 'unknown_query';
}

async function putBusinessMetric(metricName, metricValue) {
  await putBusinessMetrics(metricName, [metricValue]);
}

async function putBusinessMetrics(metricName, metricValues) {
  if (!Array.isArray(metricValues) || metricValues.length === 0) {
    return;
  }

  for (let idx = 0; idx < metricValues.length; idx += MAX_METRICS_PER_CALL) {
    const chunk = metricValues.slice(idx, idx + MAX_METRICS_PER_CALL);
    const metricData = chunk.map((value) => ({
      MetricName: metricName,
      Unit: 'None',
      Value: value,
      Timestamp: new Date(),
      Dimensions: [
        {
          Name: metricName,
          Value: metricName,
        }
      ]
    }));

    const input = {
      Namespace: METRIC_NAMESPACE,
      MetricData: metricData,
    };

    await cloudWatchClient.send(new PutMetricDataCommand(input));
  }
}

module.exports = {
  buildMetricNameFromQueryName,
  putBusinessMetric,
  putBusinessMetrics,
};
