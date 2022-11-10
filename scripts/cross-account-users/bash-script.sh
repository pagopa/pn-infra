#!/bin/bash

# 0. Set the variables
for ARGUMENT in "$@"; do
  KEY=$(echo $ARGUMENT | cut -f1 -d=)

  KEY_LENGTH=${#KEY}
  VALUE="${ARGUMENT:$KEY_LENGTH+1}"

  export "$KEY"="$VALUE"
done

## Receives the profile name for CICD account and the region
echo "REGION = $REGION"
echo "CICD_PROFILE = $CICD_PROFILE"

## Receives a list of profiles to deploy the cross account stacks in for example DEV_PROFILE=profile1,profile2,profile3
## String converted to Bash Array
IFS=',' read -r -a arrProfiles <<< "$PROFILES"
PROFILES=${arrProfiles[@]}
echo "PROFILES = $PROFILES"

IFS=',' read -r -a ACCOUNT_NAMES <<< "$ACCOUNT_NAMES"

# Get the CICD Account ID
cicdAccountId=$(aws sts get-caller-identity \
  --query "Account" \
  --output text \
  --profile $CICD_PROFILE)

scriptDir=$(dirname "$0")
echo $scriptDir

## Create stack function
function createOrUpdateStack() {
  profile=$1
  region=$2
  stackName=$3
  templateFile=$4

  shift 4

  echo "Start stack ${stackName} creation or update"
  if [[ ! -z $@ ]]; then
    aws --profile $profile --region $region cloudformation deploy \
      --stack-name ${stackName} \
      --template-file ${scriptDir}/cnf-templates/${templateFile} \
      --capabilities CAPABILITY_NAMED_IAM \
      --parameter-override $@
  else
    aws --profile $profile --region $region cloudformation deploy \
      --stack-name ${stackName} \
      --template-file ${scriptDir}/cnf-templates/${templateFile} \
      --capabilities CAPABILITY_NAMED_IAM
  fi 
}

# Get the ARN of the AdministratorAccess and ReadOnly Access
function getRoleArn() {
  profile=$1
  region=$2
  accountName=$3

  # Global variables
  arraVar=$(aws cloudformation describe-stacks \
    --stack-name cross-account-$accountName \
    --profile $profile \
    --region $region \
    --query "Stacks[0].Outputs[?OutputKey=='RolesArnJson'].OutputValue" \
    --output text)
  keys=$(echo $arraVar | jq 'keys[]')
}

function createAssumeRolePolicies() {
  echo "Creating Assume Role Policy $1"
  aws iam --profile $CICD_PROFILE --region $REGION create-policy \
    --policy-name $1 \
    --tags Key=$2,Value=true \
    --policy-document '{"Version":"2012-10-17","Statement":[{"Action":["sts:AssumeRole"],"Resource":'"$3"',"Effect":"Allow"}]}'
}

INDEX=0
# 1. Launch the stack for each Dev Profile
for profile in ${PROFILES[@]}; do
  accountName=${ACCOUNT_NAMES[$INDEX]}
  echo "Working on $profile and $accountName"
  createOrUpdateStack $profile $REGION cross-account-$accountName cross-account-role.yaml "Environment=${accountName}" "TrustedAccountId=${cicdAccountId}"
  getRoleArn $profile $REGION $accountName
  # Create Policies in CICD Account
  for key in $keys; do
    key=$(echo $key | tr -d '"')
    value=$(echo $arraVar | jq --arg key "$key" '.[$key]')
    createAssumeRolePolicies assume-role-$key-$accountName $key-$accountName $value
  done
  ((INDEX=INDEX+1))
done

# 2. Deploy the stack in CICD Account
createOrUpdateStack $CICD_PROFILE $REGION cross-account-cicd cicd-account.yaml

# 3. If $REGION is not set to us-east-1, then deploy the event routing
if [[ "$REGION" != "us-east-1" ]]; then
  ## a. Get the ARN of the default event bus for the CICD account in $REGION
  EventBus_ARN=$(aws events list-event-buses \
    --query "EventBuses[?Name == 'default'].Arn" \
    --region $REGION \
    --profile $CICD_PROFILE \
    --output text)

  ## b. Deploy cicd-account-event-routing.yaml
  createOrUpdateStack $CICD_PROFILE us-east-1 cross-account-event-routing-cicd cicd-account-event-routing.yaml CrossRegionDestinationBus=$EventBus_ARN
fi