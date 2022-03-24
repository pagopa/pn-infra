#!/usr/bin/env bash -e

scriptDir=$( dirname "$0" )

if ( [ $# -ne 4 ] ) then
  echo "This script create a test spidhub instance"
  echo "Usage: $0 <profile> <region> <destination-url> <user-registry-api-key>"
  echo "<profile> the profile to access AWS account"
  echo "<zone>: where to deploy the spidhub istance"
  echo "<login-success-url>: redirection url after successful login"
  echo ""
  echo "This script require following executable configured in the PATH variable:"
  echo " - aws cli 2.0 "
  echo " - jq"

  if ( [ "$BASH_SOURCE" = "" ] ) then
    return 1
  else
    exit 1
  fi
fi

profile=$1
region=$2

LoginSuccessDestinationEnpoint=$3
UserRegistryApiKey=$4

EnvName="spid-hub-test"
DnsDomain="${profile}.pn.pagopa.it"
UserRegistryApiUrl="https://api.${profile}.userregistry.pagopa.it/user-registry-management/v1"
KeyName="${EnvName}-ssh-key"
StackName="${EnvName}"
KeyFileName="${KeyName}-${region}-${profile}.pem"


echo ""
echo ""
echo ""

echo "###                        PRODUCE SSH KEY                        ###"
echo "#####################################################################"

echo "# Search if key already exsists on AWS EC2"
DescribeKey=$( \
    aws --profile $profile --region $region ec2 describe-key-pairs \
        --filters Name=key-name,Values=$KeyName \
  )
echo $DescribeKey

keyExsists=$( echo $DescribeKey | jq -r '.KeyPairs | length' )
if ( [ "0" -eq "$keyExsists" ] ) then
  
  echo ""
  echo "# SSH access key do not exsists, crate it ..."
  MYKEY=$( aws --profile $profile --region $region ec2 create-key-pair \
              --key-name $KeyName \
              --output json \
              --no-cli-pager \
          )
  echo $MYKEY
  PRIVKEY=$( echo $MYKEY | sed 's/\([^",\{\}]\)$/\1\\n/g' | tr -d '\n' | jq -r .KeyMaterial )
  
  echo ""
  echo "# ... and store on AWS parameter store"
  aws --profile $profile --region $region ssm put-parameter \
      --type "SecureString" \
      --name "${KeyName}" \
      --value "$PRIVKEY" \
      --overwrite
else
  echo ""
  echo "# SSH access key already exsists retrieve from parameter store"
  PRIVKEY=$( aws --profile $profile --region $region ssm get-parameter \
      --with-decryption \
      --name "${KeyName}" \
      --query "Parameter.Value" \
      --output text )
  
fi

echo ""
echo "# Store SSH Private KEY on your filesystem in path $HOME/.spidhub_keys/${KeyFileName}"
mkdir -p $HOME/.spidhub_keys/
chmod 700 $HOME/.spidhub_keys/

echo "$PRIVKEY" > $HOME/.spidhub_keys/${KeyFileName}
chmod 600 $HOME/.spidhub_keys/${KeyFileName}


echo ""
echo ""
echo ""

echo "###                    INSTANTIATE EC2 MACHINE                    ###"
echo "#####################################################################"

echo ""
echo "# Retrieve ami-id"
# Applica i filtri per architettura e nome, poi prende la piu recente (ordine inverso per data di creazione).
AmiId=$( aws --profile $profile --region $region ec2 describe-images \
             --filters Name=architecture,Values=x86_64 "Name=name,Values=amzn2-ami-kernel-*-hvm-*-gp2" \
             --query 'reverse(sort_by(Images, &CreationDate))[0].ImageId' \
             --output text
      )
echo "# AMI-ID: ${AmiId}"

echo ""
echo "# Deploy EC2 instance"
aws --profile "$profile" --region "$region" cloudformation deploy \
    --stack-name "${StackName}" \
    --template-file ${scriptDir}/cfn-templates/vpc_with_public_ec2.yaml \
    --parameter-overrides \
      KeyName="$KeyName" \
      AmiId="${AmiId}" \
      EnvName="${EnvName}" \
      DnsZoneDomain="${DnsDomain}"


echo ""
echo ""
echo ""

echo "###                      PREPARE EC2 MACHINE                      ###"
echo "#####################################################################"
echo ""
echo "!!!! WARNING: ssh connection errors can be coused by DNS and EC2 setup delay."
echo "!!!! WARNING: you can be prompted to accept ssh host key"
echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"

SshConnectionUrl="ec2-user@${EnvName}.${DnsDomain}"
KeyPath="$HOME/.spidhub_keys/${KeyFileName}"

echo ""
echo "# Copiyng files to SSH ${SshConnectionUrl} with identity ${KeyPath}"
scp -r -i ${KeyPath} "${scriptDir}/remote-scripts/"* "${SshConnectionUrl}:~"

echo ""
echo "# Write full dns name"
ssh -i ${KeyPath} "${SshConnectionUrl}" " echo ${EnvName}.${DnsDomain} > ./full-dns-name"

echo ""
echo "# Write successfull login destination"
ssh -i ${KeyPath} "${SshConnectionUrl}" " echo ${LoginSuccessDestinationEnpoint} > ./login-success-destination-enpoint"

echo ""
echo "# Write userregistry api key"
ssh -i ${KeyPath} "${SshConnectionUrl}" " echo ${UserRegistryApiKey} > ./user-registry-api-key"

echo ""
echo "# Write userregistry api url"
ssh -i ${KeyPath} "${SshConnectionUrl}" " echo ${UserRegistryApiUrl} > ./user-registry-api-url"


echo ""
echo "### Execute install script"
ssh -i ${KeyPath} "${SshConnectionUrl}" source ./install.sh

echo ""
echo "### Execute build script"
ssh -i ${KeyPath} "${SshConnectionUrl}" source ./build.sh

echo ""
echo "### RUN"
ssh -i ${KeyPath} "${SshConnectionUrl}" source ./run.sh
