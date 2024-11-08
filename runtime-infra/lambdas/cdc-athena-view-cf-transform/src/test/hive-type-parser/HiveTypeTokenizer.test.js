import { HiveTypeTokenizer } from '../../app/hive-type-parser/HiveTypeTokenizer.js';
import { expect } from 'chai';

describe("HiveTypeTokenizer tests", function () {
  it("should generate one single fixed token", async () => {
    
    let tokenizer = new HiveTypeTokenizer(">");
    let token = tokenizer.next();
    
    expect(tokenizer.hasNext()).to.be.false;
    
    expect( token.position ).to.be.equals( 0 );
    expect( token.value ).to.be.equals( ">" );
    expect( token.isFixed ).to.be.true;
    expect( token.type ).to.be.equals( "FIXED>" );
  });

  it("should generate one single word token", async () => {
    
    let tokenizer = new HiveTypeTokenizer("one_word");
    let token = tokenizer.next();
    
    expect(tokenizer.hasNext()).to.be.false;
    expect( token.position ).to.be.equals( 0 );
    expect( token.value ).to.be.equals( "one_word" );
    expect( token.isFixed ).to.be.false;
    expect( token.type ).to.be.equals( "WORD" );
  });

  it("should trim spaces and newline around tokens", async () => {
    
    let tokenizer = new HiveTypeTokenizer(" < two\nwords >  ");
    let tokenMinor = tokenizer.next();
    let tokenTwo = tokenizer.next();
    let tokenWords = tokenizer.next();
    let tokenMajor = tokenizer.next();
    
    expect(tokenizer.hasNext()).to.be.false;
    
    expect( tokenMinor.position ).to.be.equals( 1 );
    expect( tokenMinor.value ).to.be.equals( "<" );
    expect( tokenMinor.isFixed ).to.be.true;
    expect( tokenMinor.type ).to.be.equals( "FIXED<" );

    expect( tokenTwo.position ).to.be.equals( 3 );
    expect( tokenTwo.value ).to.be.equals( "two" );
    expect( tokenTwo.isFixed ).to.be.false;
    expect( tokenTwo.type ).to.be.equals( "WORD" );

    expect( tokenWords.position ).to.be.equals( 7 );
    expect( tokenWords.value ).to.be.equals( "words" );
    expect( tokenWords.isFixed ).to.be.false;
    expect( tokenWords.type ).to.be.equals( "WORD" );

    expect( tokenMajor.position ).to.be.equals( 13 );
    expect( tokenMajor.value ).to.be.equals( ">");
    expect( tokenMajor.isFixed ).to.be.true;
    expect( tokenMajor.type ).to.be.equals( "FIXED>" );
  });


  it("should recognize long word with keywods inside", async () => {
    
    let tokenizer = new HiveTypeTokenizer(" arrays  array my_array ");
    let word1 = tokenizer.next();
    let keyword = tokenizer.next();
    let word2 = tokenizer.next();

    expect(tokenizer.hasNext()).to.be.false;
    
    expect( word1.position ).to.be.equals( 1 );
    expect( word1.value ).to.be.equals( "arrays" );
    expect( word1.isFixed ).to.be.false;
    expect( word1.type ).to.be.equals( "WORD" );

    expect( keyword.position ).to.be.equals( 9 );
    expect( keyword.value ).to.be.equals( "array" );
    expect( keyword.isFixed ).to.be.true;
    expect( keyword.type ).to.be.equals( "FIXEDarray" );

    expect( word2.position ).to.be.equals( 15 );
    expect( word2.value ).to.be.equals( "my_array" );
    expect( word2.isFixed ).to.be.false;
    expect( word2.type ).to.be.equals( "WORD" );
  });

  it("top method should not consume tokens", async () => {
    
    let tokenizer = new HiveTypeTokenizer(" arrays ");
    let topResult = tokenizer.top();
    expect(tokenizer.hasNext()).to.be.true;

    let nextResult = tokenizer.next();
    expect(tokenizer.hasNext()).to.be.false;
    
    expect( topResult == nextResult ).to.be.true;
  });


  it("correct assertions should pass", async () => {
    
    let tokenizer = new HiveTypeTokenizer(" struct ");
    
    expect( tokenizer.topTokenTypeIs("FIXEDstruct") ).to.be.true
    
    tokenizer.assertTopTokenType("FIXEDstruct")
    tokenizer.assertTopTokenTypeAndConsumeToken("FIXEDstruct")

    expect(tokenizer.hasNext()).to.be.false;
  });

  it("wrong assertions should fail", async () => {
    
    let tokenizer = new HiveTypeTokenizer(" structure_is_not_a_keyword ");
    
    expect( tokenizer.topTokenTypeIs("FIXEDstruct") ).to.be.false
    
    expect( () => tokenizer.assertTopTokenType("FIXEDstruct") ).to.throw(Error)
    expect( () => tokenizer.assertTopTokenTypeAndConsumeToken("FIXEDstruct") ).to.throw(Error)
    
    expect(tokenizer.hasNext()).to.be.false;
  });

})
