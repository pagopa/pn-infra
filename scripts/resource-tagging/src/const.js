const IGNORED_RESOURCE_TYPES = [
    'AWS::CloudWatch::Dashboard', 
    'AWS::Logs::MetricFilter', 
    'AWS::Logs::SubscriptionFilter',
    'AWS::Lambda::Permission',
    'AWS::ApiGateway::Authorizer',
    'AWS::ApiGateway::BasePathMapping',
    'AWS::ApiGateway::Method',
    'AWS::ApiGateway::Resource',
    'AWS::ApiGateway::Deployment',
    'AWS::ApiGateway::Stage',
    'AWS::ApiGateway::Resource',
    'AWS::ApiGateway::GatewayResponse',
    'AWS::Lambda::EventSourceMapping',
    'AWS::ApiGateway::Model',
    'AWS::ApiGateway::RequestValidator',
    'AWS::ApiGateway::UsagePlan'
];

const WAIT_TIME_BETWEEN_TAGS_MS = 5000

const ALL_MICROSERVICES = {
    core: [
        'pn-delivery',
        'pn-delivery-push',
        'pn-logextractor-be',
        'pn-downtime-logs',
        'pn-external-channels',
        'pn-external-registries',
        'pn-logsaver-be',
        'pn-mandate',
        'pn-user-attributes',
        'pn-apikey-manager',
        'pn-progression-sensor',
        'pn-auth-fleet',
        'pn-paper-channel',
        'pn-national-registries',
        'pn-service-desk',
        'pn-f24',
        'pn-radd-alt'
    ],
    confinfo: [
        'pn-data-vault',
        'pn-cn',
        'pn-ss',
        'pn-ec',
        'pn-address-manager',
        'pn-statemachinemanager',
        'pn-logsaver-be'
    ]
}

RESOURCE_TAGGED_PER_API_CALL=20

module.exports = {
    IGNORED_RESOURCE_TYPES,
    WAIT_TIME_BETWEEN_TAGS_MS,
    ALL_MICROSERVICES,
    RESOURCE_TAGGED_PER_API_CALL
};