#! /bin/bash -e
# Script to create image repository and pull image for amazon/aws-otel-collector
# Run once in CI/CD profile

CICD_PROFILE=cicd
AWS_REGION=eu-central-1
TAG=0.11.0
IMAGE_NAME=testcontainers/ryuk
REPOSITORY=testcontainers/ryuk ## ECR repository to host the container image 
IMAGE=$REPOSITORY:$TAG
CICD_ACCOUNT=$(aws sts get-caller-identity --profile $CICD_PROFILE --query 'Account' | jq -r .) 

echo "Creating repo ${REPOSITORY} on account ${CICD_ACCOUNT}"

# docker login
aws ecr get-login-password --region $AWS_REGION --profile $CICD_PROFILE | docker login --username AWS --password-stdin $CICD_ACCOUNT.dkr.ecr.$AWS_REGION.amazonaws.com

# Remote Repository
REMOTE_REPOSITORY=$CICD_ACCOUNT.dkr.ecr.$AWS_REGION.amazonaws.com/$REPOSITORY:$TAG

# docker tag.
docker tag ${IMAGE_NAME}:${TAG} $REMOTE_REPOSITORY

# docker push
docker push $REMOTE_REPOSITORY