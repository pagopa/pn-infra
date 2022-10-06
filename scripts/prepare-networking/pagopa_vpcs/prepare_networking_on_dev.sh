#!/usr/bin/env bash

# More details at https://pagopa.atlassian.net/browse/PN-1773

set -Eeuo pipefail
trap cleanup SIGINT SIGTERM ERR EXIT

cleanup() {
  trap - SIGINT SIGTERM ERR EXIT
  # script cleanup here
}

script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" &>/dev/null && pwd -P)


usage() {
      cat <<EOF
    Usage: $(basename "${BASH_SOURCE[0]}") [-h] [-v] -r <aws-region> -p-core <aws-profile> -p-helpdesk <aws-profile> -p-confidential <aws-profile> -p-spidhub <aws-profile>

    [-h]                      : this help message
    [-v]                      : verbose mode
    
EOF
  exit 1
}

names=(core helpdesk confidential spidhub)

parse_params() {
  # default values of variables set from params
  aws_profiles=()
  aws_region="eu-south-1"
  igress_num=(4 2 1)
  egress_num=(16 8 7)
  private_num=(32 64 65)
  
  while :; do
    case "${1-}" in
    -h | --help) usage ;;
    -v | --verbose) set -x ;;
    -r | --region ) 
      aws_region="${2-}"
      shift
      ;;
    -p-core ) 
      aws_profiles[0]="${2-}"
      shift
      ;;
    -p-helpdesk ) 
      aws_profiles[1]="${2-}"
      shift
      ;;
    -p-confidential ) 
      aws_profiles[2]="${2-}"
      shift
      ;;
    -p-spidhub )
      aws_profiles[3]="${2-}"
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

get_account_number(){
  account_ids=()
  for  idx in ${!aws_profiles[@]}; do
    account_id=$( aws --profile ${aws_profiles[$idx]} --region ${aws_region} \
    sts get-caller-identity --query "Account" --output text  
  )
  account_ids[$idx]=${account_id}
  done
}

dump_params(){
  echo ""
  echo "######      PARAMETERS      ######"
  echo "##################################"
  echo "Number of accounts: ${number_of_accounts}"
  get_account_number
  for  idx in ${!aws_profiles[@]}; do
    echo "=======   Account ${names[$idx]}   ======="
    echo " - Profile:    ${aws_profiles[$idx]}"
    echo " - Account Id: ${account_ids[$idx]}"
    echo " - Region:     ${aws_region}"
    echo " - Igress:     ${igress_num[$idx]}"
    echo " - Egress:     ${egress_num[$idx]}"
    echo " - Private:    ${private_num[$idx]}"
  done
}


# START SCRIPT

parse_params "$@"
dump_params


echo ""
echo ""
echo ""
echo "#######################################################################"
echo "###                CREATE NETWORKING IN EACH ACCOUNT                ###"
echo "#######################################################################"
vpc_ids=()
for  idx in ${!aws_profiles[@]}; do
  echo ""
  echo ""
  echo "=== AWS ACCOUNT NAME: ${names[$idx]}"
  echo "======================================="
  aws --profile ${aws_profiles[$idx]} --region ${aws_region} \
    cloudformation deploy \
      --stack-name MultiVpc \
      --template-file ${script_dir}/cnf-templates/multi-vpcs.yaml \
      --parameter-overrides \
        VpcEgressName="Egress" \
        VpcEgressNumber="${egress_num[$idx]}" \
        VpcIngressName="Ingress" \
        VpcIngressNumber="${igress_num[$idx]}" \
        VpcPrivateName="Private" \
        VpcPrivateNumber="${private_num[$idx]}"
  
  vpc_id=$( aws --profile ${aws_profiles[$idx]} --region ${aws_region} \
    cloudformation describe-stacks \
      --stack-name MultiVpc \
    | jq -r '.Stacks[0] | .Outputs | .[] | select(.OutputKey=="PrivateVPCId") | .OutputValue' \
  )
  vpc_ids[$idx]=${vpc_id}

  echo ""
  echo " - Private VPC Id:          ${vpc_ids[$idx]}"
 
done




echo ""
echo ""
echo ""
echo "#######################################################################"
echo "###                             PEERING                             ###"
echo "#######################################################################"

function makeOnePeering() {
  fromIdx=$1
  toIdx=$2

  PeerAccountId=${account_ids[$toIdx]}
  PeerVpcId=${vpc_ids[$toIdx]}
  VpcId=${vpc_ids[$fromIdx]}
  #TransitGatewayRouteTableId=${transit_gateway_route_table_ids[$fromIdx]}
  #DestinationVPCCidr="10.${private_num[$toIdx]}.0.0/16"

  echo ""
  echo ""
  echo "=== ${names[$fromIdx]} ==> ${names[$toIdx]}"
  echo "=========================================================="
  echo " - Source AWS CLI Profile:: ${aws_profiles[$fromIdx]}"
  echo " - Destination Account Id: ${PeerAccountId}"
  echo " - From VPC: ${VpcId}"
  echo " - To VPC: ${PeerVpcId}"
  #echo " - Transit Gateway Routing Table: ${TransitGatewayRouteTableId}"
  #echo " - Destination Cidr: ${DestinationVPCCidr}"
  request_id=$( aws --profile ${aws_profiles[$fromIdx]} --region ${aws_region} \
    ec2 create-vpc-peering-connection \
      --peer-owner-id $PeerAccountId \
      --peer-vpc-id $PeerVpcId \
      --vpc-id $VpcId \
      --peer-region $aws_region \
    | jq -r '.VpcPeeringConnection.VpcPeeringConnectionId' )
  echo " - Vpc Peering request Id: ${request_id}"
  echo " = Accept the VPC peering"
  aws --profile ${aws_profiles[$toIdx]} --region ${aws_region} \
    ec2 accept-vpc-peering-connection --vpc-peering-connection-id ${request_id}
  
  echo ""
  echo "List and update source routing tables"
  
  sourceRoutingTablesIds=$( aws --profile ${aws_profiles[$fromIdx]} --region ${aws_region} \
    ec2 describe-route-tables --filters "Name=vpc-id,Values=${VpcId}" \
    | jq -r '.RouteTables | .[] | .RouteTableId' )
  
  for tableId in ${sourceRoutingTablesIds} ; do
    cidr="10.${private_num[$toIdx]}.0.0/16"
    
    echo "Add route $cidr to $tableId"
    aws --profile ${aws_profiles[$fromIdx]} --region ${aws_region} \
        ec2 create-route --route-table-id ${tableId} \
            --destination-cidr-block $cidr \
            --vpc-peering-connection-id ${request_id} || echo "Already exists"
  done


  echo ""
  echo "List and update destination routing tables"
  
  destinationRoutingTablesIds=$( aws --profile ${aws_profiles[$toIdx]} --region ${aws_region} \
    ec2 describe-route-tables --filters "Name=vpc-id,Values=${PeerVpcId}" \
    | jq -r '.RouteTables | .[] | .RouteTableId' )
  
  for tableId in ${destinationRoutingTablesIds} ; do
    cidr="10.${private_num[$fromIdx]}.0.0/16"
    
    echo "Add route $cidr to $tableId"
    aws --profile ${aws_profiles[$toIdx]} --region ${aws_region} \
        ec2 create-route --route-table-id ${tableId} \
            --destination-cidr-block $cidr \
            --vpc-peering-connection-id ${request_id} || echo "Already exists"
  done
}


makeOnePeering 0 1
makeOnePeering 0 2
makeOnePeering 1 2