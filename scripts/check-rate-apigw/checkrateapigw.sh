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
    Usage: $(basename "${BASH_SOURCE[0]}") [-h] [-v]  -e <env-type> -d <test-tax-id> -k <api-key> -t <time-curl>
    [-h]                      : this help message
    [-v]                      : verbose mode
    [-e] <env-type>           : aws env type
    [-d] <test-tax-id>        : user tax id
    [-k] <api-key>            : api key
    [-t] <time-curl>          : time between curls
EOF
  exit 1
}

parse_params() {
  # default values of variables set from params
  project_name=pn
  work_dir=$HOME/tmp/deploy
  env_type=""
  test_tax_id=""
  apy_key=""
  time_curl=""

  while :; do
    case "${1-}" in
    -h | --help) usage ;;
    -v | --verbose) set -x ;;
    -w | --work-dir) 
      work_dir="${2-}"
      shift
      ;;
    -e | --env-type) 
      env_type="${2-}"
      shift
      ;;
    -d | --test-tax-id) 
      test_tax_id="${2-}"
      shift
      ;;
    -k | --api-key) 
      api_key="${2-}"
      shift
      ;;
    -t | --time-curl) 
      time_curl="${2-}"
      shift
      ;;
    -?*) die "Unknown option: $1" ;;
    *) break ;;
    esac
    shift
  done

  args=("$@")

  # check required params and arguments
  [[ -z "${env_type}" ]] && usage
  return 0
}

dump_params(){
  echo ""
  echo "######      PARAMETERS      ######"
  echo "##################################"
  echo "Project Name:       ${project_name}"
  echo "Work directory:     ${work_dir}"
  echo "AWS env type:       ${env_type}"
  echo "Tax ID Test         ${test_tax_id}"
  echo "Api Key             ${api_key}" 
  echo "Time Curl           ${time_curl}"      
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

echo "create output directory by date and aws environment if not exists: "

dir="report_testrate_${env_type}_$(date +"%d-%m-%Y")"

mkdir -p $dir

echo "change work directory"

cd $dir

urlcurl="https://api-io."$env_type".pn.pagopa.it/delivery/notifications/received/GEZG-TQPH-TPAQ-202303-D-1"

apikey="x-api-key: $api_key"

testtaxid="x-pagopa-cx-taxid: $test_tax_id"


while true;

do 

curl  --request GET \
  --url "$urlcurl" \
  --header 'Content-Type: application/json' \
  --header "$apikey" \
  --header "$testtaxid" \
  --data '{}' >>  report.txt  && echo >> report.txt;

sleep $time_curl;

done
