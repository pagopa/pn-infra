const coreMapping = {
    'pn-user-attributes': [
        'oncall-pn-user-attributes-ErrorFatalLogs-Alarm',
        'pn-user-attributes-WEB-ApiGwAlarm',
        'pn-address-book-WEB-ApiGwAlarm',
        'pn-address-book-io-IO-ApiGwAlarm',
        'oncall-pn-user-attributes-WEB-ApiGwLatencyAlarm',
        'oncall-pn-address-book-WEB-ApiGwLatencyAlarm',
        'oncall-pn-address-book-io-IO-ApiGwLatencyAlarm',
        'pn-user-attributes-actions-HasOldMessage'
    ],
    'pn-apikey-manager': [
        'pn-apikey-manager-WEB-ApiGwAlarm',
        'pn-apikey-manager-bo-BACKOFFICE-ApiGwAlarm',
        'oncall-pn-apikey-manager-ErrorFatalLogs-Alarm',
        'oncall-pn-apikey-manager-bo-BACKOFFICE-ApiGwLatencyAlarm',
        'oncall-pn-apikey-manager-WEB-ApiGwLatencyAlarm'
    ],
    'pn-auth-fleet-v2': [
        'pn-authFleet-JwtAuthorizerErrorFatalLogsMetricAlarm',
        'pn-authFleet-ApiKey2ErrorFatalLogsMetricAlarm',
        'pn-authFleet-TokenExchangeErrorFatalLogsMetricAlarm',
        'pn-authFleet-IoAuthorizerErrorFatalLogsMetricAlarm',
        'pn-token-exchange-api-ErrorAlarm',
        'oncall-pn-token-exchange-api-LatencyAlarm'
    ],
    'pn-paper-channel': [
        'pn-nationalregistries_to_paperchannel-HasOldMessage',
        'oncall-pn-paper-channel-ErrorFatalLogs-Alarm',
        'pn-nationalregistries_to_paperchannel-DLQ-HasMessage',
        'oncall-pn-paper-channel-bo-BACKOFFICE-ApiGwLatencyAlarm',
        'pn-paper-channel-bo-BACKOFFICE-ApiGwAlarm'
    ],
    'pn-external-registries': [
        'pn-external-registries-B2B-ApiGwAlarm',
        'oncall-pn-external-registries-ErrorFatalLogs-Alarm',
        'pn-external-registries-WEB-ApiGwAlarm',
        'oncall-pn-external-registries-B2B-ApiGwLatencyAlarm',
        'oncall-pn-external-registries-WEB-ApiGwLatencyAlarm'
    ],
    'pn-delivery': [
        'pn-delivery-B2B-ApiGwAlarm',
        'oncall-pn-delivery-ErrorFatalLogs-Alarm',
        'oncall-pn-delivery-IO-ApiGwLatencyAlarm',
        'oncall-pn-delivery-WEB-ApiGwLatencyAlarm',
        'pn-delivery-IO-ApiGwAlarm',
        'oncall-pn-delivery-B2B-ApiGwLatencyAlarm',
        'pn-delivery-WEB-ApiGwAlarm',
        'pn-delivery_insert_trigger_DLQ-HasMessage'
    ],
    'pn-progression-sensor': [
        'pn-slaViolationCheckerLambda-LogInvocationErrors-Alarm',
        'pn-slaViolationCloseSchedulingLambda-LogInvocationErrors-Alarm',
        'pn-activityStepManagerLambda-LogInvocationErrors-Alarm',
        'pn-searchSLAViolationsLambda-LogInvocationErrors-Alarm',
        'pn-progression-sensor-queue-HasOldMessage',
        'pn-progression-sensor-queue-DLQ-HasMessage'
    ],
    'pn-downtime-logs': [
        'pn-downtime-logs-WEB-ApiGwAlarm',
        'oncall-pn-downtime-logs-ErrorFatalLogs-Alarm',
        'oncall-pn-downtime-logs-WEB-ApiGwLatencyAlarm',
        'pn-downtime_logs_internal_events-HasOldMessage',
        'pn-safestore_to_downtime_logs-HasOldMessage',
        'pn-composite_alarms_for_downtime-HasOldMessage',
        'pn-safestore_to_downtime_logs-DLQ-HasMessage',
        'pn-composite_alarms_for_downtime-DLQ-HasMessage'
    ],
    'pn-infra': [
        'LogsBucket-Storage-Limit-Exceeded',
        'pn-logsToOpenSearch-opensearch-ingestion-LogInvocationErrors-Alarm',
        'pn-safestorage-logger-LogInvocationErrors-Alarm',
        'pn-logsTos3-Kinesis-Alarm',
        'pn-cdcTos3-Kinesis-Alarm',
        'pn-ECSOutOfMemory-Alarm',
        'pn-CoreEventBus-DLQ-HasMessage',
        'pn-opensearch-cluster-red',
        'pn-opensearch-writes-blocked',
        'pn-opensearch-low-storage',
        'pn-opensearch-cluster-yellow',
        'pn-core-redis-MemoryUsage',
        'pn-core-redis-CPUUtilization',
        'pn-core-redis-EngineCPUUtilization',
        'pn-core-redis-CurrentConnections'
    ],
    'pn-mandate': [
        'oncall-pn-mandate-ErrorFatalLogs-Alarm',
        'pn-mandate-WEB-ApiGwAlarm',
        'oncall-pn-mandate-WEB-ApiGwLatencyAlarm'
    ],
    'pn-kafka-bridge': [
        'oncall-pn-kafka-bridge-ErrorFatalLogs-Alarm',
        'pn-kafka_bridge_onboarding-HasOldMessage',
        'pn-kafka_bridge_onboarding-DLQ-HasMessage'
    ],
    'pn-delivery-push': [
        'pn-nationalregistries_to_deliverypush-HasOldMessage',
        'pn-nationalregistries_to_deliverypush-DLQ-HasMessage',
        'oncall-pn-delivery-push-ErrorFatalLogs-Alarm',
        'pn-delivery_push_actions_done-HasOldMessage',
        'pn-delivery_push_actions-HasOldMessage',
        'pn-safestore_to_deliverypush-HasOldMessage',
        'pn-delivery_push_inputs-HasOldMessage',
        'pn-safestore_to_deliverypush-DLQ-HasMessage',
        'pn-addressmanager_to_deliverypush-DLQ-HasMessage',
        'pn-addressmanager_to_deliverypush-HasOldMessage'
    ],
    'pn-frontend': [
        'www.${env}notifichedigitali.it-DistributionRequestsAlarm',
        'www.${env}notifichedigitali.it-DistributionErrorsAlarm',
        'login.${env}notifichedigitali.it-DistributionRequestsAlarm',
        'login.${env}notifichedigitali.it-DistributionErrorsAlarm',
        'imprese.${env}notifichedigitali.it-DistributionRequestsAlarm',
        'imprese.${env}notifichedigitali.it-DistributionErrorsAlarm',
        'cittadini.${env}notifichedigitali.it-DistributionErrorsAlarm',
        'cittadini.${env}notifichedigitali.it-DistributionRequestsAlarm',
        'selfcare.${env}notifichedigitali.it-DistributionErrorsAlarm',
        'selfcare.${env}notifichedigitali.it-DistributionRequestsAlarm'
    ],
    'pn-logsaver-be': [
        'pn-logsaver-be-ErrorFatalLogs-Alarm',
        'pn-logsaver-be-FailedInvocation-Alarm'
    ],
    'pn-national-registries': [
        'oncall-pn-national-registries-ErrorFatalLogs-Alarm',
        'oncall-pn-national-registries-PNPG-ApiGwLatencyAlarm',
        'pn-national-registries-PNPG-ApiGwAlarm',
        'pn-national_registry_gateway_outputs-HasOldMessage',
        'pn-national_registry_gateway_outputs-DLQ-HasMessage'
    ],
    'pn-radd-fsu': [
        'oncall-pn-radd-fsu-ErrorFatalLogs-Alarm'
    ],
    'pn-helpdesk-fe': [
        'helpdesk.${env}notifichedigitali.it-DistributionErrorsAlarm',
        'helpdesk.${env}notifichedigitali.it-DistributionRequestsAlarm'
    ],
    'pn-logextractor-be': [
        'oncall-pn-logextractor-be-ErrorFatalLogs-Alarm',
        'oncall-pn-logextractor-be-BACKOFFICE-ApiGwLatencyAlarm',
        'pn-logextractor-be-BACKOFFICE-ApiGwAlarm'
    ]
}

