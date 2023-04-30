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
    Usage: $(basename "${BASH_SOURCE[0]}") [-h] [-v] -p <aws-profile-from> -P <aws-profile-to> -r <aws-region> [-w <work-dir>] [--table-name]
    [-h]                    : this help message
    [-v]                    : print commands
    -p <aws-profile-from>   : aws cli profile
    -P <aws-profile-to>     : aws cli profile
    -r <aws-region>         : aws region as eu-south-1
    [-w <work-dir>]         : folder for temporary files
    [--table-name]          : Table to be copied
EOF
  exit 1
}

parse_params() {
  # default values of variables set from params
  work_dir=$TMPDIR
  aws_profile_from=""
  aws_profile_to=""
  aws_region=""
  table_name="pn-counter"

  while :; do
    case "${1-}" in
    -h | --help) usage ;;
    -v | --verbose) set -x ;;
    -p) 
      aws_profile_from="${2-}"
      shift
      ;;
    -P) 
      aws_profile_to="${2-}"
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
  [[ -z "${aws_profile_from-}" ]] && usage
  [[ -z "${aws_profile_to-}" ]] && usage
  [[ -z "${table_name-}" ]] && usage
  return 0
}

dump_params(){
  echo ""
  echo "######      PARAMETERS      ######"
  echo "##################################"
  echo "Work directory:             ${work_dir}"
  echo "AWS region:                 ${aws_region}"
  echo "AWS profile copy from:      ${aws_profile_from}"
  echo "AWS profile copy to:        ${aws_profile_to}"
  echo "Nome tabella:               ${table_name}"
}

# START SCRIPT

parse_params "$@"
dump_params


aws --profile "$aws_profile_from" --region "$aws_region" \
        dynamodb scan \
        --table-name "$table_name" \
        --max-items 50000 \
      | jq -r '.Items | .[] | tojson' \
      | tee "$work_dir/counter_table_dump.json"

nrows=$(cat "$work_dir/counter_table_dump.json" | wc -l)
for (( n=1; n<=${nrows}; n++ )); do
  cat "$work_dir/counter_table_dump.json" | head -n $n | tail -1 > "$work_dir/put_command.json"
  
  echo "########## $table_name step $n of $nrows"
  aws --profile "$aws_profile_to" --region "$aws_region" \
      dynamodb put-item \
               --table-name "$table_name" \
               --item file://$work_dir/put_command.json
done
