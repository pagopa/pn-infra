const fs = require('fs');
const path = require('path');
const { queryExecutionParallel } = require('./lib/athena');
const { buildMetricNameFromQueryName, putBusinessMetrics } = require('./lib/cloudwatch');
const { getOrCreateStartTimeParameter, updateStartTimeParameter } = require('./lib/ssm');

const METRIC_BATCH_SIZE = 20;

function loadQueryFromResources(fileName) {
  if (typeof fileName !== 'string' || fileName.trim().length === 0) {
    throw new Error('Each query file name must be a non-empty string.');
  }

  // Prevent loading files outside resources through path traversal.
  const normalizedName = path.basename(fileName.trim());
  const safeFileName = normalizedName.toLowerCase().endsWith('.sql')
    ? normalizedName
    : `${normalizedName}.sql`;
  const queryPath = path.join(__dirname, 'resources', safeFileName);

  if (!fs.existsSync(queryPath)) {
    throw new Error(`Query file not found in resources: ${safeFileName}`);
  }

  return fs.readFileSync(queryPath, 'utf8');
}

function getRequiredConfig() {
  const workgroup = process.env.ATHENA_WORKGROUP;
  const database = process.env.ATHENA_DATABASE;
  const outputLocation = process.env.ATHENA_OUTPUT_LOCATION;

  if (!workgroup) {
    throw new Error('Missing Athena workgroup. Provide ATHENA_WORKGROUP env var.');
  }
  if (!database) {
    throw new Error('Missing Athena database. Provide ATHENA_DATABASE env var.');
  }
  if (!outputLocation) {
    throw new Error('Missing Athena output location. Provide ATHENA_OUTPUT_LOCATION env var.');
  }

  return { workgroup, database, outputLocation };
}

function getQueryFileNames(event = {}) {
  if (Array.isArray(event.queryFiles) && event.queryFiles.length > 0) {
    return event.queryFiles;
  }
  if (Array.isArray(event.files) && event.files.length > 0) {
    return event.files;
  }
  if (typeof event.queryFile === 'string' && event.queryFile.trim().length > 0) {
    return [event.queryFile];
  }

  throw new Error('Missing query file names. Provide event.queryFiles (array) or event.queryFile (string).');
}

function applyStartTimeToQuery(queryTemplate, startTime) {
  if (typeof queryTemplate !== 'string') {
    throw new Error('Invalid query template, expected string.');
  }
  if (queryTemplate.indexOf('<START_TIME>') === -1) {
    throw new Error('Query does not contain <START_TIME> placeholder.');
  }

  return queryTemplate.replace(/<START_TIME>/g, startTime);
}

function toIsoHour(value) {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return null;
  }

  parsed.setUTCMinutes(0, 0, 0);
  return parsed.toISOString();
}

function getCurrentMinusTwoHoursIsoHour() {
  const now = new Date();
  now.setUTCHours(now.getUTCHours() - 2);
  return toIsoHour(now.toISOString());
}

async function normalizeQueryInputs(event, defaults) {
  const queryFiles = getQueryFileNames(event);
  const normalizedInputs = [];

  for (let idx = 0; idx < queryFiles.length; idx++) {
    const fileName = queryFiles[idx];
    const queryTemplate = loadQueryFromResources(fileName);
    const safeName = path.basename(String(fileName).trim());
    const metricName = buildMetricNameFromQueryName(safeName || `query-${idx + 1}`);
    const startTimeState = await getOrCreateStartTimeParameter(metricName);
    console.log(`Loaded start-time from Parameter Store ${startTimeState.parameterName}: ${startTimeState.startTime}`);
    const query = applyStartTimeToQuery(queryTemplate, startTimeState.startTime);
    console.log(`Applied <START_TIME> placeholder for query ${safeName || `query-${idx + 1}`}`);

    normalizedInputs.push({
      name: safeName || `query-${idx + 1}`,
      metricName,
      parameterName: startTimeState.parameterName,
      startTime: startTimeState.startTime,
      query,
      workgroup: defaults.workgroup,
      database: defaults.database,
      outputLocation: defaults.outputLocation,
    });
  }

  return normalizedInputs;
}

function toNumberOrNull(value) {
  if (value === null || value === undefined || value === '') {
    return null;
  }
  const numericValue = Number(value);
  return Number.isNaN(numericValue) ? null : numericValue;
}

function buildInsightsLog(metricName, resultName, queryExecutionId, row) {
  const diffHoursValue = row.diff_hours ?? row.diff_hour;

  return {
    event_type: metricName,
    query_name: resultName,
    query_execution_id: queryExecutionId,
    iun: row.iun ?? null,
    diff_hours: toNumberOrNull(diffHoursValue),
  };
}

const handler = async (event = {}) => {
  const config = getRequiredConfig();
  const queryInputs = await normalizeQueryInputs(event, config);
  const queryInputByName = new Map(queryInputs.map((item) => [item.name, item]));
  const metricBuffers = new Map(queryInputs.map((item) => [item.name, []]));

  const queryInputsWithHandlers = queryInputs.map((queryInput) => ({
    ...queryInput,
    onRow: async (row, executionContext) => {
      const metricName = queryInput.metricName;
      const logRecord = buildInsightsLog(metricName, queryInput.name, executionContext.queryExecutionId, row);
      console.log(JSON.stringify(logRecord));

      const metricValue = toNumberOrNull(row.diff_hours ?? row.diff_hour) ?? 0;
      const buffer = metricBuffers.get(queryInput.name);
      buffer.push(metricValue);

      if (buffer.length >= METRIC_BATCH_SIZE) {
        await putBusinessMetrics(metricName, buffer.splice(0, buffer.length));
      }
    }
  }));

  console.log(`Executing ${queryInputsWithHandlers.length} Athena query(ies) in parallel`);

  const results = await queryExecutionParallel(queryInputsWithHandlers);

  for (const result of results) {
    const queryContext = queryInputByName.get(result.name);
    const metricName = queryContext ? queryContext.metricName : buildMetricNameFromQueryName(result.name);
    const pendingMetrics = metricBuffers.get(result.name) || [];

    console.log(`Result for ${result.name} - queryExecutionId: ${result.queryExecutionId}`);
    console.log(`Rows (${result.rowCount}):`);

    if (pendingMetrics.length > 0) {
      await putBusinessMetrics(metricName, pendingMetrics.splice(0, pendingMetrics.length));
    }

    if (queryContext && result.rowCount > 0) {
      console.log(`Keeping start-time parameter ${queryContext.parameterName} unchanged (${queryContext.startTime}) because rows were found`);
    }

    if (queryContext && result.rowCount === 0) {
      const currentMinusTwoHours = getCurrentMinusTwoHoursIsoHour();
      await updateStartTimeParameter(queryContext.parameterName, currentMinusTwoHours);
      console.log(`Updated start-time parameter ${queryContext.parameterName} to current minus 2 hours ${currentMinusTwoHours} because no rows were found`);
    }
  }

  return {
    executedQueries: results.length,
    results,
  };
};

module.exports = {
  handler
};