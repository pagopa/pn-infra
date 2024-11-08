import { BaseHiveTypeVisitor } from '../hive-type-parser/BaseHiveTypeVisitor.js';
import { SimplifiedCdcViewGeneratorContext } from './SimplifiedCdcViewGeneratorContext.js'

const DYNAMODB_NULL_SUFFIX = "NULL";

export class CdcViewGeneratorHiveTypeVisitor extends BaseHiveTypeVisitor {
  #simpleTypeTranslator;
  #aliasCustomizer;
  #useDdlOrDqlSyntax;

  
  constructor( useDdlOrDqlSyntax, aliasCustomizer, simpleTypeTranslator = (el)=>el) {
    super();
    this.#useDdlOrDqlSyntax = useDdlOrDqlSyntax;
    this.#simpleTypeTranslator = simpleTypeTranslator;
    this.#aliasCustomizer = aliasCustomizer;
  }

  getViewQuery( hiveType, tableName, indentationStepSize ) {
    let rootContext = this.#newSimplifiedCdcViewGeneratorContextInstance( [], 0 )
    this.visit( hiveType, rootContext )
    return rootContext.getViewQuery( tableName, indentationStepSize )
  }

  getViewColumns( hiveType ) {
    let rootContext = this.#newSimplifiedCdcViewGeneratorContextInstance( [], 0 )
    this.visit( hiveType, rootContext )
    return rootContext.getViewColumns()
  }

  #newSimplifiedCdcViewGeneratorContextInstance( rootPath, depth) {
    return new SimplifiedCdcViewGeneratorContext(
        this.#useDdlOrDqlSyntax, 
        rootPath, depth,
        this.#simpleTypeTranslator,
        this.#aliasCustomizer
      )
  }

  enterNodeVisit( ht, context ) {
    let descend;

    if ( ! context.isContextRootNode( ht ) && ht.category == "ARRAY" ) {
      const childCtx = context.addArray( ht.path )
      this.visit( ht, childCtx )
      descend = false
    }
    else {
      descend = true
    }
    return descend;
  }

  exitNodeVisit( ht, context ) {
    if ( ht.category == "SIMPLE" ) {
      if( this.#acceptSimpleProperty( ht ) ) {
        context.addAlias( ht.path, ht.simpleType )
      }
    }
  }

  #acceptSimpleProperty( ht ) {
    let accept = ht.path.length > 0;
    if ( accept ) {
      const lastPathStep = ht.path[ ht.path.length - 1 ];
      accept = lastPathStep != this.constructor.DYNAMODB_NULL_SUFFIX;
    }
    return accept;
  }

}

CdcViewGeneratorHiveTypeVisitor.DYNAMODB_NULL_SUFFIX = DYNAMODB_NULL_SUFFIX;
