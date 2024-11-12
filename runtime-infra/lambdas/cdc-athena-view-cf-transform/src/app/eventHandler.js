const { CdcViewGenerator } = require("./view-generator/CdcViewGenerator.js");

const OUTPUT_TYPE__STORAGE_COLUMNS = "StorageDescriptor-Columns";
const OUTPUT_TYPE__PRESTO_VIEW_DEF = "ViewOriginalText";

async function handleEvent(event) {
  console.debug(
    '{ "handleEvent_event":\n' + 
    + JSON.stringify( event, null, 2 )
    + "\n}"
  )
  const params = event["params"]
  const outputType = params.OutputType;
  const enabled = params.Enabled == "true";

  let fragmentResult;
  
  // - Keep separation from enabled and disabled code to 
  //   have more probability that transformation don't 
  //   fail if it is not needed
  if ( enabled ) {
    const cdcViewGenerator = new CdcViewGenerator( params );
    if ( outputType == OUTPUT_TYPE__STORAGE_COLUMNS ) {
      fragmentResult = cdcViewGenerator.buildCloudFormationStorageDescriptorColumns();
    }
    else if ( outputType == OUTPUT_TYPE__PRESTO_VIEW_DEF ) {
      const viewData = cdcViewGenerator.buildPrestoViewData();
      console.debug("QUERY:\n" + viewData.originalSql )
      console.debug(
          '{ "VIEW_DATA":\n'
          + JSON.stringify( viewData, null, 2 )
          + "\n}"
        );
      fragmentResult = cdcViewGenerator.buildPrestoViewString();
    }
    else {
      throw new Error("Output Type not supported " + outputType );
    }
  }

  // - Do nothing but return some well-structured cloudformation fragment
  else {
    if ( outputType == OUTPUT_TYPE__STORAGE_COLUMNS ) {
      fragmentResult = [{
          "Name": "fake_column",
          "Type": "string"
        }];
    }
    else if ( outputType == OUTPUT_TYPE__PRESTO_VIEW_DEF ) {
      const fakeViewData = {
          originalSql: "SELECT 'a_value' AS fake_column",
          catalog: params.CatalogName || "awsdatacatalog",
          schema: params.DatabaseName || "database_name",
          columns: [{
              "name": "fake_column",
              "type": "VARCHAR"
            }]
        };
      fragmentResult = "/* Presto View: " + btoa(JSON.stringify( fakeViewData )) + " */";
    }
    else {
      // - Fail because do not know the needed result format
      throw new Error("Output Type not supported " + outputType );
    }

  }

  return {
    requestId: event.requestId,
    fragment: fragmentResult,
    status: 'success'
  }
}

exports.handleEvent = handleEvent;
