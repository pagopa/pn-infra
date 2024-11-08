import { HiveTypeToken } from "./HiveTypeToken.js"

export class HiveTypeTokenizer {
  #hiveTypeString;
  #tokens;
  #isInWord;
  #currentWordStartPosition;
  
  constructor( hiveTypeString ) {
    this.#hiveTypeString = hiveTypeString;
    this.#tokens = [];
    
    this.#isInWord = false;
    this.#currentWordStartPosition = null;

    let position = 0;
    while ( position < this.#hiveTypeString.length ) {
      let currentChar = this.#hiveTypeString.charAt( position );
      if ( currentChar.trim().length == 0 ) {
        this.#addCurrentWord( position );
      }
      else if ( HiveTypeToken.PUNCTUATION.includes( currentChar) ) {
        this.#addCurrentWord( position );
        this.#tokens.push( new HiveTypeToken( currentChar, position ));
      }
      else {
        // - Enter in a word token if not already inside a word token
        if ( ! this.#isInWord ) {
          this.#isInWord = true;
          this.#currentWordStartPosition = position;
        }
      }
      position = position + 1;
    }
    this.#addCurrentWord( position );
  }

  toString() {
    return `Tokenizer[\n    ${this.#tokens.join(',\n    ')}\n]`
  }

  #addCurrentWord( position ) {
    if ( this.#isInWord ) {
      let tokenValue = this.#hiveTypeString.substring( this.#currentWordStartPosition, position );
      this.#tokens.push( new HiveTypeToken( tokenValue, this.#currentWordStartPosition ));
      this.#isInWord = false;
      this.#currentWordStartPosition = null;
    }
  }


  hasNext() {
    return this.#tokens.length > 0
  }

  next() {
    let t = this.#tokens.shift();
    return t;
  }

  top() {
    if( this.hasNext() ) {
      return this.#tokens[0];
    }
    else {
      return null
    }
  }
  
  topTokenTypeIs( type ) {
    return this.hasNext() && type == this.top().type
  }

  assertTopTokenType( type ) {
    if ( ! this.topTokenTypeIs( type )) {
      let msg;
      if ( this.hasNext() ) {
        msg = `Expected token of type ${type} but no token remains`
      }
      else {
        msg = `Top token type is ${this.top().type} but ${type} was expected`
      }
      throw new Error( msg )  
    }
  }
  
  assertTopTokenTypeAndConsumeToken( type ) {
    try {
      this.assertTopTokenType( type )
    }
    finally {
      this.next()
    }
    
  }
  
}

