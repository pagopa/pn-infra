#! /bin/bash

assumed_role="arn:aws:iam::558518206506:role/ProvaCiCdRole-CiCdRole-1UBTLAMIMM27Z"

external_id=$1
env_name=Prova
env_number=1

target_profile=staging
cicd_profile=cicd
region=eu-south-1


echo "I am ..."
aws sts get-caller-identity --profile ${cicd_profile}

echo " ... assume role ${assumed_role} ..."
newRoleOutput=$(aws sts assume-role --role-arn "${assumed_role}" \
    --external-id "${external_id}" \
    --role-session-name "personal-mvit-update" \
    --profile ${cicd_profile})
#echo ${newRoleOutput} | tr "," "\n"

export AWS_ACCESS_KEY_ID=$(echo ${newRoleOutput} | tr "," "\n" | grep AccessKeyId | sed -e 's/.*": "//' | sed -e 's/".*//')
export AWS_SECRET_ACCESS_KEY=$(echo ${newRoleOutput} | tr "," "\n" | grep SecretAccessKey | sed -e 's/.*": "//' | sed -e 's/".*//')
export AWS_SESSION_TOKEN=$(echo ${newRoleOutput} | tr "," "\n" | grep SessionToken | sed -e 's/.*": "//' | sed -e 's/".*//')

env | grep AWS

echo " ... now I am ..."
aws sts get-caller-identity


echo "### Create environment ###"
aws cloudformation create-stack --stack-name "${env_name}Vpc" \
    --template-body "file://vpc.cfn.yaml"  \
    --region ${region} \
    --profile cicd_staging \
    --parameters "ParameterKey=EnvName,ParameterValue=${env_name}" \
                 "ParameterKey=EnvNumber,ParameterValue=${env_number}"



