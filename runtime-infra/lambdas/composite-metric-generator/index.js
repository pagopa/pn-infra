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
            accountId = event.account; // override account ID with accounts to read alarms from

            if(event.account!=process.env.HELPDESK_ACCOUNT_ID && event.account!=process.env.CONFIDENTIAL_INFO_ACCOUNT_ID){
                console.warn('Invalid account ID '+event.account)
                return {
                    success: true
                }
            }
        }
        
        const microserviceName = findMicroserviceByAlarm(event.detail.alarmName, envType, accountId);
        if(!microserviceName){
            console.warn('Alarm doesn\'t match any of microservice alarms list');
            return {
                success: true
            }
        }
        const msAlarms = findAllAlarmsByMicroservice(microserviceName, envType, accountId)
        const alarmsInAlarmState = await getActiveAlarms(msAlarms, event.region, accountId)
        if(alarmsInAlarmState){
            await putMicroserviceMetric(microserviceName+'-ActiveAlarms', alarmsInAlarmState.length, region);
        }
    } else {
        // periodic evaluation
        console.log('Periodic evaluation');
        const microserviceConfigs = findAllMicroservices()
        for(let i=0; i<microserviceConfigs.length; i++){
            for(let j=0; j<microserviceConfigs[i].microservices.length; j++){
                const microserviceName = microserviceConfigs[i].microservices[j]
                const msAlarms = findAllAlarmsByMicroservice(microserviceName, envType, microserviceConfigs[i].accountId)
                const alarmsInAlarmState = await getActiveAlarms(msAlarms, region, microserviceConfigs[i].accountId)
                console.log('Microservice '+microserviceName+' in account '+microserviceConfigs[i].accountId, alarmsInAlarmState)
                if(alarmsInAlarmState){
                    await putMicroserviceMetric(microserviceName+'-ActiveAlarms', alarmsInAlarmState.length, region);
                } 
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