const { fromIni } = require("@aws-sdk/credential-provider-ini");
const { CloudFormationClient, ListStackResourcesCommand } = require("@aws-sdk/client-cloudformation");
const { ResourceGroupsTaggingAPIClient, TagResourcesCommand } = require("@aws-sdk/client-resource-groups-tagging-api");

const env = 'dev'
const profile = 'sso_pn-core-'+env
const microservice = 'pn-delivery-push';

const configObj = {
    region: 'eu-south-1',
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

async function tagResources(resources, tags) {
    const resourceARNs = resources.map(r => r.PhysicalResourceId);
    const awsTags = Object.entries(tags).map(([Key, Value]) => ({ Key, Value }));
    const tagResourceCommand = new TagResourcesCommand({ ResourceARNList: resourceARNs, Tags: awsTags });
    return await taggingClient.send(tagResourceCommand);
}

const microsvcStackName = microservice+'-microsvc-'+env;
const storageStackName = microservice+'-storage-'+env;

const mapping = require('./resource-tags.json')

async function tagStack(stackName) {
    return getResources(stackName).then((resources) => {
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
            }
            return acc;
        }, {});
    
    
        // tag resources
        const promises = Object.entries(tagsByResourceType).map(([resourceType, tags]) => {
            return tagResources(resourcesByType[resourceType], tags);
        });
    
        Promise.all(promises).then((result) => {
            console.log('Resources tagged');
        }).catch((err) => {
            console.error(err);
        });
    }).catch((err) => {
        console.error(err);
    })    
}

async function main(){
    await tagStack(microsvcStackName);
    await tagStack(storageStackName);
}

main().then(() => console.log('Tags applied successfully')).catch(err => console.error('Error applying tags:', err));