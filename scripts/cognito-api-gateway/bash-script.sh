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
echo "DOMAIN_NAME = $DOMAIN_NAME"

# Deploy Cognito
aws cloudformation deploy \
--stack-name cognito \
--template-file ./account-A-cognito.yaml \
--capabilities CAPABILITY_IAM \
--parameter-overrides \
    DomainName=$DOMAIN_NAME \
--profile $COGNITO_PROFILE \
--region $REGION

# Deploy API Gateway and the associated Lambda functions
CognitoARN=$(aws cloudformation describe-stacks \
--stack-name cognito \
--profile $COGNITO_PROFILE \
--region $REGION \
--query "Stacks[0].Outputs[?OutputKey=='UserPoolARN'].OutputValue" \
--output text )

CognitoClientId=$(aws cloudformation describe-stacks \
--stack-name cognito \
--profile $COGNITO_PROFILE \
--region $REGION \
--query "Stacks[0].Outputs[?OutputKey=='ClientId'].OutputValue" \
--output text)

aws cloudformation deploy \
 --stack-name api-gateway \
 --template-file ./account-B-api-gateway.yaml \
 --capabilities CAPABILITY_IAM \
 --parameter-overrides \
    CognitoUserPoolArn=$CognitoARN \
    CognitoDomain=$DOMAIN_NAME \
    CognitoClientId=$CognitoClientId \
 --profile $API_PROFILE \
 --region $REGION

 # Create and attach Lambda Layer (requests package)
response=$(aws lambda publish-layer-version \
--layer-name requests-package \
--zip-file fileb://runtime/requests.zip \
--compatible-runtimes python3.9 \
--profile $API_PROFILE \
--region $REGION)

layerARN=$(echo $response | jq -r '.LayerVersionArn')

aws lambda update-function-configuration \
--function-name api-auth \
--layers $layerARN \
--profile $API_PROFILE \
--region $REGION
