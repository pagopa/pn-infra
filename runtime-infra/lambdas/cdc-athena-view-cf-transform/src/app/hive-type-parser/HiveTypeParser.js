const { HiveTypeBuilder } = require("./HiveTypeBuilder.js");
const { HiveTypeTokenizer } = require("./HiveTypeTokenizer.js");

class HiveTypeParser {

  constructor() { }

  parse( typeString ) {
    try {
      const tokenizer = new HiveTypeTokenizer( typeString )
      const result = this.#parseType( tokenizer )
      if ( tokenizer.hasNext() ) {
        const unexpectedToken = tokenizer.next();
        throw new Error("end-of-string expected, got " + unexpectedToken );
      }
      return result;
    }
    catch( err ) {
      throw new Error( err + "\n SOURCE STRING: \n " + typeString, { cause: err });
    }
  }

  #parseType( tokenizer ) {
    const typeBuilder = new HiveTypeBuilder();
    const t = tokenizer.next();

    if ( t.type === "FIXEDstruct" ) {
      tokenizer.assertTopTokenTypeAndConsumeToken( "FIXED<")
      while ( ! tokenizer.topTokenTypeIs( "FIXED>" )) {
        tokenizer.assertTopTokenType( "WORD" )
        const fieldName = tokenizer.next().value
        
        tokenizer.assertTopTokenTypeAndConsumeToken( "FIXED:")
        const fieldType = this.#parseType( tokenizer )
        
        typeBuilder.addStructField( fieldName, fieldType )
        if( tokenizer.topTokenTypeIs( "FIXED," )) {
          tokenizer.next()
        }
        else {
          tokenizer.assertTopTokenType( "FIXED>")
        }
      }
      tokenizer.assertTopTokenTypeAndConsumeToken( "FIXED>")
    }
    else if ( t.type === "FIXEDarray" ) {
      tokenizer.assertTopTokenTypeAndConsumeToken( "FIXED<")
      const elementType = this.#parseType( tokenizer )
      typeBuilder.arrayType( elementType )
      tokenizer.assertTopTokenTypeAndConsumeToken( "FIXED>")
    }
    else if( t.type === "WORD") {
      typeBuilder.simpleType( t.value )
    }
    else {
      throw new Error("Expected array,struct or simple type got" + t) 
    }
    return typeBuilder.build()
  }
}

exports.HiveTypeParser = HiveTypeParser;
