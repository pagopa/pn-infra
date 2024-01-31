#! /bin/bash -e
# Script to create image repository and pull image for amazon/aws-otel-collector
# Run once in CI/CD profile

CICD_PROFILE=cicd
AWS_REGION=eu-central-1
TAG=v1.32.0
REPOSITORY=aws-otel-agent-injector ## ECR repository to host the container image - needs to be created before run this script
IMAGE=$REPOSITORY:$TAG
CICD_ACCOUNT=$(aws sts get-caller-identity --profile $CICD_PROFILE --query 'Account' | jq -r .)


echo "Creating repo ${REPOSITORY} on account ${CICD_ACCOUNT}"

# build source image
docker build -t $IMAGE --build-arg version=$TAG .

# docker login
aws ecr get-login-password --region $AWS_REGION --profile $CICD_PROFILE | docker login --username AWS --password-stdin $CICD_ACCOUNT.dkr.ecr.$AWS_REGION.amazonaws.com

# Remote Repository
REMOTE_REPOSITORY=$CICD_ACCOUNT.dkr.ecr.$AWS_REGION.amazonaws.com/$REPOSITORY:$TAG

# docker tag.
docker tag $IMAGE $REMOTE_REPOSITORY

# docker push
docker push $REMOTE_REPOSITORY