const { STSClient, GetCallerIdentityCommand } = require("@aws-sdk/client-sts"); 
const { fromIni } = require("@aws-sdk/credential-provider-ini");
const { CloudFormationClient, ListStackResourcesCommand } = require("@aws-sdk/client-cloudformation");
const { ResourceGroupsTaggingAPIClient, TagResourcesCommand } = require("@aws-sdk/client-resource-groups-tagging-api");
const { parseArgs } = require('util');


function _checkingParameters(args, values){
  const usage = "Usage: index.js --envName <envName> --microserviceName <microserviceName> --region <region> --accountType <accountType>"
  //CHECKING PARAMETER
  args.forEach(el => {
    if(el.mandatory && !values.values[el.name]){
      console.log("Param " + el.name + " is not defined")
      console.log(usage)
      process.exit(1)
    }
  })
  args.filter(el=> {
    return el.subcommand.length > 0
  }).forEach(el => {
    if(values.values[el.name]) {
      el.subcommand.forEach(val => {
        if (!values.values[val]) {
          console.log("SubParam " + val + " is not defined")
          console.log(usage)
          process.exit(1)
        }
      })
    }
  })
}

const args = [
  { name: "envName", mandatory: true, subcommand: [] },
  { name: "microserviceName", mandatory: true, subcommand: [] },
  { name: "region", mandatory: false, subcommand: [] },
  { name: "accountType", mandatory: true, subcommand: [] },
]
const values = {
  values: { envName, microserviceName, region, accountType },
} = parseArgs({
  options: {
    envName: {
      type: "string", short: "e", default: undefined
    },
    microserviceName: {
      type: "string", short: "m", default: undefined
    },
    region: {
      type: "string", short: "r", default: 'eu-suoth-1'
    },
    accountType: {
      type: "string", short: "a", default: undefined
    },
  },
});  

_checkingParameters(args, values)

const profile = 'sso_pn-'+accountType+'-'+envName

const configObj = {
    region: region,
    credentials: fromIni({ 
        profile: profile,
    })
};

const cloudFormationClient = new CloudFormationClient(configObj);
const taggingClient = new ResourceGroupsTaggingAPIClient(configObj);
const stsClient = new STSClient(configObj);

async function getAccountId(){
    const input = {}
    const command = new GetCallerIdentityCommand(input);
    const response = await stsClient.send(command);
    return response.Account;
}

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

function getResourceArnByCloudformationResource(resource, ctx = {}){
    const { ResourceType, PhysicalResourceId } = resource;
    const { Account: accountId } = ctx;

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

async function tagResources(resources, tags, ctx = {}) {
    const resourceARNs = resources.filter((r) => {
        return ['AWS::CloudWatch::Dashboard', 'AWS::Logs::MetricFilter', 'AWS::Logs::SubscriptionFilter'].indexOf(r.ResourceType) === -1;
    }).map(r => getResourceArnByCloudformationResource(r, ctx));

    console.log('Tagging resources:', resourceARNs, 'with tags:', tags)
    if(resourceARNs.length === 0) {
        return;
    }
    const tagResourceCommand = new TagResourcesCommand({ ResourceARNList: resourceARNs, Tags: tags });
    return await taggingClient.send(tagResourceCommand);
}

const sleep = (ms) => new Promise(resolve => setTimeout(resolve, ms));

const microsvcStackName = microserviceName+'-microsvc-'+envName;
const storageStackName = microserviceName+'-storage-'+envName;

const mapping = require('./resource-tags.json')

async function tagStack(stackName, ctx = {}) {
    return getResources(stackName).then(async (resources) => {
        
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
                acc[resourceType] = Object.assign({}, mapping[resourceType], mapping.default, { Environment: envName, Source: 'https://github.com/pagopa/'+microserviceName,  Microservice: microserviceName });
            } else {
                acc[resourceType] = Object.assign({}, mapping.default, { Environment: envName, Source: 'https://github.com/pagopa/'+microserviceName, Microservice: microserviceName });
            }
            return acc;
        }, {});
    
    
        const res = Object.entries(tagsByResourceType)

        for(let i=0; i<res.length; i++){
            const [ resourceType, tags ] = res[i];
            console.log('applying tags ', tags, ' to resources of resources ', resourcesByType[resourceType])
            try {
                await tagResources(resourcesByType[resourceType], tags, ctx);
            } catch(e){
                console.error('Error applying tags to resources of type ', resourceType, ' - ', e)
            }
            await sleep(5000)
        }
    
    }).catch((err) => {
        console.error(err);
    })    
}

async function main(){
    const accountId = await getAccountId();
    const ctx = {
        Account: accountId,
    }

    await tagStack(microsvcStackName, ctx);
    await tagStack(storageStackName, ctx);
}

main().then(() => console.log('Tags applied successfully')).catch(err => console.error('Error applying tags:', err));