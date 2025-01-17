const { handleEvent } = require("../app/eventHandler.js");
const { expect } = require('chai');

async function makeOneTest( baseEvent, expectedCloudformationColumns, expectedCloudformationColumnsForCacheTable, expectedViewData, expectedUnionAllViewData ) {
  const columnEvent = JSON.parse(JSON.stringify( baseEvent ));
  columnEvent.requestId = columnEvent.requestId + "__col";
  columnEvent.params.OutputType = "StorageDescriptor-Columns";
  
  const columnResponse = await handleEvent( columnEvent )
  expect(columnResponse.requestId).to.be.equal( columnEvent.requestId );
  expect(columnResponse.fragment ).to.be.deep.equal( expectedCloudformationColumns );

  const cacheColumnEvent = JSON.parse(JSON.stringify( baseEvent ));
  cacheColumnEvent.requestId = columnEvent.requestId + "__col_noPart";
  cacheColumnEvent.params.OutputType = "StorageDescriptor-Columns-noParsedPartition";
  
  const cacheColumnResponse = await handleEvent( cacheColumnEvent )
  expect(cacheColumnResponse.requestId).to.be.equal( cacheColumnEvent.requestId );
  expect(cacheColumnResponse.fragment ).to.be.deep.equal( expectedCloudformationColumnsForCacheTable );


  const viewEvent = JSON.parse(JSON.stringify( baseEvent ));
  viewEvent.requestId = viewEvent.requestId + "__view";
  viewEvent.params.OutputType = "ViewOriginalText";
  
  const viewResponse = await handleEvent( viewEvent )
  const bas64string = viewResponse.fragment.replace(/.*Presto View:(.*) \*\/.*/, "$1").trim();
  const reversedViewStringData = JSON.parse( atob( bas64string ));
  expect(viewResponse.requestId).to.be.equal( viewEvent.requestId );
  expect(reversedViewStringData ).to.be.deep.equal( expectedViewData );


  const unionAllViewEvent = JSON.parse(JSON.stringify( baseEvent ));
  unionAllViewEvent.requestId = viewEvent.requestId + "__view_unionAll";
  unionAllViewEvent.params.OutputType = "ViewOriginalText-unionAll";
  
  const unionAllViewResponse = await handleEvent( unionAllViewEvent )
  const unionAllBas64string = unionAllViewResponse.fragment.replace(/.*Presto View:(.*) \*\/.*/, "$1").trim();
  const unionAllReversedViewStringData = JSON.parse( atob( unionAllBas64string ));
  expect(unionAllViewResponse.requestId).to.be.equal( unionAllViewEvent.requestId );
  expect(unionAllReversedViewStringData ).to.be.deep.equal( expectedUnionAllViewData );
}


function trimCodeIndent( codeIndentSize, str ) {
  const result = str.split("\n")
     .filter( el => el.trim().length > 0 )
     .map( el => el.substring( codeIndentSize ))
     .join("\n")
     ;
  return result;
}



