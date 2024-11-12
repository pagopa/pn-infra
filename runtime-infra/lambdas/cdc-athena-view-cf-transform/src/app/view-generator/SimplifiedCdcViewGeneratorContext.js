const { HiveType } = require('../hive-type-parser/HiveType.js');

const DYNAMODB_SUFFIXES = ["S", "N", "BOOL", "L", "M"];
const TABLE_ALIAS = "t"

class SimplifiedCdcViewGeneratorContext {
  #useDdlOrDqlSyntax;
  #arrayKeyword;
  #rowKeyword;
  #nameTypeSep;
  #openComplexType;
  #closeComplexType;

  #rootPath;
  #depth;
  #childArrays;
  #fieldAliases;
  #fieldTypes;
  #reverseAliases;

  #simpleTypeTranslator;
  #aliasCustomize;

  constructor( useDdlOrDqlSyntax, rootPath, depth, simpleTypeTranslator, aliasCustomize ) {
    this.#useDdlOrDqlSyntax = useDdlOrDqlSyntax;
    this.#initializeKeywords( useDdlOrDqlSyntax );
    this.#rootPath = rootPath;
    this.#depth = depth;
    this.#childArrays = {}
    this.#fieldAliases = {}
    this.#fieldTypes = {}
    this.#reverseAliases = {}
  
    this.#simpleTypeTranslator = simpleTypeTranslator;
    this.#aliasCustomize = aliasCustomize;
  }

