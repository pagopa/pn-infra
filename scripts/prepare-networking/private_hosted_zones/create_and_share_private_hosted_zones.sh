#!/usr/bin/env bash
    
set -Eeuo pipefail
trap cleanup SIGINT SIGTERM ERR EXIT

cleanup() {
  trap - SIGINT SIGTERM ERR EXIT
  # script cleanup here
}

script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" &>/dev/null && pwd -P)


usage() {
      cat <<EOF
    Usage: $(basename "${BASH_SOURCE[0]}") [-h] [-v] -r <aws-region> -p-<n> <aws-profile> -d-<n> <private-dns-domain> -v-<n> <vpc-id>

    [-h]                      : this help message
    [-v]                      : verbose mode
    
EOF
  exit 1
}

parse_params() {
  # default values of variables set from params
  aws_profiles=()
  aws_region="eu-south-1"
  private_domains=()
  vpc_ids=()
  
  while :; do
    case "${1-}" in
    -h | --help) usage ;;
    -v | --verbose) set -x ;;
    -r | --region ) 
      aws_region="${2-}"
      shift
      ;;
    -p-1 | --profile-1 ) 
      aws_profiles[0]="${2-}"
      shift
      ;;
    -p-2 | --profile-2 ) 
      aws_profiles[1]="${2-}"
      shift
      ;;
    -p-3 | --profile-3 ) 
      aws_profiles[2]="${2-}"
      shift
      ;;
    -d-1 | --dns-1 ) 
      private_domains[0]="${2-}"
      shift
      ;;
    -d-2 | --dns-2 ) 
      private_domains[1]="${2-}"
      shift
      ;;
    -d-3 | --dns-3 ) 
      private_domains[2]="${2-}"
      shift
      ;;
    -v-1 | --vpc-1 ) 
      vpc_ids[0]="${2-}"
      shift
      ;;
    -v-2 | --vpc-2 ) 
      vpc_ids[1]="${2-}"
      shift
      ;;
    -v-3 | --vpc-3 ) 
      vpc_ids[2]="${2-}"
      shift
      ;;
    -?*) usage ;;
    *) break ;;
    esac
    shift
  done

  args=("$@")

  number_of_accounts=${#aws_profiles[@]}

  return 0
}

dump_params(){
  echo ""
  echo "######      PARAMETERS      ######"
  echo "##################################"
  echo "Number of accounts: ${number_of_accounts}"
  for  idx in ${!aws_profiles[@]}; do
    echo "=======   Account $(( ${idx} + 1 ))   ======="
    echo " - DNS Domain: ${private_domains[$idx]}"
    echo " - VPC Id:     ${vpc_ids[$idx]}"
    echo " - Profile:    ${aws_profiles[$idx]}"
    echo " - Region:     ${aws_region}"
  done
}


# START SCRIPT

parse_params "$@"
dump_params


echo ""
echo ""
echo ""
echo "#######################################################################"
echo "###    CREATE OR UPDATE PRIVATE HOSTED ZONE USING CLOUDFORMATION    ###"
echo "#######################################################################"

for  idx in ${!aws_profiles[@]}; do
  echo ""
  echo "=== PROFILE: ${aws_profiles[$idx]}"
  echo "======================================="
  aws --profile ${aws_profiles[$idx]} --region ${aws_region} \
    cloudformation deploy \
      --stack-name init-private-dns-zone \
      --template-file ${script_dir}/cnf-templates/private-hosted-zone.yaml \
      --parameter-overrides \
        HostedZoneDomainName="${private_domains[$idx]}" \
        VPCID="${vpc_ids[$idx]}"
done



echo ""
echo ""
echo ""
echo "######################################################################"
echo "###                READ THE PRIVATE HOSTED ZONE IDS                ###"
echo "######################################################################"
private_zones_ids=()
for  idx in ${!aws_profiles[@]}; do
  echo ""
  echo "=== PROFILE: ${aws_profiles[$idx]}"
  echo "======================================="
  private_zone_id=$( aws --profile ${aws_profiles[$idx]} --region ${aws_region} \
    cloudformation describe-stacks \
      --stack-name init-private-dns-zone \
    | jq -r '.Stacks[0] | .Outputs | .[] | select(.OutputKey=="PrivateHostedZoneId") | .OutputValue' \
  )
  private_zones_ids[$idx]=${private_zone_id}
  echo " - Private Hosted Zone Id:     ${private_zones_ids[$idx]}"
done




for  idxFrom in ${!aws_profiles[@]}; do
  for  idxTo in ${!aws_profiles[@]}; do
    if ( [ "${idxFrom}" -ne "${idxTo}" ] ) then
      echo ""
      fromProfile=${aws_profiles[$idxFrom]}
      toProfile=${aws_profiles[$idxTo]}
      hosted_zone_id=${private_zones_ids[$idxFrom]}
      to_vpc_id=${vpc_ids[$idxTo]}

      echo " === Create association request ${fromProfile}  ==> ${toProfile} for zone ${hosted_zone_id} to vpc ${to_vpc_id}"
      aws --region ${aws_region} --profile ${fromProfile} \
              route53 create-vpc-association-authorization \
                      --hosted-zone-id ${hosted_zone_id} \
                      --vpc VPCRegion=${aws_region},VPCId=${to_vpc_id}
      
      echo " === Accept association request ${fromProfile}  ==> ${toProfile} for zone ${hosted_zone_id} to vpc ${to_vpc_id}"
      aws --region ${aws_region} --profile ${toProfile} \
              route53 associate-vpc-with-hosted-zone \
                      --hosted-zone-id ${hosted_zone_id} \
                      --vpc VPCRegion=${aws_region},VPCId=${to_vpc_id}
    fi
  done
done
