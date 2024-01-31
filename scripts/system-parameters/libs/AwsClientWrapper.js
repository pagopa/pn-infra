
const { fromIni } = require("@aws-sdk/credential-provider-ini");
const { SSMClient, GetParameterCommand, PutParameterCommand, DescribeParametersCommand} = require("@aws-sdk/client-ssm");
function awsClientCfg( profile ) {
  const self = this;
  //if(!profileName){
    return { 
      region: "eu-south-1", 
      credentials: fromIni({ 
        profile: profile,
      })
    }
  //}
}

class AwsClientsWrapper {

  constructor( envName, profileName, roleArn ) {
    const ssoCoreProfile = `sso_pn-core-${envName}`
    const ssoConfinfoProfile = `sso_pn-confinfo-${envName}`
    this._ssmCoreClient = new SSMClient( awsClientCfg( ssoCoreProfile, profileName, roleArn ))
    this._ssmConfinfoClient = new SSMClient( awsClientCfg( ssoConfinfoProfile, profileName, roleArn ))
  }

  _getClient(accountName) {
    switch(accountName) {
      case 'core':
        return this._ssmCoreClient
      case 'confinfo':
        return this._ssmConfinfoClient
    }
  }

  async _getSSMParameter(accountName, param) {
    const input = { // GetParameterRequest
      Name: param, // required
      WithDecryption: true,
    };
    const res = await this._getClient(accountName).send(new GetParameterCommand(input));
    if(res) {
      return res.Parameter.Value
    }
  }

  async _getSSMParameterDescriptionTier(accountName, param) {
    const input = { // DescribeParametersRequest
      Filters: [ // ParametersFilterList
        { // ParametersFilter
          Key: "Name", // required
          Values: [ // ParametersFilterValueList // required
            param,
          ],
        },
      ],
    };
    const res = await this._getClient(accountName).send(new DescribeParametersCommand(input));
    if(res) {
      var parameters = {}
      res.Parameters?.forEach(x => {
          parameters[x.Name] = x.Tier; 
      })
      return parameters
    }
    else {
      this._errorDuringProcess(res.httpStatusCode, "_getSSMParameterDescriptionTier")
    }
  }

  async _updateSSMParameter(name, tier, value) {
    const input = { // PutParameterRequest
      Name: name, // required
      Value: value, // required
      Type: "String", 
      Overwrite: true,
      Tier: tier,
    };
    const command = new PutParameterCommand(input);
    const res = await this._getClient(accountName).send(command);
    if(res["$metadata"].httpStatusCode != 200) 
      this._errorDuringProcess(res.httpStatusCode, "_updateSSMParameter")
  }

  async _listSSMParameters(accountName) {
    const input = { // DescribeParametersRequest
      Filters: [ // ParametersFilterList
        
      ],
      MaxResults: 50,
    };

    // pagination and return all parameters
    var parameters = {}
    var nextToken = ""
    do {
      input.NextToken = nextToken
      const res = await this._getClient(accountName).send(new DescribeParametersCommand(input));
      if(res) {
        res.Parameters?.forEach(x => {
            parameters[x.Name] = x
        })
        nextToken = res.NextToken ? res.NextToken : ""
      }
      else {
        this._errorDuringProcess(res.httpStatusCode, "_listSSMParameters")
      }
    } while (nextToken != "")        

    return parameters;

  }

  _errorDuringProcess(httpStatusCode, methodName){
    console.error("Error during process, HTTPStatusCode= " + httpStatusCode + " during " + methodName + " method execution")
    process.exit(1)
  }
}

exports.AwsClientsWrapper = AwsClientsWrapper;