const confidentialInfoMapping = {
    'pn-data-vault': [
        'oncall-pn-data-vault-sep-ErrorFatalLogs-Alarm',
    ],
    'pn-logsaver-be-confidential-info': [
        'pn-logsaver-be-ErrorFatalLogs-Alarm',
        'pn-logsaver-be-FailedInvocation-Alarm'
    ],
    'pn-infra-confidential-info': [
        'pn-cdcTos3-Kinesis-Alarm',
        'pn-logsTos3-Kinesis-Alarm',
        'pn-LambdaAllAlarmSnsPublisher-Alarm'
    ],
    'pn-address-manager': [
        'oncall-pn-address-manager-ErrorFatalLogs-Alarm',
        'pn-AddressManagerBus-DLQ-HasMessage'
    ],
    'pn-safe-storage': [
        'oncall-pn-safe-storage-ErrorFatalLogs-Alarm',
        'pn-new-safestorage-cloudtrail-file-DLQ-HasMessage',
        'pn-ss-staging-bucket-events-queue-HasOldMessage',
        'pn-ss-main-bucket-events-queue-HasOldMessage',
        'pn-ss-gestore-bucket-invocation-errors-queue-HasOldMessage',
        'pn-new-safestorage-cloudtrail-file-HasOldMessage'
    ],
    'pn-external-channel': [
        'oncall-pn-external-channel-ErrorFatalLogs-Alarm'
    ],
    'pn-state-machine-manager': [
        'oncall-pn-state-machine-manager-ErrorFatalLogs-Alarm'
    ],
    'pn-spidhub': [
        'spidhub-${env1}-ExternalALBAlarm',
        'spidhub-${env1}-CPUUtilization',
        'spidhub-${env1}-EngineCPUUtilization',
        'spidhub-${env1}-CurrentConnections',
        'spidhub-${env1}-MemoryUsage',
        'spidhub-${env1}-spid-ecs-cpu-utilization',
        'spidhub-${env1}-spid-ecs-memory-utilization'
    ]
}

