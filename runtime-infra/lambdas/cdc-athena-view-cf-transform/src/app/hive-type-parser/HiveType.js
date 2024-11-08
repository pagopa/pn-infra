const ARRAY_DESCEND_PATH_STEP = "[*]";

export class HiveType {

  #category;
  #simpleType;
  #arrayElementType;
  #structChildren;
  #parent;
  #positionIntoParent;

  constructor(category, simpleType, arrayElementType, structChildren, 
                                    parent = null, positionIntoParent = null) {
    this.#category = category;
    this.#simpleType = simpleType;
    this.#arrayElementType = this.#setParentToChildType( arrayElementType, this );
    this.#structChildren = this.#setParentToChildrenTypes( structChildren, this) ;
    this.#parent = parent;
    this.#positionIntoParent = positionIntoParent;

    Object.freeze(this.#structChildren)
    Object.seal(this.#structChildren)
  }

  #setParentToChildType( child, parent ) {
    let newChild;
    if( child ) {
      newChild = child.withParent( parent );
    }
    else {
      newChild = child
    }
    return newChild;
  }

  #setParentToChildrenTypes( children, parent ) {
    let newChildren = {};
    if ( children ) {
      for (const [key, child] of Object.entries(children)) {
        newChildren[ key ] = this.#setParentToChildType( child, parent );
      }
    }
    return newChildren;
  }

  withParent( parent ) {
    return new HiveType( 
        this.#category, 
        this.#simpleType, 
        this.#arrayElementType, 
        this.#structChildren, 
        parent, 
        this.#positionIntoParent
      );
  }

  withPositionIntoParent( positionIntoParent ) {
    return new HiveType( 
        this.#category, 
        this.#simpleType, 
        this.#arrayElementType, 
        this.#structChildren, 
        this.#parent, 
        positionIntoParent
      );
  }

  get path() {
    let result;
    if ( this.#parent ) {
      result = this.#parent.path;
      result.push( this.#positionIntoParent );
    }
    else {
      result = [];
    }
    return result;
  }

  get category() {
    return this.#category;
  }

  get simpleType() {
    return this.#simpleType;
  }

  get arrayElementType() {
    return this.#arrayElementType;
  }

  get structChildren() {
    return this.#structChildren;
  }

  sql() {
    let result;
    if( "SIMPLE" == this.#category ) {
      result = this.#simpleType;
    }
    else if( "ARRAY" == this.#category ) {
      result = "array<" + this.#arrayElementType.sql() + ">"
    }
    else if( "STRUCT" == this.#category ) {
      const oneFieldDeclLambda = (key) => {
        const childTypeStr = this.#structChildren[key].sql()
        return key + ":" + childTypeStr;
      }

      const fieldsString = Object.keys(this.#structChildren).sort()
            .map( oneFieldDeclLambda )
            .join(",")
      result = "struct<" + fieldsString + ">"
    }
    else {
      throw new Error("Category not supported: " + this.#category)
    }
    return result;
  }

}

HiveType.ARRAY_DESCEND_PATH_STEP = ARRAY_DESCEND_PATH_STEP;

