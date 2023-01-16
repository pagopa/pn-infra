import { initOpenSearchClient } from './lib/init.js';
import { extractKinesisData } from './lib/kinesis.js';
import { prepareBulkBody, failedSeqNumbers } from './lib/openSearch.js';

const openSearch = await initOpenSearchClient();

const handler = async (event) => {
  const logs = extractKinesisData(event);
  console.log(`Batch size: ${logs.length} logs`);

  const bulkBodyBatches = prepareBulkBody(logs);

  if(bulkBodyBatches.length>0){
    const seqNumbers = []
    for(let i=0; i<bulkBodyBatches.length; i++){
      const bulkBody = bulkBodyBatches[i]
      console.log(`Bulk batch size: ${bulkBody.length}`);
      const bulkResponse = await openSearch.bulk({ body: bulkBody });
      const batchSeqNumbers = failedSeqNumbers(bulkResponse, bulkBody);
      console.log(`Bulk done with ${batchSeqNumbers.length} errors`);
      if(batchSeqNumbers.length>0){
        console.log(JSON.stringify(bulkResponse))
      }
      seqNumbers.push(...batchSeqNumbers);
    }

    if(seqNumbers.length>0){
      console.error(`Bulk import has ${seqNumbers.length} failures`);
    } else {
      console.log(`Bulk imported completed`);
    }

    return {
      batchItemFailures:  [...new Set(seqNumbers)]
    }

  } else {
    return {
      batchItemFailures: []
    }
  }
};

export { handler };
