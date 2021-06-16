#! /bin/bash

env_name=Prova
external_id=$1

target_profile=staging
cicd_profile=cicd
region=eu-south-1


echo "### Get CI/CD account id"
cicd_account=$( aws sts get-caller-identity --profile ${cicd_profile} \
         | grep Account | sed -e 's/.*": "//' | sed -e 's/".*//' )

echo "### Update cross account role in target account ###"
aws sts get-caller-identity --profile ${target_profile}
aws cloudformation update-stack --stack-name "${env_name}CiCdRole" \
    --template-body "file://target_account_crossaccount_role.yaml"  \
    --capabilities CAPABILITY_IAM  \
    --profile ${target_profile} \
    --region ${region} \
    --parameters "ParameterKey=EnvName,ParameterValue=${env_name}" \
                 "ParameterKey=ExternalId,ParameterValue=${external_id}" \
                 "ParameterKey=CiCdAccount,ParameterValue=${cicd_account}"

echo "### ... wait ... ###"
aws cloudformation wait stack-create-complete --stack-name "${env_name}CiCdRole" \
    --region ${region} \
    --profile ${target_profile} 
echo "### ... DONE!!  ###"
echo "###  Cross account role in target account ###"
target_role=$(aws cloudformation describe-stacks --stack-name "${env_name}CiCdRole" \
        --region ${region} --profile ${target_profile} \
        | grep "OutputValue" | sed -e 's/.*": "//' | sed -e 's/".*//')
echo "== ARN: ${target_role}"
echo "== ExternalId: ${external_id}"
echo ""
echo ""
echo ""

echo "### Give the ability to assume role in target account ###"
aws sts get-caller-identity --profile ${cicd_profile}
aws cloudformation create-stack --stack-name "${env_name}CiCdGroup" \
    --template-body "file://cicd_account_assume_role.yaml"  \
    --capabilities CAPABILITY_NAMED_IAM  \
    --profile ${cicd_profile} \
    --region ${region} \
    --parameters "ParameterKey=EnvName,ParameterValue=${env_name}" \
                 "ParameterKey=TargetRole,ParameterValue=${target_role}"
echo "### ... wait ... ###"
aws cloudformation wait stack-create-complete --stack-name "${env_name}CiCdGroup" \
    --region ${region} \
    --profile ${cicd_profile} 
echo "### ... DONE!!  ###"



