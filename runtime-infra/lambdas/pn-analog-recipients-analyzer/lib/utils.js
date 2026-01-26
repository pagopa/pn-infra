function retrieveRequestIdWithoutPCRETRY(requestId) {
    return requestId.split('.PCRETRY_')[0];
}

function trasformPrepareToSendAnalogTimelineKey(requestId) {
    return `SEND_ANALOG_DOMICILE.IUN_${requestId.split('IUN_')[1]}`;
}

function retrieveIunFromRequestId(requestId) {
  return requestId.split('IUN_')[1].split('.')[0]; 
}

function prepareMessageToSns(csvLine) {
    const [requestId, recipientZip, expectedRecipientId, courier, registeredLetterCode, productType] = csvLine.split(', ').map(item => item.trim());
    return `Alert: Mismatch detected
    RequestId: ${requestId}
    Courier: ${courier}
    Registered Letter Code: ${registeredLetterCode}
    Product Type: ${productType}
    Expected Recipient ID: ${expectedRecipientId}
    Actual Recipient ZIP: ${recipientZip}`;
}

function retrieveInfoFromDetails(event){
  console.log("Retrieving analog mail info from event details", event);
  return {
    courier: event.courier,
    requestId: retrieveRequestIdWithoutPCRETRY(event.requestId),
    registeredLetterCode: event.registeredLetterCode
  }
}

module.exports = {
  retrieveRequestIdWithoutPCRETRY,
  trasformPrepareToSendAnalogTimelineKey,
  retrieveIunFromRequestId,
  prepareMessageToSns,
  retrieveInfoFromDetails
};
