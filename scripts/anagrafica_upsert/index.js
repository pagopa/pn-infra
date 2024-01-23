const { AwsClientsWrapper } = require("./libs/AwsClientWrapper");
const { parseArgs } = require('util');
const fs = require('fs');


function _checkingParameters(args, values){
  const usage = "Usage: index.js --envName <envName> --tableName <tableName> --configPath <configPath> --cmd <cmd> [--batchDimension <batchDimension>]"
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
]
const values = {
  values: { envName, tableName, configPath, batchDimension },
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
  },
});  

if(!config[tableName]) throw new Error("Missing configuration for table "+tableName) 

const profile = 'sso_pn-'+config[tableName].AccountName+'-'+envName

console.log('profile', profile)

_checkingParameters(args, values)
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
}

const compareExecutor = async(lines, cfg) => {
  return true
}

const syncExecutor = async(lines, cfg) => {
  const elements = lines.map(JSON.parse);
  const batchDimension = Number(cfg.batchDimension)
  for (i = 0; i < elements.length; i = i+batchDimension){
    const batch = elements.slice(i, i+batchDimension);
    console.log("N° " + ((i+batchDimension > elements.length) ? elements.length : i+batchDimension) + " elements imported!")
    await awsClient._batchWriteItems(cfg.tableName, batch);
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

  validateLines(lines)

  const commandExecutor = makeExecutor(cmd)

  await commandExecutor(lines, {
    tableName,
    tableConfig: config[tableName],
    batchDimension
  })
  /*const elements = lines.map(JSON.parse);
  batchDimension = Number(batchDimension)
  for (i = 0; i < elements.length; i = i+batchDimension){
    const batch = elements.slice(i, i+batchDimension);
    console.log("N° " + ((i+batchDimension > elements.length) ? elements.length : i+batchDimension) + " elements imported!")
    await awsClient._batchWriteItems(tableName, batch);
    
  }*/
  console.log("Command "+cmd+" complete")
}

main();