#!/bin/bash

# 0. Set the variables 
for ARGUMENT in "$@"
do
   KEY=$(echo $ARGUMENT | cut -f1 -d=)

   KEY_LENGTH=${#KEY}
   VALUE="${ARGUMENT:$KEY_LENGTH+1}"

   export "$KEY"="$VALUE"
done

echo "REGION = $REGION"
echo "CICD_PROFILE = $CICD_PROFILE"
echo "DEV_PROFILE = $DEV_PROFILE"
echo "HOTFIX_PROFILE = $HOTFIX_PROFILE"

# Get the CICD Account ID


cicdAccount=$(aws sts get-caller-identity \
--query "Account" \
--output text \
--profile $CICD_PROFILE)

scriptDir=$( dirname "$0" )

echo here

# 1. Launch the stack in the environment
function createOrUpdateStack() {
  profile=$1
  region=$2
  stackName=$3
  templateFile=$4
  tagKeyAdmin=$5
  tagValueAdmin=$6
  tagKeyReadOnly=$7
  tagValueReadOnly=$8


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
        TrustedAccountId=$cicdAccount \
        TagKeyReadOnly=$tagKeyAdmin \
        TagValueReadOnly=$tagValueAdmin \
        TagKeyAdminAccess=$tagKeyReadOnly \
        TagValueAdminAccess=$tagValueReadOnly
}

echo "Deploy Dev"
createOrUpdateStack $DEV_PROFILE $REGION cross-account-$DEV_PROFILE cross-account-role.yaml "TagKeyAdminAccess=pn-admin" "TagValueAdminAccess=true" "TagKeyReadOnly=pn-read-only" "TagValueReadOnly=true"

echo "Deploy Hotfix"
createOrUpdateStack $HOTFIX_PROFILE $REGION cross-account-$HOTFIX_PROFILE cross-account-role.yaml "TagKeyAdminAccess=pn-admin" "TagValueAdminAccess=true" "TagKeyReadOnly=pn-read-only" "TagValueReadOnly=true"

# 2. Get the ARN of the AdministratorAccess and ReadOnly Access

### DEV ###
RoleReadOnlyAccessARN_DEV=$(aws cloudformation describe-stacks \
--stack-name cross-account-${DEV_PROFILE} \
--profile $DEV_PROFILE \
--region $REGION \
--query "Stacks[0].Outputs[?OutputKey=='RoleReadOnlyAccessARN'].OutputValue" \
--output text ) 

RoleAdministratorAccessARN_DEV=$(aws cloudformation describe-stacks \
--stack-name cross-account-${DEV_PROFILE} \
--profile $DEV_PROFILE \
--region $REGION \
--query "Stacks[0].Outputs[?OutputKey=='RoleAdministratorAccessARN'].OutputValue" \
--output text )

## HOTFIX ###
RoleReadOnlyAccessARN_HOTFIX=$(aws cloudformation describe-stacks \
--stack-name cross-account-${HOTFIX_PROFILE} \
--profile $HOTFIX_PROFILE \
--region $REGION \
--query "Stacks[0].Outputs[?OutputKey=='RoleReadOnlyAccessARN'].OutputValue" \
--output text )

RoleAdministratorAccessARN_HOTFIX=$(aws cloudformation describe-stacks \
--stack-name cross-account-${HOTFIX_PROFILE} \
--profile $HOTFIX_PROFILE \
--region $REGION \
--query "Stacks[0].Outputs[?OutputKey=='RoleAdministratorAccessARN'].OutputValue" \
--output text )

# 3. Deploy the stack in CICD Account
aws cloudformation deploy \
--stack-name cross-account-1-cicd \
--template-file ./cnf-templates/cicd-account-1.yaml \
--capabilities CAPABILITY_NAMED_IAM \
--parameter-overrides \
  RoleAdministratorAccessDEV=$RoleAdministratorAccessARN_DEV \
  RoleReadOnlyAccessDEV=$RoleReadOnlyAccessARN_DEV \
  RoleAdministratorAccessHOTFIX=$RoleAdministratorAccessARN_HOTFIX \
  RoleReadOnlyAccessHOTFIX=$RoleReadOnlyAccessARN_HOTFIX \
--profile $CICD_PROFILE \
--region $REGION

# 8. If $REGION is not set to us-east-1, then deploy the event routing 
if [[ "$REGION" != "us-east-1" ]]
then 
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
