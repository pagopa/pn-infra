const { CdcViewColumnSorter } = require('../../app/view-generator/CdcViewColumnSorter.js');
const { expect } = require('chai');

describe("CdcViewColumnSorter tests", function () {

  it("should have key at start and other technical columns at the end", async () => {
    const toBeTested = new CdcViewColumnSorter();

    const actual = toBeTested.sortArray([
      'addresstype',
      'codevalid',
      'created',
      'dynamodb_sizebytes',
      'dynamodb_keys_pk',
      'dynamodb_keys_sk',
      'failedattempts',
      'kinesis_dynamodb_approximatecreationdatetime',
      'lastmodified',
      'pecvalid',
      'p_day',
      'p_hour',
      'p_month',
      'p_year',
      'pk', 'hk',
      'requestid',
      'senderid',
      'sk',
      'stream_awsregion',
      'stream_eventid',
      'stream_eventname',
      'stream_recordformat',
      'stream_tablename',
      'stream_useridentity',
      'ttl',
      'verificationcode'
    ], (el) => el )

    expect( actual ).to.be.deep.equals( [
      'hk',
      'pk',
      'sk',
      'addresstype',
      'codevalid',
      'created',
      'failedattempts',
      'lastmodified',
      'pecvalid',
      'requestid',
      'senderid',
      'ttl',
      'verificationcode',
      'dynamodb_keys_pk',
      'dynamodb_keys_sk',
      'dynamodb_sizebytes',
      'kinesis_dynamodb_approximatecreationdatetime',
      'stream_awsregion',
      'stream_eventid',
      'stream_eventname',
      'stream_recordformat',
      'stream_tablename',
      'stream_useridentity',
      'p_hour', // - Mettere le ore prima dell'anno non è un errore: serve per semplificare il partizionamento a soli anno, mese, giorno dei parquet derivati dai json
      'p_year',
      'p_month',
      'p_day'
    ])
  })

  it("should mantain order of identical key", async () => {
    const toBeTested = new CdcViewColumnSorter();

    const input = [{ name: 'a', data: 1 }, { name: 'a', data: 2 }];
    const actual = toBeTested.sortArray( input, (el) => el.name );
      
    expect( actual ).to.be.deep.equals( input )
  })

})
