const { HiveType } = require("./HiveType.js");

class HiveTypeBuilder {

  #category;
  #simpleType;
  #arrayElementType;
  #structChildren;
  

  constructor() {
    this.#category = null;
    this.#simpleType = null;
    this.#arrayElementType = null;
    this.#structChildren = {};
  }

  simpleType( typeString ) {
    this.#category = "SIMPLE";
    this.#simpleType = typeString;
    return this;
  }

  arrayType( elementTypeString ) {
    this.#category = "ARRAY";
    this.#arrayElementType = elementTypeString
                             .withPositionIntoParent( HiveType.ARRAY_DESCEND_PATH_STEP );
    return this;
  }

  addStructField( fieldName, fieldType ) {
    this.#category = "STRUCT";
    this.#structChildren[ fieldName ] = fieldType.withPositionIntoParent( fieldName );
    return this;
  }

  build() {
    let ht = new HiveType( 
        this.#category, 
        this.#simpleType, 
        this.#arrayElementType, 
        { ... this.#structChildren }
      );
    
    return ht;
  }
}

exports.HiveTypeBuilder = HiveTypeBuilder;
