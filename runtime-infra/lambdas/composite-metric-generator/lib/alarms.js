const mapping = {
    'pn-user-attributes': [
        'pn-UserAttributes-ErrorFatalLogs-Alarm',
        'pn-pn-UserAttributes-WEB-ApiGwAlarm',
        'pn-pn-AddressBook-WEB-ApiGwAlarm',
        'pn-pn-AddressBookIO-IO-ApiGwAlarm',
        'pn-pn-UserAttributes-WEB-ApiGwLatencyAlarm',
        'pn-pn-AddressBook-WEB-ApiGwLatencyAlarm',
        'pn-pn-AddressBookIO-IO-ApiGwLatencyAlarm',
        'pn-user-attributes-actions-HasOldMessage'
    ],
    'pn-apikey-manager': [

    ],
    'pn-auth-fleet-v2': [

    ],
    'pn-paper-channel': [

    ],
    'pn-external-registries': [

    ],
    'pn-delivery': [

    ],
    'pn-progression-sensor': [

    ],
    'pn-downtime-logs': [

    ],
    'pn-infra': [

    ],
    'pn-mandate': [

    ],
    'pn-kafka-bridge': [

    ],
    'pn-delivery-push': [

    ],
    'pn-radd-fsu': [
        
    ],
    'pn-frontend': [
        
    ],
    'pn-logsaver-be': [

    ],
    'pn-national-registries': [

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