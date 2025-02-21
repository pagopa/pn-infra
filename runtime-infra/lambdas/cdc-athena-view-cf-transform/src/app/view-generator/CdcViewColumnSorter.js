
class CdcViewColumnSorter {


  sortArray( columnsArr, nameExtractorFunction ) {

    let result = [ ... columnsArr ];
    result.sort( (a, b) => this.#compareNames( 
        nameExtractorFunction(a), 
        nameExtractorFunction(b)
      ));
    return result;
  }

  // La prima colonna sarà sempre pk (o hk)
  // La seconda colonna sarà sempre sk (o rk)
  // seguono tutte le 
  #compareNames( a, b ) {
    let result;

    if( a === b ) {
      result = 0;
    }
    else {
      const categoryA = this.#findCategory( a );
      const categoryB = this.#findCategory( b );
    
      // - Se i due nomi appartengono alla stessa categoria ...
      if( categoryA === categoryB ) {
        // ... allora si segue l'ordine alfabetico.
        result = ( a > b ? 1 : -1 );
      }
      else {
        // - Se i due nomi appartengono a categorie differenti è la categoria che decide l'ordine
        result = ( categoryA > categoryB ? 1 : -1 );
      }
    }
    
    return result;
  }

  #findCategory( name ) {
    let result = COLUMNS_CATEGORY_ORDER.indexOf(null);

    for( let idx = 0; idx < COLUMNS_CATEGORY_ORDER.length; idx++ ) {
      const regExp = COLUMNS_CATEGORY_ORDER[ idx ];

      if( regExp !== null && name.match( regExp )) {
        result = idx;
        break;
      }
    }

    return result;
  }
}

const COLUMNS_CATEGORY_ORDER = [
    '^(pk|hk)$',
    '^(sk|rk)$',
    null,
    '^dynamodb_.*',
    '^kinesis_dynamodb_.*',
    '^stream_.*',
    '^p_hour$',
    '^p_year$',
    '^p_month$',
    '^p_day$'
  ];
  
  exports.CdcViewColumnSorter = CdcViewColumnSorter;