describe("eventHandler tests", function () {
  it("should generate view", async () => {
      
    const baseEvent = {
        requestId: 'evtId1',
        params: {
          CatalogName : 'awsdatacatalog',
          DatabaseName: 'cdc_analytics_database',
          CdcTableName: 'pn_notifications_table',
          CdcParsedTableName: 'pn_notifications_table_parsed',
          CdcViewName: 'pn_notifications_view',
          CdcKeysType: 'struct<iun:struct<S:string>>',
          CdcNewImageType: `struct<
                              iun:struct<S:string>,
                              taxonomyCode:struct<S:string>
                            >`,
          CdcRecordFilter: "",
          Enabled: "true"
        }
      };
    
    const expectedCloudformationColumns = [
      {
        "Name": "iun",
        "Type": "string"
      },
      {
        "Name": "taxonomyCode",
        "Type": "string"
      },
      {
        "Name": "dynamodb_SizeBytes",
        "Type": "bigint"
      },
      {
        "Name": "dynamodb_keys_iun",
        "Type": "string"
      },
      {
        "Name": "kinesis_dynamodb_ApproximateCreationDateTime",
        "Type": "bigint"
      },
      {
        "Name": "stream_awsregion",
        "Type": "string"
      },
      {
        "Name": "stream_eventid",
        "Type": "string"
      },
      {
        "Name": "stream_eventname",
        "Type": "string"
      },
      {
        "Name": "stream_recordformat",
        "Type": "string"
      },
      {
        "Name": "stream_tablename",
        "Type": "string"
      },
      {
        "Name": "stream_useridentity",
        "Type": "string"
      },
      {
        "Name": "p_hour",
        "Type": "string"
      },
      {
        "Name": "p_year",
        "Type": "string"
      },
      {
        "Name": "p_month",
        "Type": "string"
      },
      {
        "Name": "p_day",
        "Type": "string"
      }
    ];

    const expectedCloudformationColumnsForCacheTable = [
      {
        "Name": "iun",
        "Type": "string"
      },
      {
        "Name": "taxonomyCode",
        "Type": "string"
      },
      {
        "Name": "dynamodb_SizeBytes",
        "Type": "bigint"
      },
      {
        "Name": "dynamodb_keys_iun",
        "Type": "string"
      },
      {
        "Name": "kinesis_dynamodb_ApproximateCreationDateTime",
        "Type": "bigint"
      },
      {
        "Name": "stream_awsregion",
        "Type": "string"
      },
      {
        "Name": "stream_eventid",
        "Type": "string"
      },
      {
        "Name": "stream_eventname",
        "Type": "string"
      },
      {
        "Name": "stream_recordformat",
        "Type": "string"
      },
      {
        "Name": "stream_tablename",
        "Type": "string"
      },
      {
        "Name": "stream_useridentity",
        "Type": "string"
      },
      {
        "Name": "p_hour",
        "Type": "string"
      }
    ];

    const expectedViewData = {
      originalSql: trimCodeIndent( 10, `
          WITH simplified_data AS (
              SELECT
                  "dynamodb"."NewImage"."iun"."S" AS "iun",
                  "dynamodb"."NewImage"."taxonomyCode"."S" AS "taxonomyCode",
                  "dynamodb"."SizeBytes" AS "dynamodb_SizeBytes",
                  "dynamodb"."Keys"."iun"."S" AS "dynamodb_keys_iun",
                  "dynamodb"."ApproximateCreationDateTime" AS "kinesis_dynamodb_ApproximateCreationDateTime",
                  "awsregion" AS "stream_awsregion",
                  "eventid" AS "stream_eventid",
                  "eventname" AS "stream_eventname",
                  "recordformat" AS "stream_recordformat",
                  "tablename" AS "stream_tablename",
                  "useridentity" AS "stream_useridentity",
                  "p_hour" AS "p_hour",
                  "p_year" AS "p_year",
                  "p_month" AS "p_month",
                  "p_day" AS "p_day"
              FROM
                  "cdc_analytics_database"."pn_notifications_table" t
          )
          SELECT
              *
          FROM
              simplified_data
        `),
      catalog: "awsdatacatalog",
      schema: "cdc_analytics_database",
      columns: [
        {
          "name": "iun",
          "type": "VARCHAR"
        },
        {
          "name": "taxonomyCode",
          "type": "VARCHAR"
        },
        {
          "name": "dynamodb_SizeBytes",
          "type": "BIGINT"
        },
        {
          "name": "dynamodb_keys_iun",
          "type": "VARCHAR"
        },
        {
          "name": "kinesis_dynamodb_ApproximateCreationDateTime",
          "type": "BIGINT"
        },
        {
          "name": "stream_awsregion",
          "type": "VARCHAR"
        },
        {
          "name": "stream_eventid",
          "type": "VARCHAR"
        },
        {
          "name": "stream_eventname",
          "type": "VARCHAR"
        },
        {
          "name": "stream_recordformat",
          "type": "VARCHAR"
        },
        {
          "name": "stream_tablename",
          "type": "VARCHAR"
        },
        {
          "name": "stream_useridentity",
          "type": "VARCHAR"
        },
        {
          "name": "p_hour",
          "type": "VARCHAR"
        },
        {
          "name": "p_year",
          "type": "VARCHAR"
        },
        {
          "name": "p_month",
          "type": "VARCHAR"
        },
        {
          "name": "p_day",
          "type": "VARCHAR"
        }
      ]
    };

    const expectedUnionAllViewData = {
      originalSql: trimCodeIndent( 10, `
            SELECT * FROM "pn_notifications_view" 
              WHERE p_year = lpad( cast( year(current_date) as varchar), 4, '0') 
                AND p_month = lpad( cast( month(current_date) as varchar), 2, '0') 
                AND p_day = lpad( cast( day(current_date) as varchar), 2, '0') 
          UNION ALL 
            SELECT * FROM "pn_notifications_table_parsed" 
        `),
      catalog: "awsdatacatalog",
      schema: "cdc_analytics_database",
      columns: [
        {
          "name": "iun",
          "type": "VARCHAR"
        },
        {
          "name": "taxonomyCode",
          "type": "VARCHAR"
        },
        {
          "name": "dynamodb_SizeBytes",
          "type": "BIGINT"
        },
        {
          "name": "dynamodb_keys_iun",
          "type": "VARCHAR"
        },
        {
          "name": "kinesis_dynamodb_ApproximateCreationDateTime",
          "type": "BIGINT"
        },
        {
          "name": "stream_awsregion",
          "type": "VARCHAR"
        },
        {
          "name": "stream_eventid",
          "type": "VARCHAR"
        },
        {
          "name": "stream_eventname",
          "type": "VARCHAR"
        },
        {
          "name": "stream_recordformat",
          "type": "VARCHAR"
        },
        {
          "name": "stream_tablename",
          "type": "VARCHAR"
        },
        {
          "name": "stream_useridentity",
          "type": "VARCHAR"
        },
        {
          "name": "p_hour",
          "type": "VARCHAR"
        },
        {
          "name": "p_year",
          "type": "VARCHAR"
        },
        {
          "name": "p_month",
          "type": "VARCHAR"
        },
        {
          "name": "p_day",
          "type": "VARCHAR"
        }
      ]
    };

    await makeOneTest( baseEvent, expectedCloudformationColumns, expectedCloudformationColumnsForCacheTable, expectedViewData, expectedUnionAllViewData );
  });

  it("should generate fake output if disabled", async () => {
      
    const baseEvent = {
        requestId: 'evtId2',
        params: {
          CatalogName : 'awsdatacatalog',
          DatabaseName: 'cdc_analytics_database',
          CdcTableName: 'pn_notifications_table',
          CdcViewName: 'pn_notifications_view',
          CdcKeysType: 'struct<iun:struct<S:string>>',
          CdcNewImageType: `struct<
                              iun:struct<S:string>,
                              taxonomyCode:struct<S:string>
                            >`,
          CdcRecordFilter: "",
          Enabled: "false"
        }
      };
    
    const expectedCloudformationColumns = [{
        "Name": "fake_column",
        "Type": "string"
      }];

    const expectedViewData = {
      originalSql: "SELECT 'a_value' AS fake_column",
      catalog: "awsdatacatalog",
      schema: "cdc_analytics_database",
      columns: [{
          "name": "fake_column",
          "type": "VARCHAR"
        }]
    };

    await makeOneTest( baseEvent, expectedCloudformationColumns, expectedCloudformationColumns, expectedViewData, expectedViewData );
  });

  it("correct output type is required", async () => { 
    const evt = {
      requestId: 'evtId1',
      params: {
        CatalogName : 'awsdatacatalog',
        DatabaseName: 'cdc_analytics_database',
        CdcTableName: 'pn_notifications_table',
        CdcParsedTableName: 'pn_notifications_table_parsed',
        CdcViewName: 'pn_notifications_view',
        CdcKeysType: 'struct<iun:struct<S:string>>',
        CdcNewImageType: `struct<
                            iun:struct<S:string>,
                            taxonomyCode:struct<S:string>
                          >`,
        CdcRecordFilter: "",
        Enabled: "true",
        OutputType: "WrongOutputType"
      }
    };

    try {
      await handleEvent( evt )
      expect( "CONTINUE" ).to.be.equal("NEVER");
    }
    catch( err ) {
      expect( "CATCH" ).to.be.equal("CATCH");
    }
  });

  it("correct output type is required also if disabled", async () => { 
    const evt = {
      requestId: 'evtId1',
      params: {
        CatalogName : 'awsdatacatalog',
        DatabaseName: 'cdc_analytics_database',
        CdcTableName: 'pn_notifications_table',
        CdcParsedTableName: 'pn_notifications_table_parsed',
        CdcViewName: 'pn_notifications_view',
        CdcKeysType: 'struct<iun:struct<S:string>>',
        CdcNewImageType: `struct<
                            iun:struct<S:string>,
                            taxonomyCode:struct<S:string>
                          >`,
        CdcRecordFilter: "",
        Enabled: "false",
        OutputType: "WrongOutputType"
      }
    };

    try {
      await handleEvent( evt )
      expect( "CONTINUE" ).to.be.equal("NEVER");
    }
    catch( err ) {
      expect( "CATCH" ).to.be.equal("CATCH");
    }
  });


  it("when disabled the only required parameter should be OutputType", async () => {
    const baseEvent = {
      requestId: 'evtId2',
      params: {
        
      }
    };
  
    const expectedCloudformationColumns = [{
        "Name": "fake_column",
        "Type": "string"
      }];

    const expectedViewData = {
      originalSql: "SELECT 'a_value' AS fake_column",
      catalog: "awsdatacatalog",
      schema: "database_name",
      columns: [{
          "name": "fake_column",
          "type": "VARCHAR"
        }]
    };

    await makeOneTest( baseEvent, expectedCloudformationColumns, expectedCloudformationColumns, expectedViewData, expectedViewData );
  })

})

