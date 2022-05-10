#!/usr/bin/env bash

set -e
set -o pipefail

AWS_REGION=eu-west-1
AWS_PROFILE=ppa-piattaforma-notifiche-beta.FullAdmin
ENVIRONMENT=beta
PROJECT=spidhub
STACK_NAME=spidhub
PACKAGE_BUCKET=cf-templates-tu6w3i55ikf3-eu-west-1
PACKAGE_PREFIX=package/$PROJECT


aws \
  --profile "$AWS_PROFILE" \
  --region "$AWS_REGION" \
  cloudformation package \
  --template-file "./$STACK_NAME.yaml" \
  --output-template-file "./$STACK_NAME.tmp" \
  --s3-bucket "$PACKAGE_BUCKET" \
  --s3-prefix "$PACKAGE_PREFIX"

aws \
  --profile "$AWS_PROFILE" \
  --region "$AWS_REGION" \
  cloudformation deploy \
  --stack-name "$PROJECT-$ENVIRONMENT" \
  --parameter-overrides "file://environments/$ENVIRONMENT/params.json" \
  --tags "file://environments/$ENVIRONMENT/tags.json" \
  --template-file "./$STACK_NAME.tmp" \
  --capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM

rm "./$STACK_NAME.tmp"
