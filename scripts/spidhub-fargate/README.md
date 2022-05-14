# SPID Hub Fargate

## Requirements

- AWS CLI `brew install awscli`
- jq `brew install jq`
- docker `brew install --cask docker`

Configure the AWS CLI via `aws configure`

## Deploy

Rename `UserRegistryApiKey.tmp.example` to `UserRegistryApiKey.tmp` and edit the
latter by specifying the key. All `.tmp` file are gitignored.

Edit the `setup.sh` file, populating the environment variables at the beginning
of the file.

> If you are provisioning the environment in a brand new account, set the
> `INITAL` environment variable to `true`; for the first run. Then take care to
> switche it back to `false` before subsequent invocations.

There is a sub-directory for each environment name, containing the parameters,
tags and configuration files for each microservice.

The `setup.sh` script main task is to package and deploy the `spudhub.yaml`
CloudFormation template, which in turns deploy its nested stacks (i.e. fragments).

> This approach allows to quickly move these templates under the already
> present CI/CD pipeline

By running the `setup.sh` script, all the necessary resources will be provisioned
and the microservices will be up and running.
