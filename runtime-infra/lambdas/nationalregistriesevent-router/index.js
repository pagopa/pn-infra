import { SQSClient, SendMessageCommand } from "@aws-sdk/client-sqs";
const sqsClient = new SQSClient({ region: process.env.AWS_REGION });

const SQS_DELIVERYPUSH_URI  = process.env.SQS_DELIVERYPUSH_URI
const SQS_PAPERCHANNEL_URI = process.env.SQS_PAPERCHANNEL_URI

async function send(params) {

    let response;

    try {
        const data = await sqsClient.send(new SendMessageCommand(params));
        if (data) {
            console.log("Success, message sent. MessageID:", data.MessageId);
            const bodyMessage = 'Message Send to SQS- Here is MessageId: ' +data.MessageId;
            response = {
                statusCode: 200,
                body: JSON.stringify(bodyMessage),
            };
        }else{
            console.log("Some error occurred !!")
            response = {
                statusCode: 500,
                body: JSON.stringify('Some error occured !!')
            };
        }
        return response;
    }
    catch (err) {
        console.log("Error", err);
        return err;
    }
    
}

function chooseDestinations(bodyMessage){
    let destinations = []; 

    if(bodyMessage.includes("digitalAddress")) {
        destinations.push(SQS_DELIVERYPUSH_URI);
    } 
    if(bodyMessage.includes("physicalAddress")) {
        destinations.push(SQS_PAPERCHANNEL_URI);
    }
    if(!destinations.length){
        destinations.push(SQS_DELIVERYPUSH_URI, SQS_PAPERCHANNEL_URI); 
    }

    console.log(bodyMessage, destinations);

    return destinations;
}

export const handler = async (event, context) => {
    let response;

    await Promise.all(event.Records.map(async (record) => {

        const bodyMessage = record.body;
        const destinations = chooseDestinations(bodyMessage);

        await Promise.all(destinations.map(async (destination) => {
            
            const params = {
                DelaySeconds: 1,
                MessageAttributes: record.MessageAttributes,
                MessageBody: bodyMessage,
                QueueUrl: destination
            };
            
            response = await send(params);            
            return response;
        }));
        
        
    }));

    
};