function replaceVariables(alarm, replacements = {}){
    let ret = alarm
    for (const [replacementKey, replacementValue] of Object.entries(replacements)) {
        ret = ret.replace('${'+replacementKey+'}', replacementValue)
    }
    return ret;
}

function getMappingByAccountId(accountId = null){
    if(!accountId){
        return coreMapping;
    }

    if(accountId==process.env.CONFIDENTIAL_INFO_ACCOUNT_ID){
        return confidentialInfoMapping;
    }

    return coreMapping
}

function findMicroserviceByAlarm(alarm, envType, accountId = null){
    const mapping = getMappingByAccountId(accountId)
    for (const [microservice, alarms] of Object.entries(mapping)) {
        let replacedAlarm = alarms.find((a) => {
            const replacedAlarm = replaceVariables(a, {
                env: envType,
                env1: envType,
            })

            return replacedAlarm==alarm
        })
        if(replacedAlarm){
            return microservice
        }
    }

    return null
}

function findAllAlarmsByMicroservice(microservice, envType, accountId = null){
    const mapping = getMappingByAccountId(accountId)
    const alarms = mapping[microservice]
    if(!alarms){
        console.warn('Invalid microservice key: '+microservice)
        return  []
    } else {
        const replacedAlarms = alarms.map((a) => {
            if(envType=='prod'){
                return replaceVariables(a, {
                    env: '',
                    env1: envType
                });
            } 
            return replaceVariables(a, {
                env: envType+'.',
                env1: envType
            });
        })

        return replacedAlarms
    }
}

function findAllMicroservices(){
    const coreKeys = Object.keys(coreMapping)
    const confidentialInfoKeys = Object.keys(confidentialInfoMapping)

    const ret = [
        {
            accountId: null,
            microservices: coreKeys
        }
    ]


    if(process.env.CONFIDENTIAL_INFO_ACCOUNT_ID){
        ret.push({
            accountId: process.env.CONFIDENTIAL_INFO_ACCOUNT_ID,
            microservices: confidentialInfoKeys
        })
    }

    return ret;
}

module.exports = {
    findMicroserviceByAlarm,
    findAllAlarmsByMicroservice,
    findAllMicroservices
}