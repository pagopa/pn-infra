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
  console.log(`Batch size: ${logs.length} logs`);
  logMemory('before bulkBodyBatches')

  const bulkBodyBatches = prepareBulkBody(logs);

  logMemory('before loop')
  if(bulkBodyBatches.length>0){
    const seqNumbers = []
    for(let i=0; i<bulkBodyBatches.length; i++){
      logMemory('start loop '+i)
      const bulkBody = bulkBodyBatches[i]
      logMemory('start loop A: '+i)
      console.log(`Bulk batch size: ${bulkBody.length}`);
      const bulkResponse = await openSearch.bulk({ body: bulkBody });
      logMemory('start loop B: '+i)
      const batchSeqNumbers = failedSeqNumbers(bulkResponse, bulkBody);
      console.log(`Bulk done with ${batchSeqNumbers.length} errors`);
      logMemory('start loop C: '+i)
      if(batchSeqNumbers.length>0){
        console.log(JSON.stringify(bulkResponse))
      }
      seqNumbers.push(...batchSeqNumbers);
      logMemory('end loop: '+i)
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
    return ret

  } else {
    return {
      batchItemFailures: []
    }
  }
};

export { handler };
