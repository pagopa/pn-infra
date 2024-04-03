function fromCamelCaseToDashCase(str) {
    return str.replace(/([a-z])([A-Z])/g, '$1-$2').toLowerCase();
}

function getSeparatorByResourceType(resourceType) {
    switch(resourceType) {
        case 'alarm':
        case 'log-group': 
        case 'function':            
            return ':';
        default:
            return '/';
    }
}

function getResourceTypeByService(service, resourceType) {
    if(service === 'apigateway') {
        if(resourceType === 'RestApi') {
            return '/restapis';
        }
    }

    return fromCamelCaseToDashCase(resourceType);
}

function getResourceName(physicalResourceId, resourceType) {
    if(resourceType==='AWS::SQS::Queue'){
        return physicalResourceId.split('/').pop();
    }

    return physicalResourceId;
}

function getResourceArnByCloudformationResource(resource, ctx = {}){
    const { ResourceType, PhysicalResourceId } = resource;
    const { Account: accountId } = ctx;

    if(PhysicalResourceId.indexOf('arn:')===0) return PhysicalResourceId;

    const resourceName = getResourceName(PhysicalResourceId, ResourceType);

    const service = ResourceType.split('::')[1].toLowerCase();
    const resourcePart = getResourceTypeByService(service, ResourceType.split('::')[2]);
    const resourceId = resourcePart+getSeparatorByResourceType(resourcePart)+resourceName;
    if(service === 's3') {
        return `arn:aws:${service}:::${resourceId}`;
    } else if(service === 'apigateway') {
        return `arn:aws:${service}:${region}::${resourceId}`;
    } else if(service === 'iam') {
        return `arn:aws:${service}::${accountId}:${resourceId}`;
    } else if(service==='cloudwatch' && resourcePart==='dashboard') {
        return `arn:aws:${service}::${accountId}:${resourceId}`;
    } else if(service==='sqs') {
        return `arn:aws:${service}:${region}:${accountId}:${resourceName}`;
    } else {
        return `arn:aws:${service}:${region}:${accountId}:${resourceId}`;
    }
}

module.exports = {
    getResourceArnByCloudformationResource
}