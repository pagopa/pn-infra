#! /bin/bash

if ( [ $# -ne 3 ] ) then
  echo "This script create DNS zone for a PN environment and create the delegation in parent zone pn.pagopa.it"
  echo "Usage: $0 <environment-name> <zone-profile> <parent-zone-profile> <region>"
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

scriptDir=$( dirname "$0" )

envName=$1
zoneStackName="${envName}-dnszone"
parentZoneStackName="${envName}-dnszone-delegation"

zoneProfile=$2

zoneRegion=$3
parentZoneRegion=$3


function createOrUpdateStack() {
  profile=$1
  region=$2
  stackName=$3
  templateFile=$4

  shift
  shift
  shift
  shift

  echo "Start stack ${stackName} creation or update"
  aws --profile $profile --region $region cloudformation deploy \
      --stack-name ${stackName} \
      --template-file ${scriptDir}/cnf-templates/${templateFile} \
      --parameter-override $@
}

echo "CONFIGURE ZONE"
createOrUpdateStack $zoneProfile $zoneRegion $zoneStackName dns-zone.yaml "EnvName=${envName}"

echo "List stack outputs"
outputs=$( aws --profile $zoneProfile --region $zoneRegion cloudformation describe-stacks \
    --stack-name ${stackName} )
echo $outputs

echo "Extract NameServers DNSs"
nameservers=$( echo $outputs | jq '.Stacks[0].Outputs[] | select(.OutputKey=="NameServers") | .OutputValue' | sed -e 's/"//g')
echo $nameservers | tr "," "\n"

nameserverParamValue=$( echo $nameservers | sed -e 's/,/|/g' )

echo $nameserverParamValue