  #newChildContext( rootPath, depth ) {
    return new SimplifiedCdcViewGeneratorContext( 
        this.#useDdlOrDqlSyntax, 
        rootPath, depth,
        this.#simpleTypeTranslator,
        this.#aliasCustomize
      );
  }

  #initializeKeywords( useDdlOrDqlSyntax ) {
    if ( "DDL" == useDdlOrDqlSyntax ) {
      this.#arrayKeyword = "array";
      this.#rowKeyword = "struct";
      this.#nameTypeSep = ":";
      this.#openComplexType = "<";
      this.#closeComplexType = ">";
    }
    else if ( "DQL" == useDdlOrDqlSyntax ) {
      this.#arrayKeyword = "array";
      this.#rowKeyword = "row";
      this.#nameTypeSep = " ";
      this.#openComplexType = "(";
      this.#closeComplexType = ")";
    }
    else {
      throw new Error(" unsupported value for " + useDdlOrDqlSyntax )
    }
  }

  isContextRootNode( ht ) {
    return JSON.stringify( ht.path ) == JSON.stringify( this.#rootPath )
  }

  addAlias( path, type) {
    const field = this.#joinPath( path );
    const alias = this.#buildAlias( path );
    this.#fieldTypes[ field ] = type;
    this.#fieldAliases[ field ] = alias;
    
    if ( ! this.#reverseAliases[ alias ] ) {
      this.#reverseAliases[ alias ] = []
    }
    this.#reverseAliases[ alias ].push( field )
  }

  addArray( path ) {
    const alias = this.#buildAlias( path );
    const arrayCtx = this.#newChildContext( path, this.#depth + 1 );
    this.#childArrays[ alias ] = arrayCtx;
    return arrayCtx  
  }

  
  #joinPath( path ) {
    const contextualPath = [ ... path].splice( this.#rootPath.length, path.length );
    const resultSteps = contextualPath
                      .filter( el => el != HiveType.ARRAY_DESCEND_PATH_STEP )
                      .map( el => `"${el}"` )
                      ;
    const result = resultSteps.join(".");
    return result
  }
  
  #buildAlias( path ) {
    const contextualPath = [ ... path].splice( this.#rootPath.length, path.length );
    const resultSteps = contextualPath
                      .filter( el => ! this.constructor.DYNAMODB_SUFFIXES.includes( el ) )
                      .filter( el => el != HiveType.ARRAY_DESCEND_PATH_STEP )
                      ;
    const alias = resultSteps.join("_");
    const customizedAlias = this.#aliasCustomize( alias );
    return customizedAlias;
  }

  getViewQuery( tableName, indentationStepSize ) {
    const indentStep = " ".repeat( indentationStepSize );
    const selectListIndent = indentStep.repeat( 2 );

    const propertiesSelectList = this.#buildSimplePropertySelectList( selectListIndent )
    const arraySelectList = this.#buildTransformSelectList( selectListIndent, indentationStepSize )
    const bothSelectListAreNotEmpty = 
                propertiesSelectList && propertiesSelectList.trim().length > 0 
              &&
                arraySelectList && arraySelectList.trim().length > 0
            ;

    // Query definition with CTE used for simple where condition writing
    const query = "WITH simplified_data AS (\n" 
                + indentStep + "SELECT\n"
                + propertiesSelectList
                + ( bothSelectListAreNotEmpty ? ",\n" : "" )
                + arraySelectList + "\n"
                // End CTE and write query.
                // The caller can add where condition using aliases instead of value expression.
                + indentStep + "FROM\n"
                + indentStep + indentStep + tableName + " " + this.constructor.TABLE_ALIAS + "\n"
                + ")\n" 
                + "SELECT\n" 
                + indentStep + "*\n" 
                + "FROM\n" 
                + indentStep + "simplified_data"
                ;
    return query;
  }

  getViewColumns() {
    let result = []

    for ( let alias of Object.keys(this.#reverseAliases).sort()) {
      const fields = this.#reverseAliases[ alias ];
      const type = this.#generateOneNonArrayType( fields );
      result.push( { name: alias, type: type} );
    }

    for ( let alias of Object.keys(this.#childArrays).sort()) {
      const childCtx = this.#childArrays[ alias ]
      const innerRowType = childCtx.#buildOnlySignaturesListForArrayCast( "", 0 )
      const innerRowTypeOnOneLine = innerRowType.replace(/[ \n]+/g, " ");
      // - type = 'array(' innerRowTypeOnOneLine ')'
      const type = `${this.#arrayKeyword}${this.#openComplexType}${innerRowTypeOnOneLine}` 
                 + `${this.#closeComplexType}`;
      result.push( { name: alias, type: type} );
    }

    return result;
  }

  #buildSimplePropertySelectList( baseIndent ) {
    const result = Object.keys( this.#reverseAliases )
          .sort()
          .map( alias => {
            const fields = this.#reverseAliases[ alias ];
            const selectListElement = baseIndent 
                                    + this.#generateOneNonArrayValue( fields )
                                    + " AS " + this.#wrapAlias( alias )
                                    ;
            return selectListElement;
          })
          .join(",\n");
    return result;
  }

  #buildTransformSelectList( baseIndent, indentationStepSize ) {
    const transformBodyIndent = baseIndent + " ".repeat( indentationStepSize );

    const result = Object.keys( this.#childArrays )
          .sort()
          .map( alias => {
            const childCtx = this.#childArrays[ alias ];
            const arrayField = this.#joinPath( childCtx.#rootPath );
            const arrayElementName = "elem" + this.#depth;

            const transformBody = childCtx.#buildSelectListForArray( 
                                 arrayElementName, transformBodyIndent, indentationStepSize );
            
            const transformFunctionCall = this.#writeTransformFunction( 
                                    baseIndent, arrayField, arrayElementName, transformBody );
            
            const selectListElement = transformFunctionCall + " AS " + this.#wrapAlias( alias );
            return selectListElement;
          })
          .join(",\n");
    return result;
  }
  
  #buildSelectListForArray( arrayElemName, baseIndent, indentStepSize ) {
    const innerIndent = baseIndent + " ".repeat( indentStepSize );
    const values = this.#buildOnlyValuesListForArrayCast( arrayElemName, innerIndent, indentStepSize );
    const signatures = this.#buildOnlySignaturesListForArrayCast( baseIndent, indentStepSize );
    const result = `${baseIndent}cast(${this.#rowKeyword}${this.#openComplexType}\n`
                 + `${values}\n`
                 + `${baseIndent}${this.#closeComplexType} AS ${signatures})`;
    return result;
  }

  #buildOnlyValuesListForArrayCast( arrayElementName, baseIndent, indentationStepSize ) {
    const simpleValues = Object.keys( this.#reverseAliases )
          .sort()
          .map( (alias) => {
            const fields = this.#reverseAliases[ alias ]
                         .map( (f) => `${arrayElementName}.${f}`);
            const value = this.#generateOneNonArrayValue( fields );
            return baseIndent + value
          })
          .join(",\n");
    
    const transformValues = Object.keys( this.#childArrays )
          .sort()
          .map( (alias) => {
            const childCtx = this.#childArrays[ alias ];
            const arrayField = this.#joinPath( childCtx.#rootPath );
            const innerArrayElementName = "elem" + this.#depth;
            const innerIndent = baseIndent + " ".repeat( indentationStepSize );
            const fullArrayField = arrayElementName + "." + arrayField;

            const innerRowCast = childCtx.#buildSelectListForArray( 
                                      innerArrayElementName, innerIndent, indentationStepSize );

            const transformValue = this.#writeTransformFunction( 
                              baseIndent, fullArrayField, innerArrayElementName, innerRowCast );
            return transformValue;
          })
          .join(",\n");
    
    const result = this.#concatNotEmpty( simpleValues, transformValues, ",\n" );
    return result;
  }

  #buildOnlySignaturesListForArrayCast( baseIndent, indentationStepSize ) {
    const listIndent = baseIndent + " ".repeat( indentationStepSize );

    const simpleSignatures = Object.keys( this.#reverseAliases )
          .sort()
          .map( (alias) => {
            const fields = this.#reverseAliases[ alias ];
            const simpleSignature = listIndent 
                                  + this.#wrapAlias( alias ) 
                                  + this.#nameTypeSep 
                                  + this.#generateOneNonArrayType( fields )
                                  ;
            return simpleSignature;
          })
          .join(",\n");

    const transformSignatures = Object.keys( this.#childArrays )
          .sort()
          .map( (alias) => {
            const childCtx = this.#childArrays[ alias ];
            const innerRowType = childCtx.#buildOnlySignaturesListForArrayCast("", 0 );
            const innerRowTypeOnOneLine = innerRowType.replace(/[ \n]+/g, " ");
            // type = 'array(' innerRowTypeOnOneLine ')'
            const type = `${this.#arrayKeyword}${this.#openComplexType}${innerRowTypeOnOneLine}${this.#closeComplexType}`;
            // transformSignature = fieldName:type
            const transformSignature = `${listIndent}${this.#wrapAlias( alias )}${this.#nameTypeSep}${type}`;
            return transformSignature;
          })
          .join(",\n");
    
    const allSignatures = this.#concatNotEmpty( simpleSignatures, transformSignatures, ",\n" );
    // result = 'row(' allSignatures ')'
    const result = `${this.#rowKeyword}${this.#openComplexType}\n`
                 + allSignatures + "\n"
                 + baseIndent + this.#closeComplexType
                 ;
    return result;  
  }

  #writeTransformFunction(baseIndent, arrayField, arrayElementName, transformBody ) {
    const result = baseIndent + "transform( " + arrayField + ", (" + arrayElementName + ") -> \n"
                 + transformBody + "\n"
                 + baseIndent + ")"
                 ;
    return result;
  }
                
  #generateOneNonArrayValue( fields ) {
    const result = ( fields.length == 1 )
                 ? fields[ 0 ]
                 : `coalesce(${ fields.join(",") })`
                 ;
    return result;
  }
                
  #generateOneNonArrayType( fields ) {
    const type = ( fields.length == 1 )
                 ? this.#fieldTypes[ fields[ 0 ] ]
                 : "string"
                 ;
    const result = this.#simpleTypeTranslator( type );
    return result;
  }
  
  #wrapAlias( alias ) {
    return `"${alias}"`;
  }

  #concatNotEmpty( str1, str2, sep ) {
    const bothStringAreNotEmpty = (str1 && str1.trim().length > 0) 
                               && (str2 && str2.trim().length > 0)
                                ;
    const result = str1 + ( bothStringAreNotEmpty ? sep : "" ) + str2;
    return result;
  }

  /* istanbul ignore next */
  dump() {
    const data = {
      rootPath : this.#rootPath,
      depth : this.#depth,
      childArrays : this.#childArrays,
      fieldAliases : this.#fieldAliases,
      fieldTypes : this.#fieldTypes,
      reverseAliases : this.#reverseAliases
    };
    return JSON.stringify( data, null, 2 );
  }

}

SimplifiedCdcViewGeneratorContext.DYNAMODB_SUFFIXES = DYNAMODB_SUFFIXES;
SimplifiedCdcViewGeneratorContext.TABLE_ALIAS = TABLE_ALIAS;

exports.SimplifiedCdcViewGeneratorContext = SimplifiedCdcViewGeneratorContext;
