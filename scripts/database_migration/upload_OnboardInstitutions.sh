#!/usr/bin/env bash -e


#set -Eeuo pipefail
#trap cleanup SIGINT SIGTERM ERR EXIT

cleanup() {
  trap - SIGINT SIGTERM ERR EXIT
  # script cleanup here
  echo "SIGINT SIGTERM ERR EXIT"
}

script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" &>/dev/null && pwd -P)


usage() {
      cat <<EOF
    Usage: $(basename "${BASH_SOURCE[0]}") [-h] [-v] -p <aws-profile> -r <aws-region> -e <env-name> [-w <work-dir>] [--table-name]
    [-h]                    : this help message
    [-v]                    : print commands
    -p <aws-profile>        : aws cli profile
    -r <aws-region>         : aws region as eu-south-1
    -e <env-name>           : environment name, used to choose file name
    [-w <work-dir>]         : folder for temporary files
    [--table-name]          : Table to be copied
EOF
  exit 1
}

parse_params() {
  # default values of variables set from params
  work_dir=$TMPDIR
  aws_profile=""
  aws_region=""
  env_name=""
  table_name="pn-OnboardInstitutions"

  while :; do
    case "${1-}" in
    -h | --help) usage ;;
    -v | --verbose) set -x ;;
    -p) 
      aws_profile="${2-}"
      shift
      ;;
    -r | --region) 
      aws_region="${2-}"
      shift
      ;;
    -w | --work-dir) 
      work_dir="${2-}"
      shift
      ;;
    -e) 
      env_name="${2-}"
      shift
      ;;
    --table-name)
      table_name="${2-}"
      shift
      ;;
    -?*) die "Unknown option: $1" ;;
    *) break ;;
    esac
    shift
  done

  args=("$@")

  # check required params and arguments
  [[ -z "${aws_region-}" ]] && usage
  [[ -z "${aws_profile-}" ]] && usage
  [[ -z "${table_name-}" ]] && usage
  [[ -z "${env_name-}" ]] && usage
  return 0
}

dump_params(){
  echo ""
  echo "######      PARAMETERS      ######"
  echo "##################################"
  echo "Work directory:             ${work_dir}"
  echo "AWS region:                 ${aws_region}"
  echo "AWS profile:                ${aws_profile}"
  echo "Environment Name:           ${env_name}"
  echo "Nome tabella:               ${table_name}"
}

# START SCRIPT

parse_params "$@"
dump_params

echo ""
echo ""
echo "===                          LOAD pn-OnboardInstitutions                          ==="
echo "====================================================================================="

file_name="OnboardInstitutions_${env_name}.json"

echo "Load file $file_name into table $table_name of account $aws_profile"

nrows=$(cat "$file_name" | wc -l)
for (( n=1; n<=${nrows}; n++ )); do
  cat "$file_name" | head -n $n | tail -1 \
      | jq -r ' . | with_entries( select( .value != null ) ) | tojson' \
      > "$work_dir/put_command.json"
  
  echo "########## $table_name step $n of $nrows"
  aws --profile "$aws_profile" --region "$aws_region" \
      dynamodb put-item \
               --table-name "$table_name" \
               --item file://$work_dir/put_command.json
done
