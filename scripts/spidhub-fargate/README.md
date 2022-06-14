# SPID Hub Fargate

## Requirements

- AWS CLI `brew install awscli`
- jq `brew install jq`
- docker `brew install --cask docker`

Configure the AWS CLI via `aws configure`

## Deploy

Run the `setup.sh` with the following parameters:

- _profile_: aws profile configured to connect to deployment account 
- _region_: target region for ECS deployment
- _environment_: folder name in _environments_ directory with the configuration to apply   
- _user-registry-api-key_: api key used for authentication in user registry API.

By running the `setup.sh` script, all the necessary resources will be provisioned
and the microservices will be up and running.

There is a sub-directory in _environments_ for each environment name, containing the parameters,
tags and configuration files for each microservice.

The `setup.sh` script main task is to package and deploy the `spudhub.yaml`
CloudFormation template, which in turns deploy its nested stacks (i.e. fragments).

> This approach allows to quickly move these templates under the already
> present CI/CD pipeline


