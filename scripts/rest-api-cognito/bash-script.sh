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
echo "COGNITO_PROFILE = $COGNITO_PROFILE"
echo "API_PROFILE = $API_PROFILE"
echo "COGNITO_USERPOOL_NAME = $COGNITO_USERPOOL_NAME"
echo "NLB_ARN" = $NLB_ARN
echo "API_URI" = $API_URI

# Deploy Cognito
function deployCognito() {
  local UserPoolName=$1

  echo "Deploying Cognito User and Identity Pool"
  aws cloudformation deploy \
  --stack-name cognito-A \
  --template-file ./account-A-cognito.yaml \
  --capabilities CAPABILITY_IAM \
  --parameter-overrides \
      CognitoUserPoolName=$UserPoolName \
  --profile $COGNITO_PROFILE \
  --region $REGION
}

function getUserPoolId() {
  local USERPOOL_NAME=$1
  echo $(aws cognito-idp list-user-pools --max-results 20 --profile $COGNITO_PROFILE --query "UserPools[?Name=='$COGNITO_USERPOOL_NAME'].Id" --output text)
}

function getUserPoolArn() {
  USER_POOL_ID=$(getUserPoolId $COGNITO_USERPOOL_NAME)
  echo $(aws cognito-idp describe-user-pool --user-pool-id $USER_POOL_ID --profile $COGNITO_PROFILE --query "UserPool.Arn" --output text)
}

  # Deploy API Gateway and the associated Lambda functions
function deployApiGateway() {
  USER_POOL_ARN=$(getUserPoolArn)
  local NLBArn=$1
  local URI=$2

  if [[ ! -z $USER_POOL_ARN ]]; then
    echo "Deploying API Gateway"
    aws cloudformation deploy \
    --stack-name api-gateway-B \
    --template-file ./account-B-api-gateway.yaml \
    --capabilities CAPABILITY_IAM \
    --parameter-overrides \
        CognitoUserPoolArn=$USER_POOL_ARN \
        NLBArn=$NLBArn \
        APIURI=$URI \
    --profile $API_PROFILE \
    --region $REGION
  fi
}

# Start Script
deployCognito $COGNITO_USERPOOL_NAME
deployApiGateway $NLB_ARN $API_URI