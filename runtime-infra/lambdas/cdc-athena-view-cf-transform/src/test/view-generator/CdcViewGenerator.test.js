const { CdcViewGenerator } = require('../../app/view-generator/CdcViewGenerator.js');
const { expect } = require('chai');

describe("CdcViewGenerator tests", function () {
  
  it("should support pn-Notification table", async () => {
    const params = {
      DatabaseName: 'cdc_analytics_database',
      CatalogName : 'awsdatacatalog',
      CdcTableName: 'pn_notifications_table',
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
          "Name": "dynamodb_SizeBytes",
          "Type": "bigint"
        },
        {
          "Name": "dynamodb_keys_iun",
          "Type": "string"
        },
        {
          "Name": "group",
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
        },
        {
          "Name": "version",
          "Type": "string"
        },
        {
          "Name": "recipients",
          "Type": "array<struct< \"recipientId\":string, \"recipientType\":string, \"payments\":array<struct< \"applyCost\":boolean, \"creditorTaxId\":string, \"f24_applyCost\":boolean, \"f24_title\":string, \"noticeCode\":string >> >>"
        }
      ];
    
    const expectedViewData = {
        originalSql: trimCodeIndent( 12, `
            WITH simplified_data AS (
                SELECT
                    "dynamodb"."SizeBytes" AS "dynamodb_SizeBytes",
                    "dynamodb"."Keys"."iun"."S" AS "dynamodb_keys_iun",
                    "dynamodb"."NewImage"."group"."S" AS "group",
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
                    "dynamodb"."NewImage"."taxonomyCode"."S" AS "taxonomyCode",
                    coalesce("dynamodb"."NewImage"."version"."N","dynamodb"."NewImage"."version"."S") AS "version",
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
                                )
                            )
                        ) AS row(
                            "recipientId" VARCHAR,
                            "recipientType" VARCHAR,
                            "payments" array(row( "applyCost" BOOLEAN, "creditorTaxId" VARCHAR, "f24_applyCost" BOOLEAN, "f24_title" VARCHAR, "noticeCode" VARCHAR ))
                        )
                    ) AS "recipients"
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
            "name": "dynamodb_SizeBytes",
            "type": "BIGINT"
          },
          {
            "name": "dynamodb_keys_iun",
            "type": "VARCHAR"
          },
          {
            "name": "group",
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
          },
          {
            "name": "version",
            "type": "VARCHAR"
          },
          {
            "name": "recipients",
            "type": "array(row( \"recipientId\" VARCHAR, \"recipientType\" VARCHAR, \"payments\" array(row( \"applyCost\" BOOLEAN, \"creditorTaxId\" VARCHAR, \"f24_applyCost\" BOOLEAN, \"f24_title\" VARCHAR, \"noticeCode\" VARCHAR )) ))"
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

function trimCodeIndent( codeIndentSize, str ) {
  const result = str.split("\n")
     .filter( el => el.trim().length > 0 )
     .map( el => el.substring( codeIndentSize ))
     .join("\n")
     ;
  return result;
}
