#! /bin/bash -e
# Script to create image repository and pull image for amazon/aws-otel-collector
# Run once in CI/CD profile

CICD_PROFILE=cicd
AWS_REGION=eu-central-1

SOURCE_IMAGE=amazon/aws-otel-collector:latest
REPOSITORY=aws-otel-collector ## ECR repository to host the container image - needs to be created before run this script
IMAGE=$REPOSITORY:latest
CICD_ACCOUNT=$(aws sts get-caller-identity --profile $CICD_PROFILE --query 'Account')
TAG=latest

echo "Creating repo ${REPOSITORY} on account ${CICD_ACCOUNT}"
# Create repository
aws ecr describe-repositories --repository-names ${REPOSITORY} --profile $CICD_PROFILE || aws ecr create-repository --repository-name ${REPOSITORY} --profile $CICD_PROFILE

# pull source image
docker pull amazon/aws-otel-collector:latest

# docker login
aws ecr get-login-password --region $AWS_REGION --profile $CICD_PROFILE | docker login --username AWS --password-stdin $CICD_ACCOUNT.dkr.ecr.$AWS_REGION.amazonaws.com

# Remote Repository
REMOTE_REPOSITORY=$CICD_ACCOUNT.dkr.ecr.$AWS_REGION.amazonaws.com/$REPOSITORY:$TAG

# docker tag.
docker tag $SOURCE_IMAGE $REMOTE_REPOSITORY

# docker push
docker push $REMOTE_REPOSITORY