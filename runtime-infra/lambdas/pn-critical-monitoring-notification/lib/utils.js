function retrieveRequestIdWithoutPCRETRY(requestId) {
  return requestId.split('.PCRETRY_')[0];
}

function retrieveIunFromRequestId(requestId) {
  return requestId.split('IUN_')[1].split('.')[0];
}

function retrieveInfoFromDetails(event) {
  console.log("Retrieving analog mail info from event details", event);
  return {
    courier: event.courier,
    requestId: event.requestId,
    requestIdWithoutPCRETRY: retrieveRequestIdWithoutPCRETRY(event.requestId),
    registeredLetterCode: event.registeredLetterCode,
    iun: retrieveIunFromRequestId(event.requestId),
    timestamp: event.clientRequestTimeStamp
  }
}

module.exports = {
  retrieveInfoFromDetails
};
