const mapping = {
    'pn-user-attributes': [
        'pn-UserAttributes-ErrorFatalLogs-Alarm',
        'pn-UserAttributes-WEB-ApiGwAlarm',
        'pn-AddressBook-WEB-ApiGwAlarm',
        'pn-AddressBookIO-IO-ApiGwAlarm',
        'pn-UserAttributes-WEB-ApiGwLatencyAlarm',
        'pn-AddressBook-WEB-ApiGwLatencyAlarm',
        'pn-AddressBookIO-IO-ApiGwLatencyAlarm',
        'pn-user-attributes-actions-HasOldMessage'
    ],
    'pn-apikey-manager': [
        'pn-ApikeyManager-WEB-ApiGwAlarm',
        'pn-ApikeyManager-bo-BACKOFFICE-ApiGwAlarm',
        'pn-ApikeyManager-ErrorFatalLogs-Alarm',
        'pn-ApikeyManager-bo-BACKOFFICE-ApiGwLatencyAlarm',
        'pn-ApikeyManager-WEB-ApiGwLatencyAlarm'
    ],
    'pn-auth-fleet-v2': [
        'pn-authFleet-JwtAuthorizerErrorFatalLogsMetricAlarm',
        'pn-authFleet-ApiKey2ErrorFatalLogsMetricAlarm',
        'pn-authFleet-TokenExchangeErrorFatalLogsMetricAlarm',
        'pn-authFleet-IoAuthorizerErrorFatalLogsMetricAlarm',
        'pn-token-exchange-api-LatencyAlarm',
        'pn-token-exchange-api-ErrorAlarm'
    ],
    'pn-paper-channel': [
        'pn-paper-channel-ErrorFatalLogs-Alarm'
    ],
    'pn-external-registries': [
        'pn-ExternalRegistry-B2B-ApiGwAlarm',
        'pn-ExternalRegistry-ErrorFatalLogs-Alarm',
        'pn-ExternalRegistry-WEB-ApiGwAlarm',
        'pn-ExternalRegistry-B2B-ApiGwLatencyAlarm',
        'pn-ExternalRegistry-WEB-ApiGwLatencyAlarm'
    ],
    'pn-delivery': [
        'pn-delivery-B2B-ApiGwAlarm',
        'pn-delivery-ErrorFatalLogs-Alarm',
        'pn-delivery-IO-ApiGwLatencyAlarm',
        'pn-delivery-WEB-ApiGwLatencyAlarm',
        'pn-delivery-IO-ApiGwAlarm',
        'pn-delivery-B2B-ApiGwLatencyAlarm',
        'pn-delivery-WEB-ApiGwAlarm',
        'pn-delivery_insert_trigger_DLQ-HasMessage'
    ],
    'pn-progression-sensor': [
        'pn-slaViolationCheckerLambda-LogInvocationErrors-Alarm',
        'pn-slaViolationCloseSchedulingLambda-LogInvocationErrors-Alarm',
        'pn-activityStepManagerLambda-LogInvocationErrors-Alarm',
        'pn-searchSLAViolationsLambda-LogInvocationErrors-Alarm',
        'pn-progression-sensor-queue-HasOldMessage'
    ],
    'pn-downtime-logs': [
        'pn-downtime-logs-WEB-ApiGwAlarm',
        'pn-downtime-logs-ErrorFatalLogs-Alarm',
        'pn-downtime-logs-WEB-ApiGwLatencyAlarm',
        'pn-downtime_logs_internal_events-HasOldMessage',
        'pn-safestore_to_downtime_logs-HasOldMessage',
        'pn-composite_alarms_for_downtime-HasOldMessage',
        'pn-safestore_to_downtime_logs-DLQ-HasMessage',
        'pn-composite_alarms_for_downtime-DLQ-HasMessage'
    ],
    'pn-infra': [
        'LogsBucket-Storage-Limit-Exceeded',
        'pn-logsToOpenSearch-opensearch-delivery-LogInvocationErrors-Alarm',
        'pn-logsTos3-Kinesis-Alarm',
        'pn-cdcTos3-Kinesis-Alarm',
        'pn-ECSOutOfMemory-Alarm',
        'pn-CoreEventBus-DLQ-HasMessage'
    ],
    'pn-mandate': [
        'pn-mandate-ErrorFatalLogs-Alarm',
        'pn-mandate-WEB-ApiGwAlarm',
        'pn-mandate-WEB-ApiGwLatencyAlarm'
    ],
    'pn-kafka-bridge': [
        'pn-kafka-bridge-ErrorFatalLogs-Alarm',
        'pn-kafka_bridge_onboarding-HasOldMessage',
        'pn-kafka_bridge_onboarding-DLQ-HasMessage'
    ],
    'pn-delivery-push': [
        'pn-nationalregistries_to_deliverypush-HasOldMessage',
        'pn-nationalregistries_to_deliverypush-DLQ-HasMessage',
        'pn-delivery-push-ErrorFatalLogs-Alarm',
        'pn-delivery_push_actions_done-HasOldMessage',
        'pn-delivery_push_actions-HasOldMessage',
        'pn-safestore_to_deliverypush-HasOldMessage',
        'pn-delivery_push_inputs-HasOldMessage',
        'pn-safestore_to_deliverypush-DLQ-HasMessage'
    ],
    'pn-frontend': [
        'www.${env}.pn.pagopa.it-DistributionRequestsAlarm',
        'www.${env}.pn.pagopa.it-DistributionErrorsAlarm',
        'portale-login.${env}.pn.pagopa.it-DistributionRequestsAlarm',
        'portale-login.${env}.pn.pagopa.it-DistributionErrorsAlarm',
        'portale-pg.${env}.pn.pagopa.it-DistributionRequestsAlarm',
        'portale-pg.${env}.pn.pagopa.it-DistributionErrorsAlarm',
        'portale.${env}.pn.pagopa.it-DistributionErrorsAlarm',
        'portale.${env}.pn.pagopa.it-DistributionRequestsAlarm'
    ],
    'pn-logsaver-be': [
        'pn-logsaver-be-ErrorFatalLogs-Alarm',
        'pn-logsaver-be-FailedInvocation-Alarm'
    ],
    'pn-national-registries': [
        'pn-NationalRegistry-ErrorFatalLogs-Alarm'
    ],
    'pn-radd-fsu': [
        'pn-radd-fsu-ErrorFatalLogs-Alarm'
    ]
}

function findMicroserviceByAlarm(alarm){

}

function findAllAlarmsByMicroservice(microservice){

}

module.exports = {
    findMicroserviceByAlarm,
    findAllAlarmsByMicroservice
}