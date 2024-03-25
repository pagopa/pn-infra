const { fromIni } = require("@aws-sdk/credential-provider-ini");
const { CloudFormationClient, ListStackResourcesCommand } = require("@aws-sdk/client-cloudformation");
const { ResourceGroupsTaggingAPIClient, TagResourcesCommand } = require("@aws-sdk/client-resource-groups-tagging-api");

const env = 'dev'
const profile = 'sso_pn-core-'+env
const microservice = 'pn-platform-usage-estimates';
const region = 'eu-south-1';
const accountId = '830192246553';

const configObj = {
    region: region,
    credentials: fromIni({ 
        profile: profile,
    })
};

const cloudFormationClient = new CloudFormationClient(configObj);
const taggingClient = new ResourceGroupsTaggingAPIClient(configObj);

async function getResources(stackName) {
    const resources = [];
    
    let nextToken = null;
    do {
        const response = await cloudFormationClient.send(new ListStackResourcesCommand({ StackName: stackName, NextToken: nextToken }));
        resources.push(...response.StackResourceSummaries);
        nextToken = response.NextToken;
    } while (nextToken);

    const nestedStacks = resources.filter(r => r.ResourceType === 'AWS::CloudFormation::Stack');

    if(nestedStacks.length > 0) {
        for (const nestedStack of nestedStacks) {
            const nestedStackResources = await getResources(nestedStack.PhysicalResourceId);
            resources.push(...nestedStackResources);
        }
    }

    return resources.filter(r => r.ResourceType !== 'AWS::CloudFormation::Stack');
}

function fromCamelCaseToDashCase(str) {
    return str.replace(/([a-z])([A-Z])/g, '$1-$2').toLowerCase();
}

function getSeparatorByResourceType(resourceType) {
    switch(resourceType) {
        case 'alarm':
        case 'log-group':            
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

function getResourceArnByCloudformationResource(resource){
    const { ResourceType, PhysicalResourceId } = resource;

    if(PhysicalResourceId.indexOf('arn:')===0) return PhysicalResourceId;

    const service = ResourceType.split('::')[1].toLowerCase();
    const resourcePart = getResourceTypeByService(service, ResourceType.split('::')[2]);
    const resourceId = resourcePart+getSeparatorByResourceType(resourcePart)+PhysicalResourceId;
    if(service === 's3') {
        return `arn:aws:${service}:::${resourceId}`;
    } else if(service === 'apigateway') {
        return `arn:aws:${service}:${region}::${resourceId}`;
    } else if(service === 'iam') {
        return `arn:aws:${service}::${accountId}:${resourceId}`;
    } else if(service==='cloudwatch' && resourcePart==='dashboard') {
        return `arn:aws:${service}::${accountId}:${resourceId}`;
    } else {
        return `arn:aws:${service}:${region}:${accountId}:${resourceId}`;
    }
}

async function tagResources(resources, tags) {
    const resourceARNs = resources.filter((r) => {
        return ['AWS::CloudWatch::Dashboard', 'AWS::Logs::MetricFilter', 'AWS::Logs::SubscriptionFilter'].indexOf(r.ResourceType) === -1;
    }).map(r => getResourceArnByCloudformationResource(r));

    console.log('Tagging resources:', resourceARNs, 'with tags:', tags)
    if(resourceARNs.length === 0) {
        return;
    }
    const tagResourceCommand = new TagResourcesCommand({ ResourceARNList: resourceARNs, Tags: tags });
    return await taggingClient.send(tagResourceCommand);
}

const sleep = (ms) => new Promise(resolve => setTimeout(resolve, ms));

const microsvcStackName = microservice+'-microsvc-'+env;
const storageStackName = microservice+'-storage-'+env;

const mapping = require('./resource-tags.json')

async function tagStack(stackName) {
    return getResources(stackName).then(async (resources) => {
        //const uniqueResourceTypes = [...new Set(resources.map(r => r.ResourceType))];  
        
        // group resources by resourceType
        const resourcesByType = resources.reduce((acc, resource) => {
            if(!acc[resource.ResourceType]) {
                acc[resource.ResourceType] = [];
            }
            acc[resource.ResourceType].push(resource);
            return acc;
        }, {});
    
        // search configuration in mapping by resourceRype
        const tagsByResourceType = Object.entries(resourcesByType).reduce((acc, [resourceType, resources]) => {
            if(mapping[resourceType]) {
                acc[resourceType] = Object.assign({}, mapping[resourceType], mapping.default, { Environment: env, Microservice: microservice });
            } else {
                acc[resourceType] = Object.assign({}, mapping.default, { Environment: env, Microservice: microservice });
            }
            return acc;
        }, {});
    
    
        //console.log(tagsByResourceType)

        //console.log(resourcesByType)
        // tag resources
        /*const promises = Object.entries(tagsByResourceType).map(([resourceType, tags]) => {
            return tagResources(resourcesByType[resourceType], tags);
        });*/




        const res = Object.entries(tagsByResourceType)

        for(let i=0; i<res.length; i++){
            const [ resourceType, tags ] = res[i];
            console.log('applying tags ', tags, ' to resources of resources ', resourcesByType[resourceType])
            try {
                await tagResources(resourcesByType[resourceType], tags);
            } catch(e){
                console.error('Error applying tags to resources of type ', resourceType, ' - ', e)
            }
            await sleep(5000)
        }
    
        /*Promise.all(promises).then((result) => {
            console.log('Resources tagged');
        }).catch((err) => {
            console.error(err);
        });*/
    }).catch((err) => {
        console.error(err);
    })    
}

async function main(){
    await tagStack(microsvcStackName);
    await tagStack(storageStackName);
}

main().then(() => console.log('Tags applied successfully')).catch(err => console.error('Error applying tags:', err));