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
    Usage: $(basename "${BASH_SOURCE[0]}") [-h] [-v]  -p <profile> -r <region> -s <suffix>
    [-h]                      : this help message
    [-v]                      : verbose mode
    [-p] <profile>            : aws profile
    [-r] <region>             : aws region
    [-s] <suffix>             : param suffix
EOF
  exit 1
}

parse_params() {
  # default values of variables set from params
  project_name=pn
  work_dir=$HOME/tmp/deploy
  aws_profile=""
  aws_region=""
  suffix=""

  while :; do
    case "${1-}" in
    -h | --help) usage ;;
    -v | --verbose) set -x ;;
    -w | --work-dir) 
      work_dir="${2-}"
      shift
      ;;
    -p | --profile) 
      aws_profile="${2-}"
      shift
      ;;
    -r | --region) 
      aws_region="${2-}"
      shift
      ;;
    -s | --suffix) 
      suffix="${2-}"
      shift
      ;;
    -?*) die "Unknown option: $1" ;;
    *) break ;;
    esac
    shift
  done

  args=("$@")

  # check required params and arguments
  [[ -z "${suffix}" ]] && usage
  return 0
}

dump_params(){
  echo ""
  echo "######      PARAMETERS      ######"
  echo "##################################"
  echo "Project Name:       ${project_name}"
  echo "Work directory:     ${work_dir}"
  echo "AWS Profile         ${aws_profile}"
  echo "AWS Region          ${aws_region}" 
  echo "Suffix              ${suffix}"      
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


parameters=$(aws ${aws_command_base_args} ssm describe-parameters)

function duplicate_param() {
  param_name=$1
  new_param_name="$1_$2"
  # get parameter value

  # create duplicate param
}

for row in $(echo "${parameters}" | jq -r '.Parameters[].Name' ); do
  duplicate_param $row $suffix
done