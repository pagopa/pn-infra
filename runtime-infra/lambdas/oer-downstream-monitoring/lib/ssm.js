const { SSMClient, GetParameterCommand, PutParameterCommand } = require('@aws-sdk/client-ssm');

const ssmClient = new SSMClient();

function getParameterName(metricName) {
  return `/pn-infra-monitoring/oer-sla-validation-monitoring/${metricName}-start-time`;
}

function getDefaultStartTimeIsoHour() {
  const now = new Date();
  now.setUTCMinutes(0, 0, 0);
  now.setUTCHours(now.getUTCHours() - 2);
  return now.toISOString();
}

async function getOrCreateStartTimeParameter(metricName) {
  const parameterName = getParameterName(metricName);
  const defaultStartTime = getDefaultStartTimeIsoHour();

  try {
    const response = await ssmClient.send(new GetParameterCommand({ Name: parameterName }));
    const value = response.Parameter && response.Parameter.Value;

    if (value && value.trim().length > 0) {
      return {
        parameterName,
        startTime: value,
        created: false,
      };
    }

    // Parameter exists but is empty: initialize it to previous hour.
    await ssmClient.send(
      new PutParameterCommand({
        Name: parameterName,
        Type: 'String',
        Value: defaultStartTime,
        Overwrite: true,
      })
    );

    return {
      parameterName,
      startTime: defaultStartTime,
      created: false,
    };
  } catch (error) {
    if (error.name !== 'ParameterNotFound') {
      throw error;
    }
  }

  await ssmClient.send(
    new PutParameterCommand({
      Name: parameterName,
      Type: 'String',
      Value: defaultStartTime,
      Overwrite: false,
    })
  );

  return {
    parameterName,
    startTime: defaultStartTime,
    created: true,
  };
}

async function updateStartTimeParameter(parameterName, startTime) {
  await ssmClient.send(
    new PutParameterCommand({
      Name: parameterName,
      Type: 'String',
      Value: startTime,
      Overwrite: true,
    })
  );
}

module.exports = {
  getOrCreateStartTimeParameter,
  updateStartTimeParameter,
};
