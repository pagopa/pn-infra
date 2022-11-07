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
      const bulkResponse = await openSearch.bulk({ body: bulkBody });
      const batchSeqNumbers = failedSeqNumbers(bulkResponse, bulkBody);
      seqNumbers.append(batchSeqNumbers)      
    }

    console.log(`Failed documents: ${seqNumbers.length}`);

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
