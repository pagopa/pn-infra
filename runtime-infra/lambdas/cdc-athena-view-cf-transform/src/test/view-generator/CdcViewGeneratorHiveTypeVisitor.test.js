const { HiveTypeParser } = require('../../app/hive-type-parser/HiveTypeParser.js');
const { CdcViewGeneratorHiveTypeVisitor } = require('../../app/view-generator/CdcViewGeneratorHiveTypeVisitor.js');
const { expect } = require('chai');


function testOneType( 
      typeString, expectedDdlColumns, expectedDqlColumns, expectedQuery, codeIndent, 
      typeCustomizer = (el) => el,
      aliasCustomizer = (el) => el,
) {
  let parser = new HiveTypeParser();
  let ddlVisitor = new CdcViewGeneratorHiveTypeVisitor( "DDL", aliasCustomizer );
  let dqlVisitor = new CdcViewGeneratorHiveTypeVisitor( "DQL", aliasCustomizer, typeCustomizer );
    
  let ht = parser.parse( typeString );
  let ddlColumns = ddlVisitor.getViewColumns( ht )
  let dqlColumns = dqlVisitor.getViewColumns( ht )
  let query = dqlVisitor.getViewQuery( ht, "source_table", 2 );

  const trimmedExpectedQuery = expectedQuery
                             .split("\n") // Spezza per linea
                             .filter( l => l.trim().length > 0) // Elimina linee senza caratteri
                             .map( l => l.substring( codeIndent )) // Togli indentazione string literal
                             .join("\n"); // Reunisci le righe
  expect( ddlColumns ).to.be.deep.equal( expectedDdlColumns );
  expect( dqlColumns ).to.be.deep.equal( expectedDqlColumns );
  expect( query ).to.be.equal( trimmedExpectedQuery );
}

describe("CdcViewGeneratorHiveTypeVisitor tests", function () {
  
  it("should support simple struct with ordered fields", async () => {
    const typeString = `
        struct< 
          field1: string, 
          field3: number, 
          field2: boolean
        >
      `;
    
    const expectedColumns = [
      { name: "field1", type: "string" },
      { name: "field2", type: "boolean" },
      { name: "field3", type: "number" }
    ]

    const expectedQuery = `
    WITH simplified_data AS (
      SELECT
        "field1" AS "field1",
        "field2" AS "field2",
        "field3" AS "field3"
      FROM
        source_table t
    )
    SELECT
      *
    FROM
      simplified_data
    `
    
    const codeIndent = 4;

    testOneType( typeString, expectedColumns, expectedColumns, expectedQuery, codeIndent );
  });

  it("should support nested array and struct", async () => {
    const typeString = `
        struct< 
          field1: string, 
          field3: array<struct< field3_1: number>>, 
          field2: boolean
        >
      `;
    
    const expectedDdlColumns = [
      { name: "field1", type: "string" },
      { name: "field2", type: "boolean" },
      { name: "field3", type: "array<struct< \"field3_1\":number >>" }
    ]
    const expectedDdqColumns = [
      { name: "field1", type: "string" },
      { name: "field2", type: "boolean" },
      { name: "field3", type: "array(row( \"field3_1\" number ))" }
    ]

    const expectedQuery = `
    WITH simplified_data AS (
      SELECT
        "field1" AS "field1",
        "field2" AS "field2",
        transform( "field3", (elem0) -> 
          cast(row(
            elem0."field3_1"
          ) AS row(
            "field3_1" number
          )
        ) AS "field3"
      FROM
        source_table t
    )
    SELECT
      *
    FROM
      simplified_data
    `
    
    const codeIndent = 4;

    testOneType( typeString, expectedDdlColumns, expectedDdqColumns, expectedQuery, codeIndent );
  });

  it("should support dynamodb type alias removal", async () => {
    const typeString = `
        struct< 
          field1: string, 
          field3: struct< N: string, S:string, NULL: boolean>, 
          field2: boolean
        >
      `;
    
    const expectedDdlColumns = [
      { name: "field1", type: "string" },
      { name: "field2", type: "boolean" },
      { name: "field3", type: "string" }
    ]
    const expectedDdqColumns = [
      { name: "field1", type: "string" },
      { name: "field2", type: "boolean" },
      { name: "field3", type: "string" }
    ]

    const expectedQuery = `
    WITH simplified_data AS (
      SELECT
        "field1" AS "field1",
        "field2" AS "field2",
        coalesce("field3"."N","field3"."S") AS "field3"
      FROM
        source_table t
    )
    SELECT
      *
    FROM
      simplified_data
    `
    
    const codeIndent = 4;

    testOneType( typeString, expectedDdlColumns, expectedDdqColumns, expectedQuery, codeIndent );
  });


  it("should support alias customizer and type replacer", async () => {
    const typeString = `
        struct< 
          field1: string, 
          field3: number, 
          field2: array<struct< field2_1: number>>
        >
      `;
    
    const expectedDdlColumns = [
      { name: "Ffield1F", type: "string" },
      { name: "Ffield3F", type: "number" },
      { name: "Ffield2F", type: "array<struct< \"Ffield2_1F\":number >>" }
    ]
    const expectedDdqColumns = [
      { name: "Ffield1F", type: "TstringT" },
      { name: "Ffield3F", type: "TnumberT" },
      { name: "Ffield2F", type: "array(row( \"Ffield2_1F\" TnumberT ))" }
    ]

    const expectedQuery = `
    WITH simplified_data AS (
      SELECT
        "field1" AS "Ffield1F",
        "field3" AS "Ffield3F",
        transform( "field2", (elem0) -> 
          cast(row(
            elem0."field2_1"
          ) AS row(
            "Ffield2_1F" TnumberT
          )
        ) AS "Ffield2F"
      FROM
        source_table t
    )
    SELECT
      *
    FROM
      simplified_data
    `
    
    const codeIndent = 4;

    testOneType( 
        typeString, expectedDdlColumns, expectedDdqColumns, expectedQuery, codeIndent, 
        (el) => "T" + el + "T",
        (el) => "F" + el + "F"
      );
  });


})
