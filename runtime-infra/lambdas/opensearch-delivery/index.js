'use strict';

import { initOpenSearchClient } from './lib/init.js';
import { extractKinesisData } from './lib/kinesis.js';
import { prepareBulkBody, failedSeqNumbers } from './lib/openSearch.js';

const openSearch = await initOpenSearchClient();

const logMemory = (message) => {
  console.log(message, process.memoryUsage())
}

const handler = async (event) => {
  logMemory('start')
  const logs = extractKinesisData(event);
  console.log(`Batch size: ${logs.length}`);
  logMemory('before bulkBodyBatches')

  const bulkBodyBatches = prepareBulkBody(logs);

  logMemory('before loop')
  if(bulkBodyBatches.length>0){
    const seqNumbers = []

    let i = 0
    for (const bulkBodyOrig of bulkBodyBatches){
      logMemory('start loop '+i)
      const bulkBody = bulkBodyOrig.map(a => {return {...a}}) // copy to allow memory reclaim
      console.log(`Bulk batch size: ${bulkBody.length}`);

      const { body: { errors, items } = {} } = await openSearch.bulk({ body: bulkBody });
      logMemory('start loop B: '+i)
      if(errors){
        const batchSeqNumbers = failedSeqNumbers({ body: {errors, items} }, bulkBody);
        if(batchSeqNumbers.length>0){
          console.log(JSON.stringify(items))
        }
        logMemory('start loop C: '+i)
        console.log(`Bulk done with ${batchSeqNumbers.length} errors`);
        seqNumbers.push(...batchSeqNumbers);
      }
      logMemory('end loop: '+i)
      i++
    }

    if(seqNumbers.length>0){
      console.error(`Bulk import has ${seqNumbers.length} failures`);
    } else {
      console.log(`Bulk imported completed`);
    }

    const uniqueSeqNumbers = [...new Set(seqNumbers)]
    const ret = uniqueSeqNumbers.map((s) => {
      return { itemIdentifier: s };
    })
    return {
      batchItemFailures: ret
    } 

  } else {
    return {
      batchItemFailures: []
    }
  }
};

export { handler };
