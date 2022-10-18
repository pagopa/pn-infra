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

# 1. Launch the stack in the Dev and HotFix environment
aws cloudformation deploy \
--stack-name cross-account-1-dev \
--template-file ./cf-templates/dev-account-1.yaml \
--capabilities CAPABILITY_NAMED_IAM \
--profile $DEV_PROFILE \
--region $REGION

aws cloudformation deploy \
--stack-name cross-account-1-hotfix \
--template-file ./cf-templates/hotfix-account-1.yaml \
--capabilities CAPABILITY_NAMED_IAM \
--profile $HOTFIX_PROFILE \
--region $REGION

# 2. Get the ARN of the AdministratorAccess and ReadOnly Access

### DEV ###
RoleReadOnlyAccessARN_DEV=$(aws cloudformation describe-stacks \
--stack-name cross-account-1-dev \
--profile $DEV_PROFILE \
--region $REGION \
--query "Stacks[0].Outputs[?OutputKey=='RoleReadOnlyAccessARN'].OutputValue" \
--output text ) 

RoleAdministratorAccessARN_DEV=$(aws cloudformation describe-stacks \
--stack-name cross-account-1-dev \
--profile $DEV_PROFILE \
--region $REGION \
--query "Stacks[0].Outputs[?OutputKey=='RoleAdministratorAccessARN'].OutputValue" \
--output text )

### HOTFIX ###
RoleReadOnlyAccessARN_HOTFIX=$(aws cloudformation describe-stacks \
--stack-name cross-account-1-hotfix \
--profile $HOTFIX_PROFILE \
--region $REGION \
--query "Stacks[0].Outputs[?OutputKey=='RoleReadOnlyAccessARN'].OutputValue" \
--output text )

RoleAdministratorAccessARN_HOTFIX=$(aws cloudformation describe-stacks \
--stack-name cross-account-1-hotfix \
--profile $HOTFIX_PROFILE \
--region $REGION \
--query "Stacks[0].Outputs[?OutputKey=='RoleAdministratorAccessARN'].OutputValue" \
--output text )

# 3. Deploy the stack in CICD Account
aws cloudformation deploy \
--stack-name cross-account-1-cicd \
--template-file ./cf-templates/cicd-account-1.yaml \
--capabilities CAPABILITY_NAMED_IAM \
--parameter-overrides \
  RoleAdministratorAccessDEV=$RoleAdministratorAccessARN_DEV \
  RoleReadOnlyAccessDEV=$RoleReadOnlyAccessARN_DEV \
  RoleAdministratorAccessHOTFIX=$RoleAdministratorAccessARN_HOTFIX \
  RoleReadOnlyAccessHOTFIX=$RoleReadOnlyAccessARN_HOTFIX \
--profile $CICD_PROFILE \
--region $REGION

# 4. Get the ARN of Lambda's execution role in the CICD account
RoleLambdaUpdateTrustPolicies_ARN=$(aws cloudformation describe-stacks \
--stack-name cross-account-1-cicd \
--profile $CICD_PROFILE \
--region $REGION \
--query "Stacks[0].Outputs[?OutputKey=='RoleLambdaUpdateTrustPoliciesOutput'].OutputValue" \
--output text)

# 5. Deploy in DEV and HOTFIX

### DEV ###
aws cloudformation deploy \
--stack-name cross-account-2-dev \
--template-file ./cf-templates/dev-account-2.yaml \
--capabilities CAPABILITY_NAMED_IAM \
--parameter-overrides \
  ExecutionRoleLambdaUpdateTrustPolicies=$RoleLambdaUpdateTrustPolicies_ARN \
  RoleReadOnlyAccessARN=$RoleReadOnlyAccessARN_DEV \
  RoleAdministratorAccessARN=$RoleAdministratorAccessARN_DEV \
--profile $DEV_PROFILE \
--region $REGION

### HOTFIX ###
aws cloudformation deploy \
--stack-name cross-account-2-hotfix \
--template-file ./cf-templates/hotfix-account-2.yaml \
--capabilities CAPABILITY_NAMED_IAM \
--parameter-overrides \
  ExecutionRoleLambdaUpdateTrustPolicies=$RoleLambdaUpdateTrustPolicies_ARN \
  RoleReadOnlyAccessARN=$RoleReadOnlyAccessARN_HOTFIX \
  RoleAdministratorAccessARN=$RoleAdministratorAccessARN_HOTFIX \
--profile $HOTFIX_PROFILE \
--region $REGION

# 6. Get the ARN of the role to update the trust policies in DEV and HOTFIX
RoleUpdateTrustPolicy_ARN_DEV=$(aws cloudformation describe-stacks \
--stack-name cross-account-2-dev \
--profile $DEV_PROFILE \
--region $REGION \
--query "Stacks[0].Outputs[?OutputKey=='RoleUpdateTrustPolicy'].OutputValue" \
--output text)

RoleUpdateTrustPolicy_ARN_HOTFIX=$(aws cloudformation describe-stacks \
--stack-name cross-account-2-hotfix \
--profile $HOTFIX_PROFILE \
--region $REGION \
--query "Stacks[0].Outputs[?OutputKey=='RoleUpdateTrustPolicy'].OutputValue" \
--output text)

# 7. Deploy CICD 2
aws cloudformation deploy \
--stack-name cross-account-2-cicd \
--template-file ./cf-templates/cicd-account-2.yaml \
--capabilities CAPABILITY_NAMED_IAM \
--parameter-overrides \
  RoleUpdateTrustPoliciesDEV=$RoleUpdateTrustPolicy_ARN_DEV \
  RoleUpdateTrustPoliciesHOTFIX=$RoleUpdateTrustPolicy_ARN_HOTFIX \
  RoleLambdaUpdateTrustPolicies=$RoleLambdaUpdateTrustPolicies_ARN \
  RoleAdministratorAccessDEV=$RoleAdministratorAccessARN_DEV \
  RoleAdministratorAccessHOTFIX=$RoleAdministratorAccessARN_HOTFIX \
  RoleReadOnlyAccessDEV=$RoleReadOnlyAccessARN_DEV \
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
  --template-file ./cf-templates/cicd-account-event-routing.yaml \
  --capabilities CAPABILITY_NAMED_IAM \
  --parameter-overrides \
    CrossRegionDestinationBus=$EventBus_ARN \
  --profile $CICD_PROFILE \
  --region us-east-1
fi 


