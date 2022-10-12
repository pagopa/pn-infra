import { initOpenSearchClient } from './lib/init.js';
import { extractKinesisData } from './lib/kinesis.js';
import { prepareBulkBody, failedSeqNumbers } from './lib/openSearch.js';

const openSearch = await initOpenSearchClient();

const handler = async (event) => {
  const logs = extractKinesisData(event);
  console.log(`Batch size: ${logs.length} logs`);

  const bulkBody = prepareBulkBody(logs);

  if(bulkBody.length>0){
    const bulkResponse = await openSearch.bulk({ body: bulkBody });

    const seqNumbers = failedSeqNumbers(bulkResponse, bulkBody);

    console.log(`Failed documents: ${seqNumbers.length}`);

    return {
      batchItemFailures: seqNumbers
    }

  } else {
    return {
      batchItemFailures: []
    }
  }
};

export { handler };
