#!/usr/bin/env bash
    
set -Eeuo pipefail
trap cleanup SIGINT SIGTERM ERR EXIT

cleanup() {
  trap - SIGINT SIGTERM ERR EXIT
  # script cleanup here
}

scriptDir=$(cd "$(dirname "${BASH_SOURCE[0]}")" &>/dev/null && pwd -P)


usage() {
      cat <<EOF
    Usage: $(basename "${BASH_SOURCE[0]}") [-h] [-v] -r <aws-region> -e <env-type> -p <aws-profile> -P <parent-zone-aws-profile> -l <login-zone-profile>

    [-h]                      : this help message
    [-v]                      : verbose mode

    [-r <aws-region>]
    -e <env-type>                   nome dell'ambiente (e della zona dns)
    -p <aws-profile>                profilo AWS per accedere all'account pn-core
    -P <parent-zone-aws-profile>    profilo aws per accedere all'account che contiene la zona pn.pagopa.it (pn_uat)
    -l <login-zone-profile>         profilo AWS per l'account di spidhub login

    This script require following executable configured in the PATH variable:
     - aws cli 2.0 
     - jq
EOF
  exit 1
}

parse_params() {
  # default values of variables set from params
  zoneProfile=""
  parentZoneProfile=""
  envName=""
  zoneRegion="eu-south-1"
  cloudFrontRegion="us-east-1"

  while :; do
    case "${1-}" in
    -h | --help) usage ;;
    -v | --verbose) set -x ;;
    -r | --region ) 
      zoneRegion="${2-}"
      shift
      ;;
    -e | --env-name ) 
      envName="${2-}"
      shift
      ;;
    -p | --zone-profile ) 
      zoneProfile="${2-}"
      shift
      ;;
    -P | --parent-zone-profile ) 
      parentZoneProfile="${2-}"
      shift
      ;;
    -l | --login-zone-profile )
      loginZoneProfile="${2-}"
      shift
      ;;
    -?*) usage ;;
    *) break ;;
    esac
    shift
  done

  # check required params and arguments
  [[ -z "${zoneProfile-}" ]] && usage 
  [[ -z "${parentZoneProfile-}" ]] && usage
  [[ -z "${loginZoneProfile-}" ]] && usage
  [[ -z "${envName-}" ]] && usage

  args=("$@")

  # COMPLETE CERTIFICATES LIST (we have a certificate for every public exposed https endpoint)
  # - Certificate used by CloudFront must be in "us-east-1" region
  certificateSubdomainsAndRegion="api#${zoneRegion} webapi#${zoneRegion} portale-pa#${cloudFrontRegion} portale#${cloudFrontRegion} portale-login#${cloudFrontRegion} www#${cloudFrontRegion} api-io#${zoneRegion}"
  

  return 0
}

dump_params(){
  echo ""
  echo "######      PARAMETERS      ######"
  echo "##################################"
  echo "AWS Region:          ${zoneRegion}"
  echo "Env name:            ${envName}"
  echo "Zone Profile:        ${zoneProfile}"
  echo "Parent Zone Profile: ${parentZoneProfile}"
  echo "SPID Zone Profile:   ${loginZoneProfile}"
}


# START SCRIPT

parse_params "$@"
dump_params


echo ""
echo ""
echo ""
echo "#######################################################################"
echo "###                   CREATE OR UPDATE PUBLIC DNS                   ###"
echo "#######################################################################"

echo "### DNS FOR ENVIRONMENT: ${envName} with profile ${zoneProfile}"
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
echo ""



echo "### CREATE CHILD ZONE FOR SPIDHUB"
aws --profile $loginZoneProfile --region $zoneRegion cloudformation deploy \
      --stack-name "${envName}-dnszone-spid" \
      --template-file ${scriptDir}/cnf-templates/spid-dns-zone.yaml \
      --parameter-override "EnvName=${envName}"

echo "List stack outputs"
outputs=$( aws --profile $loginZoneProfile --region $zoneRegion cloudformation describe-stacks \
    --stack-name "${envName}-dnszone-spid" )
echo $outputs

echo "Extract NameServers DNSs"
nameservers=$( echo $outputs | jq '.Stacks[0].Outputs[] | select(.OutputKey=="NameServers") | .OutputValue' | sed -e 's/"//g')
echo $nameservers | tr "," "\n"

nameserverParamValue=$( echo $nameservers | sed -e 's/,/|/g' )

echo "### DELEGATE CHILD ZONE FOR SPIDHUB"
aws --profile $zoneProfile --region $zoneRegion cloudformation deploy \
    --stack-name "${envName}-dnszone-spid-delegation" \
    --template-file ${scriptDir}/cnf-templates/zone-delegation-recordset.yaml \
    --parameter-override \
      "EnvName=spid" \
      "BaseDnsDomain=${envName}.pn.pagopa.it" \
      "NameServers=${nameserverParamValue}"




