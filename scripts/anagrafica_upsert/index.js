const { AwsClientsWrapper } = require("./libs/AwsClientWrapper");
const { parseArgs } = require('util');
const fs = require('fs');


function _checkingParameters(args, values){
  const usage = "Usage: index.js --envName <envName> --tableName <tableName> --configPath <configPath> --cmd <cmd> [--batchDimension <batchDimension>] [--withRole <withRole>]"
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

const config = require("./config.json")

const args = [
  { name: "envName", mandatory: true, subcommand: [] },
  { name: "tableName", mandatory: true, subcommand: [] },
  { name: "configPath", mandatory: true, subcommand: [] },
  { name: "cmd", mandatory: false, subcommand: [] },
  { name: "batchDimension", mandatory: false, subcommand: [] },
  { name: "withRole", mandatory: false, subcommand: [] },
]
const values = {
  values: { envName, tableName, configPath, batchDimension, cmd, withRole },
} = parseArgs({
  options: {
    envName: {
      type: "string", short: "e", default: undefined
    },
    tableName: {
      type: "string", short: "t", default: undefined
    },
    configPath: {
      type: "string", short: "c", default: undefined
    },
    cmd: {
      type: "string", short: "d", default: "validate"
    },
    batchDimension: {
      type: "string", short: "b", default: "25"
    },
    withRole: {
      type: "boolean", short: "r", default: false
    }
  },
});  

_checkingParameters(args, values)
if(!config[tableName]) throw new Error("Missing configuration for table "+tableName) 

let profile = 'sso_pn-'+config[tableName].AccountName+'-'+envName
if(withRole){
  profile = 'default'
}

console.log('profile', profile)

const awsClient = new AwsClientsWrapper( profile );

function getImportFilePath(){
  const accountName = config[tableName].AccountName
  const localFile = configPath+'/'+envName+'/_conf/'+accountName+'/dynamodb/'+tableName+'.json'
  if(!fs.existsSync(localFile)){
    const globalFile = configPath+'/_conf/'+accountName+'/dynamodb/'+tableName+'.json'
    if(!fs.existsSync(globalFile)){
      throw new Error("Missing import file "+localFile+" or "+globalFile)
    }
    return globalFile
  }
  return localFile
}

const validateExecutor = async(lines, cfg) => {
  if(!cfg.tableConfig.ProtectedKey) return ;

  const tableKeyName = cfg.tableConfig.ProtectedKey.name
  const tableKeyValues = cfg.tableConfig.ProtectedKey.values

  lines.forEach(l => {
    if(!l) return;
    const line = JSON.parse(l)
    const lineKeyValue = line[tableKeyName].S
    if(tableKeyValues.indexOf(lineKeyValue)>=0){
      throw new Error("The import file contains the protected key "+tableKeyName+" and value "+lineKeyValue+"")
    }
  })

  return {
    validation: true
  }
}

async function dumpTable(tableName){
  let results = []
  let first = true;
  let lastEvaluatedKey = null
  while(first || lastEvaluatedKey != null) {
    const res = await awsClient._scanRequest(tableName, lastEvaluatedKey);
    if(res.LastEvaluatedKey) {
      lastEvaluatedKey = res.LastEvaluatedKey
    } 
    else {
      lastEvaluatedKey = null;
      first = false;
    }
    results = results.concat(res.Items);
  }

  return results
}

const compareExecutor = async(lines, cfg) => {
  // download from dynamodb
  const items = await dumpTable(cfg.tableName)
  const localItems = lines.map(JSON.parse)

  // compare array of json objects to find different items, items in dynamodb but not in local file and items in local file but not in dynamodb
  const differentItems = []
  const itemsInDynamoDbButNotInLocalFile = []
  const itemsInLocalFileButNotInDynamoDb = []

  items.forEach(item => {
    const localItem = localItems.find(localItem => {
      const tableKeys = cfg.tableConfig.Keys
      
      const keysAreEqual = tableKeys.every(key => {
        return localItem[key].S == item[key].S
      })

      return keysAreEqual
    })

    if(!localItem) {
      itemsInDynamoDbButNotInLocalFile.push(item)
    }
    else {
      if(JSON.stringify(item) != JSON.stringify(localItem)){
        differentItems.push({ dynamodb: item, local: localItem })
      }
    }
  })

  localItems.forEach(localItem => {
    const item = items.find(item => {
      const tableKeys = cfg.tableConfig.Keys
      
      const keysAreEqual = tableKeys.every(key => {
        return localItem[key].S == item[key].S
      })

      return keysAreEqual
    })

    if(!item) {
      itemsInLocalFileButNotInDynamoDb.push(localItem)
    }
  })

  return {
    differentItems,
    itemsInDynamoDbButNotInLocalFile,
    itemsInLocalFileButNotInDynamoDb
  
  }
}

const syncExecutor = async(lines, cfg) => {
  const validateExecutor = makeExecutor("validate")
  await validateExecutor(lines, cfg)

  const elements = lines.map(JSON.parse);
  const batchDimension = Number(cfg.batchDimension)
  for (i = 0; i < elements.length; i = i+batchDimension){
    const batch = elements.slice(i, i+batchDimension);
    console.log("N° " + ((i+batchDimension > elements.length) ? elements.length : i+batchDimension) + " elements imported!")
    await awsClient._batchWriteItems(cfg.tableName, batch);
  }

  return {
    total: elements.length
  }
}

function makeExecutor(cmd){

  switch(cmd){
    case "validate":
      return validateExecutor
    case "compare":
      return compareExecutor
    case "sync":
      return syncExecutor
    default:
      throw new Error("Command "+cmd+" not supported")
  }

}

async function main() {

  const fileName = getImportFilePath()
  console.log('filename '+fileName)
  const data = fs.readFileSync(fileName, { encoding: 'utf8', flag: 'r' });
  const lines = data.trim().split('\n');

  const commandExecutor = makeExecutor(cmd)

  const res = await commandExecutor(lines, {
    tableName,
    tableConfig: config[tableName],
    batchDimension
  })

  console.log("Command "+cmd+" complete")

  fs.writeFileSync('./result/'+(new Date().toISOString())+'_'+tableName+'_'+cmd+'.json', JSON.stringify(res, null, 2))
}

main();