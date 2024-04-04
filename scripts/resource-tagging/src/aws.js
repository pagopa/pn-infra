const { STSClient, GetCallerIdentityCommand } = require("@aws-sdk/client-sts"); 
const { fromIni } = require("@aws-sdk/credential-provider-ini");
const { CloudFormationClient, ListStackResourcesCommand } = require("@aws-sdk/client-cloudformation");
const { ResourceGroupsTaggingAPIClient, TagResourcesCommand } = require("@aws-sdk/client-resource-groups-tagging-api");
const { IGNORED_RESOURCE_TYPES, RESOURCE_TAGGED_PER_API_CALL, WAIT_TIME_BETWEEN_TAGS_MS } = require("./const");
const { getResourceArnByCloudformationResource } = require("./arn");
const { sleep } = require("./util");

class ResourceTagger {

    constructor(values) {
        const { envName, region, accountType } = values;
        const profile = 'sso_pn-'+accountType+'-'+envName

        const configObj = {
            region: region,
            credentials: fromIni({ 
                profile: profile,
            })
        };
        
        this.cloudFormationClient = new CloudFormationClient(configObj);
        this.taggingClient = new ResourceGroupsTaggingAPIClient(configObj);
        this.stsClient = new STSClient(configObj);
    }

    async getAccountId(){
        const input = {}
        const command = new GetCallerIdentityCommand(input);
        const response = await this.stsClient.send(command);
        return response.Account;
    }

    async getResources(stackName, nested = false) {
        const resources = [];
        
        let nextToken = null;
        do {
            const response = await this.cloudFormationClient.send(new ListStackResourcesCommand({ StackName: stackName, NextToken: nextToken }));
            // add FromNested property to response.StackResourceSummaries
            response.StackResourceSummaries.forEach(r => r.FromNested = nested);
            resources.push(...response.StackResourceSummaries);
            nextToken = response.NextToken;
        } while (nextToken);
    
        const nestedStacks = resources.filter(r => r.ResourceType === 'AWS::CloudFormation::Stack');
    
        if(nestedStacks.length > 0) {
            for (const nestedStack of nestedStacks) {
                const nestedStackResources = await this.getResources(nestedStack.PhysicalResourceId, true);
                resources.push(...nestedStackResources);
            }
        }
    
        return resources.filter(r => r.ResourceType !== 'AWS::CloudFormation::Stack');
    }
    

    async tagResources(resources, tags, ctx = {}) {
        const resourceARNs = resources.filter((r) => {
            return IGNORED_RESOURCE_TYPES.indexOf(r.ResourceType) === -1;
        }).map(r => getResourceArnByCloudformationResource(r, ctx));

        console.log('Tagging resources:', resourceARNs, 'with tags:', tags)
        if(resourceARNs.length === 0) {
            return;
        }

        // divide resources in two groups according to FromNested property
        const nestedResources = resourceARNs.filter(r => r.FromNested);
        const notNestedResources = resourceARNs.filter(r => !r.FromNested);

        // tag nested resource
        if(nestedResources.length > 0) {
            tags.Source = 'https://github.com/pagopa/'+ctx.microserviceName

            // split in batch of RESOURCE_TAGGED_PER_API_CALL and do multiple calls
            const chunks = [];
            for (let i = 0; i < nestedResources.length; i += RESOURCE_TAGGED_PER_API_CALL) {
                chunks.push(nestedResources.slice(i, i + RESOURCE_TAGGED_PER_API_CALL));
            }

            for (const chunk of chunks) {
                const tagResourceCommand = new TagResourcesCommand({ ResourceARNList: chunk, Tags: tags });
                await this.taggingClient.send(tagResourceCommand);
                await sleep(WAIT_TIME_BETWEEN_TAGS_MS)
            }
        }

        // tag not nested resources
        if(notNestedResources.length > 0) {
            // update tags Source with new value "pn-infra"
            tags.Source = 'https://github.com/pagopa/pn-infra'

            // split in batch of RESOURCE_TAGGED_PER_API_CALL and do multiple calls
            const chunks = [];
            for (let i = 0; i < notNestedResources.length; i += RESOURCE_TAGGED_PER_API_CALL) {
                chunks.push(notNestedResources.slice(i, i + RESOURCE_TAGGED_PER_API_CALL));
            }

            for (const chunk of chunks) {
                const tagResourceCommand = new TagResourcesCommand({ ResourceARNList: chunk, Tags: tags });
                await this.taggingClient.send(tagResourceCommand);
                await sleep(WAIT_TIME_BETWEEN_TAGS_MS)
            }
        }

        return true
    }
}

module.exports = {
    ResourceTagger,
}