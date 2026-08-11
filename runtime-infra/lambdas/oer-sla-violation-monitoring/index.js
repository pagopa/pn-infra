const fs = require('fs');
const path = require('path');
const { queryExecutionParallel } = require('./lib/athena');

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

function normalizeQueryInputs(event, defaults) {
  const queryFiles = getQueryFileNames(event);

  return queryFiles.map((fileName, idx) => {
    const query = loadQueryFromResources(fileName);
    const safeName = path.basename(String(fileName).trim());

    return {
      name: safeName || `query-${idx + 1}`,
      query,
      workgroup: defaults.workgroup,
      database: defaults.database,
      outputLocation: defaults.outputLocation,
    };
  });
}

const handler = async (event = {}) => {
  const config = getRequiredConfig();
  const queryInputs = normalizeQueryInputs(event, config);

  console.log(`Executing ${queryInputs.length} Athena query(ies) in parallel`);

  const results = await queryExecutionParallel(queryInputs);

  for (const result of results) {
    console.log(`Result for ${result.name} - queryExecutionId: ${result.queryExecutionId}`);
    console.log(`Rows (${result.rowCount}):`);
    console.log(JSON.stringify(result.rows, null, 2));
  }

  return {
    executedQueries: results.length,
    results,
  };
};

module.exports = {
  handler
};