const { HiveTypeParser } = require("../hive-type-parser/HiveTypeParser.js");
const { CdcViewGeneratorHiveTypeVisitor } = require ('./CdcViewGeneratorHiveTypeVisitor.js');

const INDENT = 4;

class CdcViewGenerator {
  #fullTableType;
  #catalogName;
  #databaseName;
  #cdcTableName;
  #cdcViewName;
  #cdcRecordFilter;

  #ddlVisitor;
  #dqlVisitor;
  
  constructor( params ) {
    const hiveTypeParser = new HiveTypeParser();

    const keysTypeString = params["CdcKeysType"];
    console.debug("Verify CdcKeysType param ...");
    hiveTypeParser.parse( keysTypeString );
    console.debug(" ... done!");

    const cdcNewImageTypeString = params["CdcNewImageType"];
    console.debug("Verify CdcNewImageType param ...");
    hiveTypeParser.parse( cdcNewImageTypeString );
    console.debug(" ... done!");

    const fullTableTypeString = this.#buildTableTypeString( keysTypeString, cdcNewImageTypeString);
    console.debug("Parsing table type structure ...");
    this.#fullTableType = hiveTypeParser.parse( fullTableTypeString );
    console.debug(" ... done!");

    console.debug("Validate other parameters ...");
    this.#catalogName = this.#normalizeTrimNotEmpty( params, "CatalogName" );
    this.#databaseName = this.#normalizeTrimNotEmpty( params, "DatabaseName" );
    this.#cdcTableName = this.#normalizeTrimNotEmpty( params, "CdcTableName" );
    this.#cdcViewName = this.#normalizeTrimNotEmpty( params, "CdcViewName" );
    this.#cdcRecordFilter = this.#normalizeTrim( params, "CdcRecordFilter" );
    console.debug(" ... done!");

    
    this.#ddlVisitor = new CdcViewGeneratorHiveTypeVisitor( 
        "DDL", 
        (alias)=> this.customizeAlias( alias) 
      );
    this.#dqlVisitor = new CdcViewGeneratorHiveTypeVisitor( 
        "DQL", 
        (alias)=> this.customizeAlias( alias ),
        (type)=> this.translateSimpleTypeFromDdlToDql( type ),
      );
  }

  #buildTableTypeString( keysType, newImageType ) {
    const tableTypeString = `
        struct<
          awsregion:string,
          eventid:string,
          eventname:string,
          useridentity:string,
          recordformat:string,
          tablename:string,
          p_year:string,
          p_month:string,
          p_day:string,
          p_hour:string,
          dynamodb:struct<
              ApproximateCreationDateTime:bigint,
              SizeBytes:bigint,
              Keys: ${keysType},
              NewImage: ${newImageType}
          >
        >`;
    return tableTypeString;
  }

  #normalizeTrimNotEmpty( params, paramName ) {
    const value = params[ paramName ];
    const trimmedValue = ( value ? value.trim() : value );
    if( trimmedValue.length == 0 ) {
      throw new Error("Parameter " + paramName + " is required ");
    }
    return trimmedValue;
  }

  #normalizeTrim( params, paramName ) {
    const value = params[ paramName ];
    const trimmedValue = ( value ? value.trim() : "" );
    return trimmedValue;
  }

  customizeAlias( originalAlias ) {
    let newAlias;
    if ( originalAlias.startsWith( "dynamodb_NewImage_" ) ) {
      newAlias = originalAlias.substring( "dynamodb_NewImage_".length);
    }
    else if ( originalAlias.startsWith( "dynamodb_Keys_" )) {
      newAlias = "dynamodb_keys_" + originalAlias.substring( "dynamodb_Keys_".length);
    } 
    else if ( originalAlias == "dynamodb_ApproximateCreationDateTime" ) {
      newAlias = "kinesis_dynamodb_ApproximateCreationDateTime"
    }
    else if ( originalAlias == "awsregion" ) {
      newAlias = "stream_awsregion"
    }
    else if ( originalAlias == "eventid" ) {
      newAlias = "stream_eventid"
    }
    else if ( originalAlias == "eventname" ) {
      newAlias = "stream_eventname"
    }
    else if ( originalAlias == "useridentity" ) {
      newAlias = "stream_useridentity"
    }
    else if ( originalAlias == "recordformat" ) {
      newAlias = "stream_recordformat"
    }
    else if ( originalAlias == "tablename" ) {
      newAlias = "stream_tablename"
    }
    else {
      newAlias = originalAlias
    }
    return newAlias;
  }

  translateSimpleTypeFromDdlToDql( ddlType ) {
    let dqlType;
    if ( ddlType == "string" ) {
      dqlType = "VARCHAR";
    }
    else if ( ddlType == "long" ) {
      dqlType = "BIGINT";
    }
    else {
      dqlType = ddlType.toUpperCase();
    }  
    return dqlType
  }

  buildCloudFormationStorageDescriptorColumns() {
    const columns = this.#ddlVisitor.getViewColumns( this.#fullTableType );
    const result = columns.map( el => ({ 
        "Name": el.name, 
        "Type": el.type.replace(/[ "]/g, '') 
      }));
    return result;
  }

  buildPrestoViewData() {
    const fullCdcTableName = `"${this.#databaseName}"."${this.#cdcTableName}"`;
    //const fullCdcViewName = `"${this.#databaseName}"."${this.#cdcViewName}"`;
    
    let query = this.#dqlVisitor.getViewQuery( this.#fullTableType, fullCdcTableName, INDENT );
    if( this.#cdcRecordFilter ) {
      query = query + "\nWHERE\n" 
                    + " ".repeat( INDENT ) + "(" + this.#cdcRecordFilter + ")"
                    ;
    }

    const columns = this.#dqlVisitor.getViewColumns( this.#fullTableType );

    const viewData = {
      originalSql: query,
      catalog: this.#catalogName,
      schema: this.#databaseName,
      columns: columns
    }
    return viewData;
  }

  buildPrestoViewString() {
    const viewData = this.buildPrestoViewData();
    const viewDataJsonString = JSON.stringify( viewData, null, 2 );
    const prestoViewString = "/* Presto View: " + btoa( viewDataJsonString) + " */";
    return prestoViewString;
  }

}

exports.CdcViewGenerator = CdcViewGenerator;
