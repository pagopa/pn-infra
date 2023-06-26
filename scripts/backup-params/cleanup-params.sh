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
    Usage: $(basename "${BASH_SOURCE[0]}") [-h] [-v] [-p <profile>] [-r <region>] -f <prefix>
    [-h]                      : this help message
    [-v]                      : verbose mode
    [-p] <profile>            : aws profile
    [-r] <region>             : aws region
    [-f] <prefix>             : param prefix
        
EOF
  exit 1
}

parse_params() {
  # default values of variables set from params
  aws_profile=""
  aws_region="eu-south-1"
  prefix=""

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
    -f | --prefix) 
      prefix="${2-}"
      shift
      ;;
    -?*) die "Unknown option: $1" ;;
    *) break ;;
    esac
    shift
  done

  args=("$@")

  # check required params and arguments
  [[ -z "${prefix}" ]] && usage
  return 0
}

dump_params(){
  echo ""
  echo "######      PARAMETERS      ######"
  echo "##################################"
  echo "AWS Profile         ${aws_profile}"
  echo "AWS Region          ${aws_region}" 
  echo "Prefix              ${prefix}"
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

function delete_param() {
  param_name=$1

  if [[ "$param_name" == "/$prefix"* ]]; then
    $(aws ${aws_command_base_args} ssm delete-parameter --name ${param_name})
    echo $param_name " deleted"
  else
    echo $param_name " deletion skipped"
  fi

}

echo "${parameters}" | jq -r '.Parameters[] | .Name'  \
| while read -r name; do
  delete_param $name
done