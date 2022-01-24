#! /bin/bash

zoneRegion="eu-central-1"
cloudFrontRegion="us-east-1"

# COMPLETE LIST OF dev & test SUBDOMAINS
environments="dev uat"

# COMPLETE CERTIFICATES LIST (we have a certificate for every public exposed https endpoint)
# - Certificate used by CloudFront must be in "us-east-1" region
certificateSubdomainsAndRegion="api#${zoneRegion} webapi#${zoneRegion} portale-pa#${cloudFrontRegion} portale#${cloudFrontRegion} www#${cloudFrontRegion}"


if ( [ $# -ne 2 ] ) then
  echo "This script create DNS zones for ($environments) PN environments in region ${zoneRegion}"
  echo "Usage: $0 <zone-profile> <parent-zone-profile>"
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


zoneProfile=$1
parentZoneProfile=$2


for envName in $( echo $environments )
do
  echo "### DNS FOR ENVIRONMENT: ${envName}"
  source "${scriptDir}/create-or-update-one-aws-dns-zone.sh" $envName $zoneProfile $parentZoneProfile $zoneRegion

  for certificateSubdomainNameAndRegion in $( echo $certificateSubdomainsAndRegion )
  do
    certificateSubdomainName=$( echo "$certificateSubdomainNameAndRegion" | sed -e 's/#.*//' )
    certificateRegion=$( echo "$certificateSubdomainNameAndRegion" | sed -e 's/.*#//' )
    echo " ---- Creating certificate ${certificateSubdomainName} for environment ${envName} --- "
    source "${scriptDir}/create-or-renew-one-certificate.sh" $certificateSubdomainName "${envName}.pn.pagopa.it" $zoneProfile $certificateRegion $zoneRegion
    echo " ------------------------------------------------------------------------------------ "
  done
  echo "#####################################"
done


