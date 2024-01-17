const { AwsClientsWrapper } = require("./libs/AwsClientWrapper");
const { parseArgs } = require('util');
const fs = require('fs');


function _checkingParameters(args, values){
  const usage = "Usage: index.js --envName <envName> --tableName <tableName> --configPath <configPath> [--batchDimension <batchDimension>] [--withSecretsValues]"
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
  { name: "withSecretValues", mandatory: false, subcommand: [] },
  { name: "batchDimension", mandatory: false, subcommand: [] },
]
const values = {
  values: { envName, tableName, configPath, batchDimension, withSecretValues},
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
    withSecretValues: {
      type: "boolean", short: "s", default: false
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

function validateLines(lines){
  if(!config[tableName].SecretAttributes || config[tableName].SecretAttributes.length==0) return;

  const tableKeyName = config[tableName].Key.name
  const tableKeyValue = config[tableName].Key.value
  const secretAttributes = config[tableName].SecretAttributes

  if(withSecretValues){
    lines.forEach(l => {
      if(!l) return;
      const line = JSON.parse(l)
      const lineKeyValue = line[tableKeyName].S
      if(lineKeyValue===tableKeyValue){
        secretAttributes.forEach(secretAttribute => {
          if(!line[secretAttribute].S){
            throw new Error("The import file does not contain the secret attribute "+secretAttribute+" for key "+lineKeyValue+' and value '+lineKeyValue)
          }

          if(line[secretAttribute].S.indexOf('<secret:')<0){
            throw new Error("The import file does not contain the secret attribute placeholder in "+secretAttribute+" for key "+lineKeyValue+' and value '+lineKeyValue)
          }
        })
      }
    })
  } else {
    lines.forEach(l => {
      if(!l) return;
      const line = JSON.parse(l)
      const lineKeyValue = line[tableKeyName].S
      if(lineKeyValue===tableKeyValue){
        throw new Error("The import file contains the key "+tableKeyName+" and value "+lineKeyValue+" while the withSecretValues flag is not set")
      }
    })
  }
}

function getImportFilePath(){
  const accountName = config[tableName].AccountName
  const withSecretValuesStr = withSecretValues ? '-secrets' : ''
  const localFile = configPath+'/'+envName+'/_conf/'+accountName+'/dynamodb/'+tableName+withSecretValuesStr+'.json'
  if(!fs.existsSync(localFile)){
    const globalFile = configPath+'/_conf/'+accountName+'/dynamodb/'+tableName+'.json'
    if(!fs.existsSync(globalFile)){
      throw new Error("Missing import file "+localFile+" or "+globalFile)
    }
    return globalFile
  }
  return localFile
}

async function main() {

  const fileName = getImportFilePath()
  console.log('filename '+fileName)
  const data = fs.readFileSync(fileName, { encoding: 'utf8', flag: 'r' });
  const lines = data.trim().split('\n');

  validateLines(lines)
  /*const elements = lines.map(JSON.parse);
  batchDimension = Number(batchDimension)
  for (i = 0; i < elements.length; i = i+batchDimension){
    const batch = elements.slice(i, i+batchDimension);
    console.log("N° " + ((i+batchDimension > elements.length) ? elements.length : i+batchDimension) + " elements imported!")
    await awsClient._batchWriteItems(tableName, batch);
    
  }*/
  console.log("Import Complete")
}

main();