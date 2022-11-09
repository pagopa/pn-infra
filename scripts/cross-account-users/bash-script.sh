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
IFS=',' read -r -a arrDevProfiles <<< "$DEV_PROFILE"
DEV_PROFILE=${arrDevProfiles[@]}
echo "DEV_PROFILE = $DEV_PROFILE"

## Receives a list of profiles to deploy the cross account stacks in for example HOTFIX_PROFILE=profile1,profile2
## String converted to Bash Array
IFS=',' read -r -a arrHotfixProfiles <<< "$HOTFIX_PROFILE"
HOTFIX_PROFILE=${arrHotfixProfiles[@]}
echo "HOTFIX_PROFILE = $HOTFIX_PROFILE"

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

  # Global variables
  arraVar=$(aws cloudformation describe-stacks \
    --stack-name cross-account-$profile \
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

# 1.a Launch the stack for each Dev Profile
for profile in ${DEV_PROFILE[@]}; do
  createOrUpdateStack $profile $REGION cross-account-$profile cross-account-role.yaml "Environment=${profile}" "TrustedAccountId=${cicdAccountId}"
  getRoleArn $profile $REGION
  # Create Policies in CICD Account
  for key in $keys; do
    key=$(echo $key | tr -d '"')
    value=$(echo $arraVar | jq --arg key "$key" '.[$key]')
    createAssumeRolePolicies assume-role-$key-$profile $key-$profile $value
  done
done

# 1.b Launch the stacks for each Hotfix Profile
for profile in ${HOTFIX_PROFILE[@]}; do
  createOrUpdateStack $profile $REGION cross-account-$profile cross-account-role.yaml "Environment=${profile}" "TrustedAccountId=${cicdAccountId}"
  getRoleArn $profile $REGION
  # Create Policies in CICD Account
  for key in $keys; do
    key=$(echo $key | tr -d '"')
    value=$(echo $arraVar | jq --arg key "$key" '.[$key]')
    createAssumeRolePolicies assume-role-$key-$profile $key-$profile $value
  done
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