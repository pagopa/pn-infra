const { HiveType } = require("./HiveType.js");

class BaseHiveTypeVisitor {

  constructor() { }

  visit( rootHiveType, context ) {
    const nodes = []
    if( rootHiveType ) {
      nodes.unshift( rootHiveType )
    }
    else {
      throw new Error("rootHiveType parameter is required")
    }
    
    while( nodes.length > 0 ) {
      const ht = nodes.shift();
      const haveToDescend = this.enterNodeVisit( ht, context );
      if ( haveToDescend ) {
        if ( "STRUCT" === ht.category ) {
          for( let fieldName of Object.keys( ht.structChildren ).sort().reverse() ) {
            let fieldType = ht.structChildren[ fieldName ]
            nodes.unshift( fieldType )
          }
        }
        else if ( "ARRAY" === ht.category ) {
          nodes.unshift( ht.arrayElementType )
        }
        else if ( "SIMPLE" !== ht.category ) {
          throw new Error("unsupported HiveType category " + ht.category)
        }
        // do not add child nodes if category is "SIMPLE"

        this.exitNodeVisit( ht, context )
      }
    }
  }

  enterNodeVisit( ht, context ) {
    return true
  }

  exitNodeVisit( ht, context ) {
    
  }

}

exports.BaseHiveTypeVisitor = BaseHiveTypeVisitor;
