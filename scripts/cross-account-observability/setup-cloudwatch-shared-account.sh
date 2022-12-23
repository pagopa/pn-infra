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
    Usage: $(basename "${BASH_SOURCE[0]}") [-h] [-v] [-p <aws-profile>] -r <aws-region> -e <env-type> -a <monitoring-aws-accounts>

    [-h]                      : this help message
    [-v]                      : verbose mode
    [-p <aws-profile>]        : aws cli profile (optional)
    -r <aws-region>           : aws region as eu-south-1
    -e <env-type>             : one of dev / uat / svil / coll / cert / prod
    -a <monitoring-aws-accounts>      : comma separated list of monitoring AWS account ID
    
EOF
  exit 1
}

parse_params() {
  # default values of variables set from params
  project_name=pn
  aws_profile=""
  aws_region=""
  env_type=""
  monitoring_account_ids=""

  while :; do
    case "${1-}" in
    -h | --help) usage ;;
    -v | --verbose) set -x ;;
    -p | --profile) 
      aws_profile="${2-}"
      shift
      ;;
    -r | --region) 
      aws_region="${2-}"
      shift
      ;;
    -e | --env-name) 
      env_type="${2-}"
      shift
      ;;
    -a | --monitoring-aws-account) 
      monitoring_account_ids="${2-}"
      shift
      ;;
    -?*) die "Unknown option: $1" ;;
    *) break ;;
    esac
    shift
  done

  args=("$@")

  # check required params and arguments
  [[ -z "${env_type-}" ]] && usage 
  [[ -z "${monitoring_account_ids-}" ]] && usage
  [[ -z "${aws_region-}" ]] && usage
  return 0
}

dump_params(){
  echo ""
  echo "######      PARAMETERS      ######"
  echo "##################################"
  echo "Project Name:              ${project_name}"
  echo "Monitoring Account IDs:     ${monitoring_account_ids}"
  echo "Env Name:                  ${env_type}"
  echo "AWS region:                ${aws_region}"
  echo "AWS profile:               ${aws_profile}"
}


# START SCRIPT

parse_params "$@"
dump_params

echo ""
echo "=== Base AWS command parameters"
aws_command_base_args=""
if ( [ ! -z "${aws_profile}" ] ) then
  aws_command_base_args="${aws_command_base_args} --profile $aws_profile"
fi
if ( [ ! -z "${aws_region}" ] ) then
  aws_command_base_args="${aws_command_base_args} --region  $aws_region"
fi
echo ${aws_command_base_args}

aws ${aws_command_base_args} cloudformation deploy \
        --stack-name ${project_name}-cross-account-monitoring-${env_type} \
        --capabilities CAPABILITY_NAMED_IAM \
        --template-file CloudWatch-CrossAccountSharingRole-AccountList-aws.yaml \
        --parameter-overrides \
            MonitoringAccountIds=${monitoring_account_ids} \
            Policy="View-Access-for-all-services"