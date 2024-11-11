import { HiveType } from '../../app/hive-type-parser/HiveType.js';
import { HiveTypeParser } from '../../app/hive-type-parser/HiveTypeParser.js';
import { BaseHiveTypeVisitor } from '../../app/hive-type-parser/BaseHiveTypeVisitor.js';
import { expect } from 'chai';

class TestingHiveTypeVisitor extends BaseHiveTypeVisitor {

  enterNodeVisit( ht, context ) {
    context.visitNodeStart.push( ht.path )
    return context.doNotDescendPath 
           ? this.#checkDescend( ht, context ) 
           : super.enterNodeVisit( ht, context);
  }

  exitNodeVisit( ht, context ) {
    context.visitNodeEnd.push( ht.path )
    super.exitNodeVisit( ht, context )
  }

  #checkDescend( ht, context ) {
    let haveToDescend;

    let hasFilter = context.doNotDescendPath
    if ( hasFilter ) {
      haveToDescend =  JSON.stringify( ht.path ) !=  JSON.stringify( context.doNotDescendPath )
    } 
    else {
      haveToDescend = true;
    }
    return haveToDescend;
  }

}

function makeOneTest( typeString, expectedPathsStart, expectedPathsEnd, doNotDescendPath ) {
  let parser = new HiveTypeParser();
  let visitor =  new TestingHiveTypeVisitor();
    
  let ht = parser.parse( typeString );

  let context = { 
      visitNodeStart: [], 
      visitNodeEnd: [], 
      doNotDescendPath: doNotDescendPath 
    }
  visitor.visit( ht, context )

  expect( context.visitNodeStart ).to.be.deep.equal( expectedPathsStart );
  expect( context.visitNodeEnd ).to.be.deep.equal( expectedPathsEnd );
}

describe("BaseHiveTypeVisitor tests", function () {
  
  it("should support ordered struct navigation", async () => {
    const typeString = `
        struct< 
          field1: string, 
          field3: number, 
          field2: array< struct< 
            field2_2: boolean, 
            field2_1: byte 
          > > 
        >
      `;
    
    const expectedPaths = [
      [],
      ["field1"],
      ["field2"],
      ["field2", "[*]"],
      ["field2", "[*]", "field2_1"],
      ["field2", "[*]", "field2_2"],
      ["field3"]
    ]
    
    makeOneTest( typeString, expectedPaths, expectedPaths )

  });

  it("should support node skipping", async () => {
    const typeString = `
        struct< 
          field1: string, 
          field3: number, 
          field2: array< struct< 
            field2_2: boolean, 
            field2_1: byte 
          > > 
        >
      `;
    
    const expectedPathsStart = [
      [],
      ["field1"],
      ["field2"],
      ["field3"]
    ]

    const expectedPathsEnd = [
      [],
      ["field1"],
      ["field3"]
    ]
    
    makeOneTest( typeString, expectedPathsStart, expectedPathsEnd, ["field2"] )

  });

  it("should throw error if type is not supported", async () => {
    const ht = new HiveType("WRONG_CATEGORY", null, null, null, null);

    let visitor =  new BaseHiveTypeVisitor();
    
    expect( () => visitor.visit( ht, {} ) ).to.throw(Error)

  })

  it("should throw error if type is empty", async () => {
    let visitor =  new BaseHiveTypeVisitor();
    
    expect( () => visitor.visit( null, {} ) ).to.throw(Error)

  })

})
