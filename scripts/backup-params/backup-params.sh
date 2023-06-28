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
    Usage: $(basename "${BASH_SOURCE[0]}") [-h] [-v] [-p <profile>] [-r <region>] -f <prefix> [-s <skip-prefix>]
    [-h]                      : this help message
    [-v]                      : verbose mode
    [-p] <profile>            : aws profile
    [-r] <region>             : aws region
    [-f] <prefix>             : param prefix
    [-s] <skip-prefix>        : param skip-prefix
        
EOF
  exit 1
}

parse_params() {
  # default values of variables set from params
  aws_profile=""
  aws_region="eu-south-1"
  prefix=""
  skip_prefix="bck"

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
    -s | --skip-prefix) 
      skip_prefix="${2-}"
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
  echo "Skip Prefix         ${skip_prefix}"       
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
  param_tier=$2
#  new_param_name="$3-$1"

  if [[ "$param_name" == "/$skip_prefix"* ]]; then
    echo "Param $param_name skipped"
    return
  fi

  if [[ "$param_name" == "/"* ]]; then # if param name starts with slash just concatenate prefix and param name
    new_param_name="/$3$1"
  else
    new_param_name="/$3/$1"
  fi


  # get parameter value
  param=$(aws ${aws_command_base_args} ssm get-parameter --name ${param_name})
  param_value=$(echo $param | jq -r '.Parameter.Value')  

  echo "copy $param_name to $new_param_name"
  
  # create duplicate param
  aws ${aws_command_base_args} ssm put-parameter --type String --name $new_param_name --value "${param_value}" --tier "$param_tier" --overwrite

  echo "copied $param_name to $new_param_name"
}

echo "${parameters}" | jq -r '.Parameters[] | .Name + " " + .Tier'  \
| while read -r name tier; do
  duplicate_param $name $tier $prefix
done