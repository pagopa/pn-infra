#! /bin/bash

if ( [ $# -ne 4 ] ) then
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
parentZoneProfile=$3

zoneRegion=$4
parentZoneRegion=$4


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


echo "CONFIGURE DELEGATION"
if ( [ ! "$envName" = "prod" ] ) then
  nameserverParamValue=$( echo $nameservers | sed -e 's/,/|/g' )
  createOrUpdateStack $parentZoneProfile $parentZoneRegion $parentZoneStackName zone-delegation-recordset.yaml \
          "EnvName=${envName}" "\"NameServers=${nameserverParamValue}\""
else
  echo " ### delegation of PRODUCTION DNS ZONE needs pull request, see engineering space on confluence"
  echo $outputs > /tmp/dns-pagopa-it-path-proposal.txt

  echo "# Subscripion PROD-PiattaformaNotifiche, pn.pagopa.it \n "\
       'resource "azurerm_dns_ns_record" "pn_pagopa_it_ns" { \n'\
       '  name                = "pn"\n'\
       '  zone_name           = azurerm_dns_zone.pagopa-it.name\n'\
       '  resource_group_name = azurerm_resource_group.rg-prod.name\n'\
       '  records = [' > /tmp/dns-pagopa-it-path-proposal.txt
  echo "$nameserverParamValue" | tr "|" "\n" | sed -e 's/^/    "/' | sed -e 's/$/.",/'\
       >> /tmp/dns-pagopa-it-path-proposal.txt

  echo '  ]\n'\
       '  ttl  = var.DEFAULT_TTL_SEC\n'\
       '  tags = var.tags\n'\
       '}' >> /tmp/dns-pagopa-it-path-proposal.txt
fi

