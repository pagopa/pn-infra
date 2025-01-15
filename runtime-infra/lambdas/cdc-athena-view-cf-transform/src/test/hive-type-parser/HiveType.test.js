const { HiveType } = require('../../app/hive-type-parser/HiveType.js');
const { expect } = require('chai');

describe("HiveType tests", function () {
  it("sql method should throw error if type is not supported", async () => {
    
    let type = new HiveType("FAKE_TYPE", null, null, null );
    
    expect( () => type.sql() ).to.throw(Error);
  });

  
})
