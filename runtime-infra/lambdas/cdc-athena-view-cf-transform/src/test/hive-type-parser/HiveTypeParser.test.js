const { HiveTypeParser } = require('../../app/hive-type-parser/HiveTypeParser.js');
const { expect } = require('chai');

describe("HiveTypeParser tests", function () {
  
  it("should support simple type", async () => {
    
    let parser = new HiveTypeParser();
    let ht = parser.parse("  string ");
    
    expect( ht.category ).to.be.equal("SIMPLE");
    expect( ht.simpleType ).to.be.equal("string");
    expect( ht.path ).to.be.deep.equal( [] );
    expect( ht.sql() ).to.be.equal( "string" );
  });

  it("should support array type", async () => {
    
    let parser = new HiveTypeParser();
    let ht = parser.parse(" array < string >");
    
    expect( ht.category ).to.be.equal("ARRAY");
    expect( ht.path ).to.be.deep.equal( [] );
    expect( ht.arrayElementType.category ).to.be.equal("SIMPLE");
    expect( ht.arrayElementType.simpleType ).to.be.equal("string");
    expect( ht.arrayElementType.path ).to.be.deep.equal( ["[*]"] );

    expect( ht.sql() ).to.be.equal( "array<string>" );
  });

  it("should support struct type", async () => {
    
    let parser = new HiveTypeParser();
    let ht = parser.parse(" struct < field1 : string >");
    
    expect( ht.category ).to.be.equal("STRUCT");
    expect( ht.path ).to.be.deep.equal( [] );
    expect( ht.structChildren['field1'].category ).to.be.equal("SIMPLE");
    expect( ht.structChildren['field1'].simpleType ).to.be.equal("string");
    expect( ht.structChildren['field1'].path ).to.be.deep.equal( ["field1"] );

    expect( ht.sql() ).to.be.equal( "struct<field1:string>" );
  });

  it("struct fields should be written by alphabetical order", async () => {
    
    let parser = new HiveTypeParser();
    let ht = parser.parse(" struct < field2: number, field1 : string >");
    
    expect( ht.category ).to.be.equal("STRUCT");
    expect( ht.path ).to.be.deep.equal( [] );
    expect( ht.structChildren['field1'].category ).to.be.equal("SIMPLE");
    expect( ht.structChildren['field1'].simpleType ).to.be.equal("string");
    expect( ht.structChildren['field1'].path ).to.be.deep.equal( ["field1"] );
    expect( ht.structChildren['field2'].category ).to.be.equal("SIMPLE");
    expect( ht.structChildren['field2'].simpleType ).to.be.equal("number");
    expect( ht.structChildren['field2'].path ).to.be.deep.equal( ["field2"] );

    expect( ht.sql() ).to.be.equal( "struct<field1:string,field2:number>" );
  });

  it("should support array of structs", async () => {
    
    let parser = new HiveTypeParser();
    let ht = parser.parse("array< struct < field2: number, field1 : string >> ");
    
    expect( ht.category ).to.be.equal("ARRAY");
    expect( ht.path ).to.be.deep.equal( [] );
    expect( ht.arrayElementType.category ).to.be.equal("STRUCT");
    expect( ht.arrayElementType.path ).to.be.deep.equal( ["[*]"] );
    expect( ht.arrayElementType.structChildren['field1'].category ).to.be.equal("SIMPLE");
    expect( ht.arrayElementType.structChildren['field1'].simpleType ).to.be.equal("string");
    expect( ht.arrayElementType.structChildren['field1'].path ).to.be.deep.equal( ["[*]","field1"] );
    expect( ht.arrayElementType.structChildren['field2'].category ).to.be.equal("SIMPLE");
    expect( ht.arrayElementType.structChildren['field2'].simpleType ).to.be.equal("number");
    expect( ht.arrayElementType.structChildren['field2'].path ).to.be.deep.equal( ["[*]","field2"] );

    expect( ht.sql() ).to.be.equal( "array<struct<field1:string,field2:number>>" );
  });
  
  it("should support struct of array", async () => {
    
    let parser = new HiveTypeParser();
    let ht = parser.parse("struct < field2: array<number>, field1 : string > ");
    
    expect( ht.category ).to.be.equal("STRUCT");
    expect( ht.path ).to.be.deep.equal( [] );
    expect( ht.structChildren['field1'].category ).to.be.equal("SIMPLE");
    expect( ht.structChildren['field1'].simpleType ).to.be.equal("string");
    expect( ht.structChildren['field1'].path ).to.be.deep.equal( ["field1"] );
    expect( ht.structChildren['field2'].category ).to.be.equal("ARRAY");
    expect( ht.structChildren['field2'].path ).to.be.deep.equal( ["field2"] );
    expect( ht.structChildren['field2'].arrayElementType.category ).to.be.equal("SIMPLE");
    expect( ht.structChildren['field2'].arrayElementType.simpleType ).to.be.equal("number");
    expect( ht.structChildren['field2'].arrayElementType.path ).to.be.deep.equal( ["field2", "[*]"] );
    
    expect( ht.sql() ).to.be.equal( "struct<field1:string,field2:array<number>>" );
  });

  it("should support struct of array of struct", async () => {
    
    let parser = new HiveTypeParser();
    let ht = parser.parse("struct < field2: array<struct<field2_1:number>>, field1 : string > ");
    
    expect( ht.category ).to.be.equal("STRUCT");
    expect( ht.path ).to.be.deep.equal( [] );
    expect( ht.structChildren['field1'].category ).to.be.equal("SIMPLE");
    expect( ht.structChildren['field1'].simpleType ).to.be.equal("string");
    expect( ht.structChildren['field1'].path ).to.be.deep.equal( ["field1"] );
    expect( ht.structChildren['field2'].category ).to.be.equal("ARRAY");
    expect( ht.structChildren['field2'].path ).to.be.deep.equal( ["field2"] );
    expect( ht.structChildren['field2'].arrayElementType.category ).to.be.equal("STRUCT");
    expect( ht.structChildren['field2'].arrayElementType.path ).to.be.deep.equal( ["field2", "[*]"] );
    expect( ht.structChildren['field2'].arrayElementType.structChildren['field2_1'].category ).to.be.equal("SIMPLE");
    expect( ht.structChildren['field2'].arrayElementType.structChildren['field2_1'].path ).to.be.deep.equal( ["field2", "[*]", "field2_1"] );
    expect( ht.structChildren['field2'].arrayElementType.structChildren['field2_1'].simpleType ).to.be.equal("number");
    
    expect( ht.sql() ).to.be.equal( "struct<field1:string,field2:array<struct<field2_1:number>>>" );
  });

  it("should detect premature end of string", async () => {
    
    const typeString = "struct < field2: number, field1 : string ";
    
    let parser = new HiveTypeParser();
    
    expect( () => parser.parse( typeString ) ).to.throws(Error);
  });

  it("should detect unused characters after type definition", async () => {
    
    const typeString = "struct < field2: number, field1 : string > a";
    
    let parser = new HiveTypeParser();
    
    expect( () => parser.parse( typeString ) ).to.throws(Error);
  });

  it("should detect wrong syntax", async () => {
    
    let parser = new HiveTypeParser();
    
    expect( () => parser.parse( "struct < field2 number>" ) ).to.throws(Error);
    expect( () => parser.parse( "struct > field2: number>" ) ).to.throws(Error);
  });

})
