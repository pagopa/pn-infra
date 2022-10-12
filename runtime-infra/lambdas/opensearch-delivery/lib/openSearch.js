function failedSeqNumbers(bulkResponse, bulkBody) {
  const seqNumbers = [];

  if (bulkResponse.body.errors) {
    const items = bulkResponse.body.items;

    items.forEach((action, i) => {
      // In our case it will always be "index"
      const operationKey = Object.keys(action)[0];
      
      if (action[operationKey].error) {
        const offset = (i * 2) + 1;
        seqNumbers.push(bulkBody[offset].kinesisSeqNumber);
      }
    });
  }

  return seqNumbers;
}

function prepareBulkBody(logs) {
  return logs.flatMap((doc) => [{ index: { _index: process.env.INDEX_NAME }}, doc]);
}

export { prepareBulkBody, failedSeqNumbers };
