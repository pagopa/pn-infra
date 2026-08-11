const { AthenaClient, StartQueryExecutionCommand, GetQueryExecutionCommand, GetQueryResultsCommand } = require("@aws-sdk/client-athena");

const client = new AthenaClient();

async function startQueryExecution(workgroup, queryString, database, outputLocation) {
  const input = {
    QueryString: queryString,
    WorkGroup: workgroup,
    QueryExecutionContext: {
      Database: database
    },
    ResultConfiguration: {
      OutputLocation: outputLocation,
    }
  };
  
  const command = new StartQueryExecutionCommand(input);
  const response = await client.send(command);
  return response.QueryExecutionId;
}

async function getQueryExecution(queryExecutionId) {
  const input = {
    QueryExecutionId: queryExecutionId
  };

  const command = new GetQueryExecutionCommand(input);
  const response = await client.send(command);
  return response.QueryExecution;
}

function mapRowToObject(row, columnInfo) {
  const values = row.Data || [];
  const result = {};

  for (let idx = 0; idx < columnInfo.length; idx++) {
    const colName = columnInfo[idx].Name;
    const colValue = values[idx] && values[idx].VarCharValue !== undefined
      ? values[idx].VarCharValue
      : null;
    result[colName] = colValue;
  }

  return result;
}

function isHeaderRow(row, columnInfo) {
  if (!row || !row.Data || row.Data.length === 0) {
    return false;
  }

  return columnInfo.every((col, idx) => {
    const value = row.Data[idx] && row.Data[idx].VarCharValue;
    return value === col.Name;
  });
}

async function getQueryResultsPaginated(queryExecutionId) {
  const rows = [];
  let nextToken;
  let columnInfo = [];
  let pageIndex = 0;

  do {
    const input = {
      QueryExecutionId: queryExecutionId,
      NextToken: nextToken
    };

    const response = await client.send(new GetQueryResultsCommand(input));
    const resultSet = response.ResultSet || {};
    columnInfo = resultSet.ResultSetMetadata ? resultSet.ResultSetMetadata.ColumnInfo || [] : columnInfo;
    const pageRows = resultSet.Rows || [];

    for (let rowIdx = 0; rowIdx < pageRows.length; rowIdx++) {
      const row = pageRows[rowIdx];
      if (pageIndex === 0 && rowIdx === 0 && isHeaderRow(row, columnInfo)) {
        continue;
      }
      rows.push(mapRowToObject(row, columnInfo));
    }

    nextToken = response.NextToken;
    pageIndex += 1;
  } while (nextToken);

  return rows;
}

async function queryExecution(workgroup, query, database, outputLocation) {
  const queryExecutionId = await startQueryExecution(workgroup, query, database, outputLocation);
  let queryExecution;
  let fileResult;

  while (true) {
    queryExecution = await getQueryExecution(queryExecutionId);
    const status = queryExecution.Status ? queryExecution.Status.State : 'UNKNOWN';
    fileResult = queryExecution.ResultConfiguration.OutputLocation;
    console.log(`Query ${queryExecutionId} execution status: ${status}`);

    if (status === 'SUCCEEDED') {
      break;
    } else if (status === 'FAILED' || status === 'CANCELLED') {
      throw new Error(`Query execution failed with status: ${status}`);
    }
    await new Promise(resolve => setTimeout(resolve, 3000));
  }

  const rows = await getQueryResultsPaginated(queryExecutionId);
  console.log(`Query ${queryExecutionId} result rows: ${rows.length}`);

  return {
    queryExecutionId,
    outputLocation: fileResult,
    rows,
    rowCount: rows.length,
    dataScannedInBytes: queryExecution.Statistics ? queryExecution.Statistics.DataScannedInBytes : undefined,
  };
}

async function queryExecutionParallel(queryInputs) {
  return Promise.all(
    queryInputs.map(async (queryInput, idx) => {
      const result = await queryExecution(
        queryInput.workgroup,
        queryInput.query,
        queryInput.database,
        queryInput.outputLocation
      );

      return {
        name: queryInput.name || `query-${idx + 1}`,
        ...result,
      };
    })
  );
}

module.exports = {
  queryExecution,
  queryExecutionParallel,
  getQueryResultsPaginated,
};