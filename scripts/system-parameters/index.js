const { AwsClientsWrapper } = require("./libs/AwsClientWrapper");
const { parseArgs } = require('util');
const fs = require('fs');

function _checkingParameters(args, values){
  const usage = "Usage: index.js --envName <env-name> --cmd <command> [--configPath <configPath>]"
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

function _writeInFile(resultFolder, filename, data) {
  fs.mkdirSync(resultFolder, { recursive: true });
  fs.writeFileSync(resultFolder + '/'+ filename, data, 'utf-8')
}

const args = [
  { name: "envName", mandatory: true, subcommand: [] },
  { name: "cmd", mandatory: true, subcommand: [] },
  { name: "configPath", mandatory: false, subcommand: [] },
]
const values = {
  values: { envName, cmd, configPath },
} = parseArgs({
  options: {
    envName: {
      type: "string", short: "e", default: undefined
    },
    cmd: {
      type: "string", short: "c", default: undefined
    },
    configPath: {
      type: "string", short: "p", default: undefined
    },
  },
});  

_checkingParameters(args, values)

const awsClient = new AwsClientsWrapper( envName );

function sanitizeFile(systemParameter){
  return systemParameter.Name.replace(/\//g, '#')+'##T##'+systemParameter.Tier
}

async function executeCommand(accountName){
  // list parameters -> return {}
  const parameters = await awsClient._listSSMParameters(accountName)
  
  const keys = Object.keys(parameters)
  for(let i=0; i<keys.length; i++) {
    parameters[keys[i]].Value = await awsClient._getSSMParameter(accountName, keys[i])
  }

  // dump into a specific folder
  if(cmd=='dump'){
    keys.forEach(key => {
      _writeInFile(configPath+'/'+envName+'/_conf/'+accountName+'/system_params/', sanitizeFile(parameters[key])+'.param', parameters[key].Value)
    })
  } else if(cmd=='compare'){
    // compare with a specific folder
    const files = fs.readdirSync(configPath+'/'+envName+'/_conf/'+accountName+'/system_params/')
    files.forEach(file => {
      const fileContent = fs.readFileSync(configPath+'/'+envName+'/_conf/'+accountName+'/system_params/'+file, 'utf-8')
      const key = file.split('##T##')[0].replace(/#/g, '/')
      if(parameters[key].Value != fileContent){
        console.log('['+accountName+'] Parameter '+key+' is in sync')
      } else {
        console.log('['+accountName+'] Parameter '+key+' has local changes')
      }
    })
  }
}
async function main() {
  await executeCommand('core')
  await executeCommand('confinfo')
}

main();