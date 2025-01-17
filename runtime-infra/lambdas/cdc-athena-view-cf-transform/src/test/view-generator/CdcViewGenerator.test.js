const { CdcViewGenerator } = require('../../app/view-generator/CdcViewGenerator.js');
const { expect } = require('chai');

describe("CdcViewGenerator tests", function () {

  it("should support pn-Notification table", async () => {
    const params = {
      DatabaseName: 'cdc_analytics_database',
      CatalogName : 'awsdatacatalog',
      CdcTableName: 'pn_notifications_table',
      CdcParsedTableName: 'pn_notifications_table_parsed',
      CdcViewName: 'pn_notifications_view',
      CdcKeysType: 'struct<iun:struct<S:string>>',
      CdcNewImageType: `
        struct<
          iun:struct<S:string>,
          taxonomyCode:struct<S:string>,
          group:struct<S:string>,
          version:struct<N:string,S:string>,
          recipients:struct<L:array<struct<M:struct<
            denomination:struct<NULL:boolean>,
            digitalDomicile:struct<NULL:boolean>,
            payments:struct<L:array<struct<M:struct<
              applyCost:struct<BOOL:boolean>,
              creditorTaxId:struct<S:string>,
              noticeCode:struct<S:string>,
              f24:struct<M:struct<
                applyCost:struct<BOOL:boolean>,
                title:struct<S:string>
              >>
            >>>>,  
            recipientId:struct<S:string>,
            recipientType:struct<S:string>,
          >>>>  
        >`,
      CdcRecordFilter: "NOT regexp_like(dynamodb_Keys_iun, '.*##.*')"
    };

    const expectedCloudformationColumns = [
        {
          "Name": "group",
          "Type": "string"
        },
        {
          "Name": "iun",
          "Type": "string"
        },
        {
          "Name": "recipients",
          "Type": "array<struct<recipientId:string,recipientType:string,payments:array<struct<applyCost:boolean,creditorTaxId:string,f24_applyCost:boolean,f24_title:string,noticeCode:string>>>>"
        },
        {
          "Name": "taxonomyCode",
          "Type": "string"
        },
        {
          "Name": "version",
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
    
    const expectedViewData = {
        originalSql: trimCodeIndent( 12, `
            WITH simplified_data AS (
                SELECT
                    "dynamodb"."NewImage"."group"."S" AS "group",
                    "dynamodb"."NewImage"."iun"."S" AS "iun",
                    transform( "dynamodb"."NewImage"."recipients"."L", (elem0) -> 
                        cast(row(
                            elem0."M"."recipientId"."S",
                            elem0."M"."recipientType"."S",
                            transform( elem0."M"."payments"."L", (elem1) -> 
                                cast(row(
                                    elem1."M"."applyCost"."BOOL",
                                    elem1."M"."creditorTaxId"."S",
                                    elem1."M"."f24"."M"."applyCost"."BOOL",
                                    elem1."M"."f24"."M"."title"."S",
                                    elem1."M"."noticeCode"."S"
                                ) AS row(
                                    "applyCost" BOOLEAN,
                                    "creditorTaxId" VARCHAR,
                                    "f24_applyCost" BOOLEAN,
                                    "f24_title" VARCHAR,
                                    "noticeCode" VARCHAR
                                ))
                            )
                        ) AS row(
                            "recipientId" VARCHAR,
                            "recipientType" VARCHAR,
                            "payments" array(row( "applyCost" BOOLEAN, "creditorTaxId" VARCHAR, "f24_applyCost" BOOLEAN, "f24_title" VARCHAR, "noticeCode" VARCHAR ))
                        ))
                    ) AS "recipients",
                    "dynamodb"."NewImage"."taxonomyCode"."S" AS "taxonomyCode",
                    coalesce("dynamodb"."NewImage"."version"."N","dynamodb"."NewImage"."version"."S") AS "version",
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
            WHERE
                (NOT regexp_like(dynamodb_Keys_iun, '.*##.*'))
          `),
        catalog: "awsdatacatalog",
        schema: "cdc_analytics_database",
        columns: [
          {
            "name": "group",
            "type": "VARCHAR"
          },
          {
            "name": "iun",
            "type": "VARCHAR"
          },
          {
            "name": "recipients",
            "type": "array(row( \"recipientId\" VARCHAR, \"recipientType\" VARCHAR, \"payments\" array(row( \"applyCost\" BOOLEAN, \"creditorTaxId\" VARCHAR, \"f24_applyCost\" BOOLEAN, \"f24_title\" VARCHAR, \"noticeCode\" VARCHAR )) ))"
          },
          {
            "name": "taxonomyCode",
            "type": "VARCHAR"
          },
          {
            "name": "version",
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

    
    const viewGenerator = new CdcViewGenerator( params );
    const cloudformationColumns = viewGenerator.buildCloudFormationStorageDescriptorColumns();
    const viewData = viewGenerator.buildPrestoViewData();
    const viewString = viewGenerator.buildPrestoViewString();

    expect( cloudformationColumns ).to.be.deep.equals( expectedCloudformationColumns );
    expect( viewData ).to.be.deep.equals( expectedViewData );

    const bas64string = viewString.replace(/.*Presto View:(.*) \*\/.*/, "$1").trim();
    const reversedViewStringData = JSON.parse( atob( bas64string ));
    expect( reversedViewStringData ).to.be.deep.equals( expectedViewData )    
  });

})

it("should support pn-Timeline table", async () => {
  const params = {
    DatabaseName: 'cdc_analytics_database',
    CatalogName : 'awsdatacatalog',
    CdcTableName: 'pn_timelines_table',
    CdcParsedTableName: 'pn_timelines_table_parsed',
    CdcViewName: 'pn_timelines_view',
    CdcKeysType: 'struct<iun:struct<S:string>,timelineElementId:struct<S:string>>',
    CdcNewImageType: `
      struct<
        iun:struct<S:string>,
        timelineElementId:struct<S:string>,
        details:struct<M:struct<
          f24Attachments:struct<L:array<struct<S:string>>>,
          vat:struct<N:string>,
          relatedFeedbackTimelineId:struct<S:string>,
          aarTemplateType:struct<S:string>
        >>
      >`
  };

  const expectedCloudformationColumns = [
      {
        "Name": "details_aarTemplateType",
        "Type": "string"
      },
      {
        "Name": "details_f24Attachments",
        "Type": "array<struct<_elem_value:string>>"
      },
      {
        "Name": "details_relatedFeedbackTimelineId",
        "Type": "string"
      },
      {
        "Name": "details_vat",
        "Type": "string"
      },
      {
        "Name": "iun",
        "Type": "string"
      },
      {
        "Name": "timelineElementId",
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
        "Name": "dynamodb_keys_timelineElementId",
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
  
  const expectedViewData = {
      originalSql: trimCodeIndent( 10, `
          WITH simplified_data AS (
              SELECT
                  "dynamodb"."NewImage"."details"."M"."aarTemplateType"."S" AS "details_aarTemplateType",
                  transform( "dynamodb"."NewImage"."details"."M"."f24Attachments"."L", (elem0) -> 
                      cast(row(
                          elem0."S"
                      ) AS row(
                          "_elem_value" VARCHAR
                      ))
                  ) AS "details_f24Attachments",
                  "dynamodb"."NewImage"."details"."M"."relatedFeedbackTimelineId"."S" AS "details_relatedFeedbackTimelineId",
                  "dynamodb"."NewImage"."details"."M"."vat"."N" AS "details_vat",
                  "dynamodb"."NewImage"."iun"."S" AS "iun",
                  "dynamodb"."NewImage"."timelineElementId"."S" AS "timelineElementId",
                  "dynamodb"."SizeBytes" AS "dynamodb_SizeBytes",
                  "dynamodb"."Keys"."iun"."S" AS "dynamodb_keys_iun",
                  "dynamodb"."Keys"."timelineElementId"."S" AS "dynamodb_keys_timelineElementId",
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
                  "cdc_analytics_database"."pn_timelines_table" t
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
          "name": "details_aarTemplateType",
          "type": "VARCHAR"
        },
        {
          "name": "details_f24Attachments",
          "type": "array(row( \"_elem_value\" VARCHAR ))"
        },
        {
          "name": "details_relatedFeedbackTimelineId",
          "type": "VARCHAR"
        },
        {
          "name": "details_vat",
          "type": "VARCHAR"
        },
        {
          "name": "iun",
          "type": "VARCHAR"
        },
        {
          "name": "timelineElementId",
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
          "name": "dynamodb_keys_timelineElementId",
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

  
  const viewGenerator = new CdcViewGenerator( params );
  const cloudformationColumns = viewGenerator.buildCloudFormationStorageDescriptorColumns();
  const viewData = viewGenerator.buildPrestoViewData();
  const viewString = viewGenerator.buildPrestoViewString();

  expect( cloudformationColumns ).to.be.deep.equals( expectedCloudformationColumns );
  expect( viewData ).to.be.deep.equals( expectedViewData );

  const bas64string = viewString.replace(/.*Presto View:(.*) \*\/.*/, "$1").trim();
  const reversedViewStringData = JSON.parse( atob( bas64string ));
  expect( reversedViewStringData ).to.be.deep.equals( expectedViewData )    
});


it("should support string and long translation", async () => {
  const params = {
    DatabaseName: 'cdc_analytics_database',
    CatalogName : 'awsdatacatalog',
    CdcTableName: 'aa',
    CdcParsedTableName: 'aa_parsed',
    CdcViewName: 'aa_view',
    CdcKeysType: 'struct<iun:struct<S:string>>',
    CdcNewImageType: `
      struct<
        iun:struct<S:string>,
        quantity:struct<N:long>
      >`,
    CdcRecordFilter: ""
  };

  const expectedColumns = [
      {
        name: "iun",
        type: "VARCHAR"
      },
      {
        name: "quantity",
        type: "BIGINT"
      }
    ];
  const interestingColumns = expectedColumns.map( el => el.name );

  const viewGenerator = new CdcViewGenerator( params );
  const cloudformationColumns = viewGenerator.buildCloudFormationStorageDescriptorColumns();
  const actualMappedColumns = viewGenerator.buildPrestoViewData().columns
                            .filter( el => interestingColumns.includes( el.name ) );

  expect( actualMappedColumns ).to.be.deep.equals( expectedColumns );
});

it("should support unionAllQuery", async () => {
  const params = {
    DatabaseName: 'cdc_analytics_database',
    CatalogName : 'awsdatacatalog',
    CdcTableName: 'aa',
    CdcParsedTableName: 'aa_parsed',
    CdcViewName: 'aa_view',
    CdcKeysType: 'struct<iun:struct<S:string>>',
    CdcNewImageType: `
      struct<
        iun:struct<S:string>,
        quantity:struct<N:long>
      >`,
    CdcRecordFilter: ""
  };

  const expectedQuery = ""
                      + "  SELECT * FROM \"aa_view\" \n"
                      + "    WHERE p_year = lpad( cast( year(current_date) as varchar), 4, '0') \n"
                      + "      AND p_month = lpad( cast( month(current_date) as varchar), 2, '0') \n"
                      + "      AND p_day = lpad( cast( day(current_date) as varchar), 2, '0') \n"
                      + "UNION ALL \n"
                      + "  SELECT * FROM \"aa_parsed\" "
                      ;
  const viewGenerator = new CdcViewGenerator( params );
  const actualQuery = viewGenerator.unionAllQuery();
  
  expect( actualQuery ).to.be.equals( expectedQuery );
});


function trimCodeIndent( codeIndentSize, str ) {
  const result = str.split("\n")
     .filter( el => el.trim().length > 0 )
     .map( el => el.substring( codeIndentSize ))
     .join("\n")
     ;
  return result;
}
