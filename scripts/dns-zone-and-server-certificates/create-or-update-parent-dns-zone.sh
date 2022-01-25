#! /bin/bash

zoneRegion="eu-central-1"
cloudFrontRegion="us-east-1"

# COMPLETE CERTIFICATES LIST (we have a certificate for every public exposed https endpoint)
# - Certificate used by CloudFront must be in "us-east-1" region
certificateSubdomainsAndRegion="api#${zoneRegion} webapi#${zoneRegion} portale-pa#${cloudFrontRegion} portale#${cloudFrontRegion}"


if ( [ $# -ne 1 ] ) then
  echo "This script create DNS zone for PROD PN environments in region ${zoneRegion}"
  echo "Usage: $0 <zone-profile>"
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


source "${scriptDir}/create-or-update-one-aws-dns-zone.sh" prod $zoneProfile "unused" $zoneRegion

for certificateSubdomainNameAndRegion in $( echo $certificateSubdomainsAndRegion )
do
  certificateSubdomainName=$( echo "$certificateSubdomainNameAndRegion" | sed -e 's/#.*//' )
  certificateRegion=$( echo "$certificateSubdomainNameAndRegion" | sed -e 's/.*#//' )
  echo " ---- Creating certificate ${certificateSubdomainName} for environment ${envName} --- "
  source "${scriptDir}/create-or-renew-one-certificate.sh" $certificateSubdomainName "pn.pagopa.it" $zoneProfile $certificateRegion $zoneRegion
  echo " ------------------------------------------------------------------------------------ "
done

echo " ###### PULL REQUEST FILE SAVED WITH PATH '/tmp/dns-pagopa-it-path-proposal.txt'"
echo " Content:"
cat /tmp/dns-pagopa-it-path-proposal.txt