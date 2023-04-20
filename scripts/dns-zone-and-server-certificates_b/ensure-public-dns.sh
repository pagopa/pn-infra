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
    Usage: $(basename "${BASH_SOURCE[0]}") [-h] [-v] -r <aws-region> -e <env-type> -p <aws-profile> -l <login-zone-profile> 
    [-h]                      : this help message
    [-v]                      : verbose mode
    [-r <aws-region>]
    -e <env-type>                   nome dell'ambiente (e della zona dns)
    -p <aws-profile>                profilo AWS per accedere all'account pn-core
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
  [[ -z "${loginZoneProfile-}" ]] && usage
  [[ -z "${envName-}" ]] && usage

  args=("$@")


  

  return 0
}

dump_params(){
  echo ""
  echo "######      PARAMETERS      ######"
  echo "##################################"
  echo "AWS Region:          ${zoneRegion}"
  echo "Env name:            ${envName}"
  echo "Zone Profile:        ${zoneProfile}"
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
source "${scriptDir}/create-or-update-one-aws-dns-zone.sh" $envName $zoneProfile $zoneRegion
echo "#####################################"
echo ""
echo ""
echo ""
echo ""
echo ""
echo ""


echo "### CREATE CHILD ZONE FOR SPIDHUB"
echo "#####################################"
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

echo ""
echo ""
echo "### DELEGATE CHILD ZONE FOR SPIDHUB"
aws --profile $zoneProfile --region $zoneRegion cloudformation deploy \
    --stack-name "${envName}-dnszone-spid-delegation" \
    --template-file ${scriptDir}/cnf-templates/zone-delegation-recordset.yaml \
    --parameter-override \
      "EnvName=spid" \
      "BaseDnsDomain=${envName}.notifichedigitali.it" \
      "NameServers=${nameserverParamValue}"

echo ""
echo ""
echo ""
echo ""
echo ""
