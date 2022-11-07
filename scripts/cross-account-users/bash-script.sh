#!/bin/bash

# 0. Set the variables
for ARGUMENT in "$@"; do
  KEY=$(echo $ARGUMENT | cut -f1 -d=)

  KEY_LENGTH=${#KEY}
  VALUE="${ARGUMENT:$KEY_LENGTH+1}"

  export "$KEY"="$VALUE"
done

echo "REGION = $REGION"
## Receives the profile name for CICD account
echo "CICD_PROFILE = $CICD_PROFILE"
## Receives a list of dev profiles, for example DEV_PROFILES=(profile1 profile2 profile3)
echo "DEV_PROFILES = $DEV_PROFILES"
## Receives a list of dev profiles, for example HOTFIX_PROFILES=(profile1 profile2 profile3)
echo "HOTFIX_PROFILES = $HOTFIX_PROFILES"

# Get Profiles for DEV and HOTFIX
environments=($DEV_PROFILES $HOTFIX_PROFILES)

echo Enviroments
printf '%s\n' "${environments[@]}"
# echo $accountProfile

# Get the CICD Account ID

cicdAccount=$(aws sts get-caller-identity \
  --query "Account" \
  --output text \
  --profile $CICD_PROFILE)

scriptDir=$(dirname "$0")

## Create stack function
function createOrUpdateStack() {
  profile=$1
  region=$2
  stackName=$3
  templateFile=$4

  shift
  shift
  shift
  shift

  echo "Start stack ${stackName} creation or update"
  aws --profile $profile --region $region cloudformation deploy \
    --stack-name ${stackName} \
    --template-file ${scriptDir}/cnf-templates/${templateFile} \
    --capabilities CAPABILITY_NAMED_IAM \
    --parameter-override $@ \
    TrustedAccountId=$cicdAccount
}

# Get the ARN of the AdministratorAccess and ReadOnly Access
function getRoleArn() {
  arraVar=$(aws cloudformation describe-stacks \
    --stack-name cross-account-$1 \
    --profile $1 \
    --region $REGION \
    --query "Stacks[0].Outputs[?OutputKey=='RolesArnJson'].OutputValue" \
    --output text)

  readOnlyRoleArn=$(echo $arraVar | jq '."pn-read-only"')
  adminRoleArn=$(echo $arraVar | jq '."pn-admin"')

  ## Creating IAM roles
  createAssumeRolePolicies assume-role-read-only-$1 pn-read-only-$account $readOnlyRoleArn
  createAssumeRolePolicies assume-role-admin-$1 pn-admin-$account $adminRoleArn

  echo "ReadOnly: $readOnlyRoleArn"
  echo "Admin: $adminRoleArn"
}

function createAssumeRolePolicies() {
  aws iam create-policy --profile $CICD_PROFILE --policy-name $1 --tags Key=$2,Value=true --policy-document '{"Version":"2012-10-17","Statement":[{"Action":["sts:AssumeRole"],"Resource":'"$3"',"Effect":"Allow"}]}'
}

# 1. Launch the stack for each environment
for environment in ${environments[@]}; do

  for account in ${environment[@]}; do

    echo "Deploying Stack in $account"
    createOrUpdateStack $account $REGION cross-account-$account cross-account-role.yaml "Environment=${account}"

    ## 2. Create Assumerole policies in CICD account
    getRoleArn $account

  done
done

# 3. Deploy the stack in CICD Account

echo "Deploying Stack in $CICD_PROFILE account"
createOrUpdateStack $CICD_PROFILE $REGION cross-account-cicd cicd-account.yaml

# 4. If $REGION is not set to us-east-1, then deploy the event routing
if [[ "$REGION" != "us-east-1" ]]; then
  ## a. Get the ARN of the default event bus for the CICD account in $REGION
  EventBus_ARN=$(aws events list-event-buses \
    --query "EventBuses[?Name == 'default'].Arn" \
    --region $REGION \
    --profile $CICD_PROFILE \
    --output text)

  ## b. Deploy cicd-account-event-routing.yaml
  aws cloudformation deploy \
    --stack-name cross-account-event-routing \
    --template-file ./cnf-templates/cicd-account-event-routing.yaml \
    --capabilities CAPABILITY_NAMED_IAM \
    --parameter-overrides \
    CrossRegionDestinationBus=$EventBus_ARN \
    --profile $CICD_PROFILE \
    --region us-east-1
fi