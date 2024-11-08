const { AwsClientsWrapper } = require("./libs/AwsClientWrapper");
const { parseArgs } = require('util');
const fs = require('fs');

function _checkingParameters(args, values){
  const usage = "Usage: index.js --envName <env-name> --cmd <command> [--parameter <parameter> --syncPath <syncPath> --configPath <configPath>]"
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
  { name: "parameter", mandatory: false, subcommand: [] },
  { name: "syncPath", mandatory: false, subcommand: ['parameter'] },
  { name: "configPath", mandatory: false, subcommand: [] },
]
const values = {
  values: { envName, cmd, parameter, syncPath, configPath },
} = parseArgs({
  options: {
    envName: {
      type: "string", short: "e", default: undefined
    },
    cmd: {
      type: "string", short: "c", default: undefined
    },
    parameter: {
      type: "string", short: "v", default: undefined
    },
    syncPath: {
      type: "string", short: "p", default: undefined
    },
    configPath: {
      type: "string", short: "p", default: undefined
    },
  },
});  


_checkingParameters(args, values)

const timestamp = new Date().toISOString()
const awsClient = new AwsClientsWrapper( envName );

function sanitizeFile(systemParameter){
  if(systemParameter.Tier==='Advanced'){
    return systemParameter.Name.replace(/\//g, '#')+'##A##' // advanced
  } else {
    return systemParameter.Name.replace(/\//g, '#') // no suffix for Standard Tier
  }
}

const appConfig = require('./config.json')

async function executeCommand(accountName){
  // list parameters -> return {}
  const parameters = await awsClient._listSSMParameters(accountName)
  const fullKeys = Object.keys(parameters)
  if(parameter) {
    if(fullKeys.indexOf(parameter) < 0) {
      console.log(`Parameter is not present in ${accountName} account`)
      return;
    }
    else {
      console.log(`Parameter found in ${accountName} account`)
    }
  }
  // remove from Parameters keys not included in appConfig.skipParameters 
  const keys = fullKeys.filter((k) => {
    return appConfig.skipParameters.indexOf(k)<0
  })

  for(let i=0; i<keys.length; i++) {
    parameters[keys[i]].Value = await awsClient._getSSMParameter(accountName, keys[i])
  }
  const syncBasePath = `${syncPath}/${envName}/_conf/${accountName}/system_params`
  const confBasePath = `${configPath}/${envName}/_conf/${accountName}/system_params`
  // dump into a specific folder
  if(cmd=='dump'){
    keys.forEach(key => {
      _writeInFile(confBasePath, sanitizeFile(parameters[key])+'.param', parameters[key].Value)
    })
  } else if(cmd=='compare'){
    // compare with a specific folder
    const files = fs.readdirSync(confBasePath)
    files.forEach(file => {
      const fileContent = fs.readFileSync(`${confBasePath}/${file}`, 'utf-8')
      const key = file.split('##A##')[0].replace(/#/g, '/')
      if(parameters[key].Value != fileContent){
        console.log('['+accountName+'] Parameter '+key+' has local changes')
      } else {
        console.log('['+accountName+'] Parameter '+key+' is in sync')
      }
    })
  } else if(cmd=='sync'){
    if(!parameter) {
      console.log("No parameter has been inserted")
      process.exit(1)
    }
    const manifest = JSON.parse(fs.readFileSync(`${syncBasePath}/_manifest.json`))

    for(const data of manifest) {
      if(data.paramName === parameter) {

        const valueBackup = await awsClient._getSSMParameter(accountName, data.paramName)
        const paramToSync = fs.readFileSync(`${syncBasePath}/${data.localName}`, 'utf-8')
        _writeInFile(`backup/${envName}/${timestamp}`, data.localName, valueBackup)
        console.log(`Backup available in ./backup/${envName}/${timestamp}/${data.localName}`)
        await awsClient._updateSSMParameter(accountName, data.paramName, data.tier, paramToSync)
        console.log(`DataStore ${data.paramName} updated successfully!!!`)
        return;
      }
    }
  }
}
async function main() {
  await executeCommand('core')
  await executeCommand('confinfo')
}

main();