const { findMicroserviceByAlarm, findAllAlarmsByMicroservice, findAllMicroservices} = require('./lib/alarms')
const { getActiveAlarms, putMicroserviceMetric } = require('./lib/cloudwatchClient')

const handler = async (event) => {
    console.info("New event received ", event);

    const region = process.env.REGION
    const accountId = process.env.ACCOUNT_ID
    const envType = process.env.ENVIRONMENT_TYPE;

    // find alarm
    if(event.source=='aws.cloudwatch'){
        if(event.account!=accountId){
            console.warn('Account ID mismatch', {
                source: event.account,
                current: accountId
            })

            return {
                success: true
            }
        }
        const microserviceName = findMicroserviceByAlarm(event.detail.alarmName, envType);
        if(!microserviceName){
            console.warn('Alarm doesn\'t match any of microservice alarms list');
            return {
                success: true
            }
        }
        const msAlarms = findAllAlarmsByMicroservice(microserviceName, envType)
        const alarmsInAlarmState = await getActiveAlarms(msAlarms, event.region)
        if(alarmsInAlarmState){
            await putMicroserviceMetric(microserviceName+'-ActiveAlarms', alarmsInAlarmState.length, region);
        }
    } else {
        // periodic evaluation
        console.log('Periodic evaluation');
        const microservices = findAllMicroservices()
        for(let i=0; i<microservices.length; i++){
            const microserviceName = microservices[i]
            const msAlarms = findAllAlarmsByMicroservice(microserviceName, envType)
            const alarmsInAlarmState = await getActiveAlarms(msAlarms, region)
            console.log('Microservice '+microserviceName, alarmsInAlarmState)
            if(alarmsInAlarmState){
                await putMicroserviceMetric(microserviceName+'-ActiveAlarms', alarmsInAlarmState.length, region);
            } 
        }
    }
    return {
        success: true
    }
};

module.exports = {
    handler
}