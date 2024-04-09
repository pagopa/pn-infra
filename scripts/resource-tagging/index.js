const { parseArgs } = require('util');
const { WAIT_TIME_BETWEEN_TAGS_MS, ALL_MICROSERVICES } = require("./src/const");
const { sleep } = require("./src/util");
const mapping = require('./resource-tags.json');
const { ResourceTagger } = require("./src/aws");

function _checkingParameters(args, values){
  const usage = "Usage: index.js --envName <envName> [--microserviceName <microserviceName>] --region <region> --accountType <accountType>"
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
  { name: "microserviceName", mandatory: false, subcommand: [] },
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
      type: "string", short: "r", default: 'eu-south-1'
    },
    accountType: {
      type: "string", short: "a", default: undefined
    },
  },
});  

_checkingParameters(args, values)

class Runner {

    #runningMode;
    #cfg

    constructor(cfg) {
        this.resourceTagger = new ResourceTagger(cfg);
        if(!cfg.microserviceName){
            this.#runningMode = 'ALL';
        }
        this.#cfg = cfg;
    }

    async tagStack(stackName, ctx = {}) {
        return this.resourceTagger.getResources(stackName).then(async (resources) => {
            
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
                    acc[resourceType] = Object.assign({}, mapping[resourceType], mapping.default, { Environment: this.#cfg.envName,  Microservice: ctx.microserviceName });
                } else {
                    acc[resourceType] = Object.assign({}, mapping.default, { Environment: this.#cfg.envName, Microservice: ctx.microserviceName });
                }
                return acc;
            }, {});
        
        
            const res = Object.entries(tagsByResourceType)
    
            for(let i=0; i<res.length; i++){
                const [ resourceType, tags ] = res[i];
                console.log('applying tags ', tags, ' to resources of resources ', resourcesByType[resourceType])
                try {
                    await this.resourceTagger.tagResources(resourcesByType[resourceType], tags, ctx);
                } catch(e){
                    console.error('Error applying tags to resources of type ', resourceType, ' - ', e)
                }
                await sleep(WAIT_TIME_BETWEEN_TAGS_MS)
            }
        
        }).catch((err) => {
            console.error(err);
        })    
    }

    async runSingleSvc() {
        const accountId = await this.resourceTagger.getAccountId();
        const ctx = {
            Account: accountId,
            microserviceName: this.#cfg.microserviceName
        }

        const microsvcStackName = microserviceName+'-microsvc-'+envName;
        const storageStackName = microserviceName+'-storage-'+envName;
    
        await this.tagStack(microsvcStackName, ctx);
        await this.tagStack(storageStackName, ctx);
    }

    async runAll() {
        const accountId = await this.resourceTagger.getAccountId();
        const ctx = {
            Account: accountId,
        }

        // list of microservices
        const microservices = ALL_MICROSERVICES[this.#cfg.accountType];
    
        for(let i=0; i<microservices.length; i++){
            const microserviceName = microservices[i];
            const microsvcStackName = microserviceName+'-microsvc-'+envName;
            const storageStackName = microserviceName+'-storage-'+envName;

            ctx.microserviceName = microserviceName; 

            await this.tagStack(microsvcStackName, ctx);
            await this.tagStack(storageStackName, ctx);
        }
    }

    async run() {
        if(this.#runningMode==='ALL'){
            console.info('Running in ALL mode')
            await this.runAll();
        } else {
            console.info('Running in SINGLE mode: '+this.#cfg.microserviceName)
            await this.runSingleSvc();
        }
    }
}

async function main(){
    const runner = new Runner({ envName, region, accountType, microserviceName });
    await runner.run();
}

main().then(() => console.log('Tags applied successfully')).catch(err => console.error('Error applying tags:', err));