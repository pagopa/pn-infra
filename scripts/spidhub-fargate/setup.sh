#!/usr/bin/env bash

AWS_REGION=eu-west-1
AWS_PROFILE=ppa-piattaforma-notifiche-beta.FullAdmin
ENVIRONMENT=dev
PROJECT=spidhub
STACK_NAME=spidhub
PACKAGE_BUCKET=cf-templates-tu6w3i55ikf3-eu-west-1
PACKAGE_PREFIX=package/$PROJECT


aws \
  --profile "$AWS_PROFILE" \
  --region "$AWS_REGION" \
  secretsmanager describe-secret \
  --secret-id $PROJECT-$ENVIRONMENT-hub-login \
  > /dev/null 2> /dev/null

if test $? -ne 0; then
  mkdir -p "./environments/$ENVIRONMENT/certs"

  openssl req -nodes -new -x509 -sha256 -days 365 -newkey rsa:2048 \
    -subj "/C=IT/ST=State/L=City/O=Acme Inc. /OU=IT Department/CN=hub-spid-login-ms" \
    -keyout "./environments/$ENVIRONMENT/certs/key.pem" \
    -out "./environments/$ENVIRONMENT/certs/cert.pem"

  mkdir -p "./environments/$ENVIRONMENT/jwt"

  openssl genrsa -out "./environments/$ENVIRONMENT/jwt/jwt_rsa_key.pem" 2048
  openssl rsa -in "./environments/$ENVIRONMENT/jwt/jwt_rsa_key.pem" \
    -outform PEM -pubout -out "./environments/$ENVIRONMENT/jwt/jwt_rsa_public.pem"

  UserRegistryApiKey=$(tr -d '\n' < "./environments/$ENVIRONMENT/UserRegistryApiKey.tmp")
  MakecertPrivate=$( sed -e 's/$/\\n/' "./environments/$ENVIRONMENT/certs/key.pem" | tr -d '\n' | sed -e 's/\\n$//')
  MakecertPublic=$( sed -e 's/$/\\n/' "./environments/$ENVIRONMENT/certs/cert.pem" | tr -d '\n' | sed -e 's/\\n$//' )
  JwtTokenPrivateKey=$( sed -e 's/$/\\n/' "./environments/$ENVIRONMENT/jwt/jwt_rsa_key.pem" | tr -d '\n' | sed -e 's/\\n$//' )
  Jwks=$(docker run -i --rm danedmunds/pem-to-jwk:latest --jwks-out < "./environments/$ENVIRONMENT/jwt/jwt_rsa_public.pem")
  Kid=$(echo "$Jwks" | jq -r '.keys[0].kid')

  sed -i '' "/^JWT_TOKEN_KID=/s/=.*/=$Kid/" "./environments/$ENVIRONMENT/storage/config/hub-login/v1/.env"

  SecretString=$(echo "{\"MakecertPrivate\":\"$MakecertPrivate\",\"MakecertPublic\":\"$MakecertPublic\",\"JwtTokenPrivateKey\":\"$JwtTokenPrivateKey\",\"UserRegistryApiKey\":\"$UserRegistryApiKey\"}" | jq --arg v "$Jwks" '. + {"Jwks":$v}')

  aws \
    --profile "$AWS_PROFILE" \
    --region "$AWS_REGION" \
    secretsmanager create-secret \
    --name $PROJECT-$ENVIRONMENT-hub-login \
    --secret-string "$SecretString"

fi

aws \
  --profile "$AWS_PROFILE" \
  --region "$AWS_REGION" \
  cloudformation deploy \
  --template-file "./stacks/storage.yaml" \
  --stack-name "$PROJECT-$ENVIRONMENT-storage" \
  --parameter-overrides Project=$PROJECT Environment=$ENVIRONMENT \
  --tags Project=$PROJECT Environment=$ENVIRONMENT \
  --no-fail-on-empty-changeset

aws \
  --profile "$AWS_PROFILE" \
  --region "$AWS_REGION" \
  s3 sync \
  ./environments/$ENVIRONMENT/storage/ \
  s3://$PROJECT-$ENVIRONMENT-$AWS_REGION/ \
  --delete

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
  --tags Project=$PROJECT Environment=$ENVIRONMENT \
  --template-file "./$STACK_NAME.tmp" \
  --capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM CAPABILITY_AUTO_EXPAND \
  --no-fail-on-empty-changeset

rm "./$STACK_NAME.tmp"
