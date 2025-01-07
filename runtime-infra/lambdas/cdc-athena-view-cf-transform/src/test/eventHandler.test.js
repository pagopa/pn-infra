const { handleEvent } = require("../app/eventHandler.js");
const { expect } = require('chai');

async function makeOneTest( baseEvent, expectedCloudformationColumns, expectedViewData ) {
  const columnEvent = JSON.parse(JSON.stringify( baseEvent ));
  columnEvent.requestId = columnEvent.requestId + "__col";
  columnEvent.params.OutputType = "StorageDescriptor-Columns";
  
  const columnResponse = await handleEvent( columnEvent )
  expect(columnResponse.requestId).to.be.equal( columnEvent.requestId );
  expect(columnResponse.fragment ).to.be.deep.equal( expectedCloudformationColumns );


  const viewEvent = JSON.parse(JSON.stringify( baseEvent ));
  viewEvent.requestId = viewEvent.requestId + "__view";
  viewEvent.params.OutputType = "ViewOriginalText";
  
  const viewResponse = await handleEvent( viewEvent )
  const bas64string = viewResponse.fragment.replace(/.*Presto View:(.*) \*\/.*/, "$1").trim();
  const reversedViewStringData = JSON.parse( atob( bas64string ));
  expect(viewResponse.requestId).to.be.equal( viewEvent.requestId );
  expect(reversedViewStringData ).to.be.deep.equal( expectedViewData );
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
        "Name": "dynamodb_SizeBytes",
        "Type": "bigint"
      },
      {
        "Name": "dynamodb_keys_iun",
        "Type": "string"
      },
      {
        "Name": "iun",
        "Type": "string"
      },
      {
        "Name": "kinesis_dynamodb_ApproximateCreationDateTime",
        "Type": "bigint"
      },
      {
        "Name": "p_day",
        "Type": "string"
      },
      {
        "Name": "p_hour",
        "Type": "string"
      },
      {
        "Name": "p_month",
        "Type": "string"
      },
      {
        "Name": "p_year",
        "Type": "string"
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
        "Name": "taxonomyCode",
        "Type": "string"
      }
    ];

    const expectedViewData = {
      originalSql: trimCodeIndent( 10, `
          WITH simplified_data AS (
              SELECT
                  "dynamodb"."SizeBytes" AS "dynamodb_SizeBytes",
                  "dynamodb"."Keys"."iun"."S" AS "dynamodb_keys_iun",
                  "dynamodb"."NewImage"."iun"."S" AS "iun",
                  "dynamodb"."ApproximateCreationDateTime" AS "kinesis_dynamodb_ApproximateCreationDateTime",
                  "p_day" AS "p_day",
                  "p_hour" AS "p_hour",
                  "p_month" AS "p_month",
                  "p_year" AS "p_year",
                  "awsregion" AS "stream_awsregion",
                  "eventid" AS "stream_eventid",
                  "eventname" AS "stream_eventname",
                  "recordformat" AS "stream_recordformat",
                  "tablename" AS "stream_tablename",
                  "useridentity" AS "stream_useridentity",
                  "dynamodb"."NewImage"."taxonomyCode"."S" AS "taxonomyCode"
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
          "name": "dynamodb_SizeBytes",
          "type": "BIGINT"
        },
        {
          "name": "dynamodb_keys_iun",
          "type": "VARCHAR"
        },
        {
          "name": "iun",
          "type": "VARCHAR"
        },
        {
          "name": "kinesis_dynamodb_ApproximateCreationDateTime",
          "type": "BIGINT"
        },
        {
          "name": "p_day",
          "type": "VARCHAR"
        },
        {
          "name": "p_hour",
          "type": "VARCHAR"
        },
        {
          "name": "p_month",
          "type": "VARCHAR"
        },
        {
          "name": "p_year",
          "type": "VARCHAR"
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
          "name": "taxonomyCode",
          "type": "VARCHAR"
        }
      ]
    };

    await makeOneTest( baseEvent, expectedCloudformationColumns, expectedViewData );
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

    await makeOneTest( baseEvent, expectedCloudformationColumns, expectedViewData );
  });

  it("correct output type is required", async () => { 
    const evt = {
      requestId: 'evtId1',
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
        Enabled: "true",
        OutputType: "WrongOutputType"
      }
    };

    try {
      await handleEvent( evt )
      expect( "FAIL" ).to.be.equal("NEVER");
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
      expect( "FAIL" ).to.be.equal("NEVER");
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

    await makeOneTest( baseEvent, expectedCloudformationColumns, expectedViewData );
  })

})

