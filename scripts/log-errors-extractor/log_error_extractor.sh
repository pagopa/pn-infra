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
    Usage: $(basename "${BASH_SOURCE[0]}") [-h] [-v] [-p <aws-profile>] -r <aws-region>
    [-h]                      : this help message
    [-v]                      : verbose mode
    [-p <aws-profile>]        : aws cli profile (optional)
    -r <aws-region>           : aws region as eu-south-1
    
EOF
  exit 1
}

parse_params() {
  # default values of variables set from params
  project_name=pn
  work_dir=$HOME/tmp/deploy
  aws_profile=""
  aws_region=""
  env_type=""

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
    -w | --work-dir) 
      work_dir="${2-}"
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
  return 0
}

dump_params(){
  echo ""
  echo "######      PARAMETERS      ######"
  echo "##################################"
  echo "Project Name:       ${project_name}"
  echo "Work directory:     ${work_dir}"
  echo "AWS region:         ${aws_region}"
  echo "AWS profile:        ${aws_profile}"
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

echo -n "insert start time, for example insert 2H for search in two hours ago : "
read time

echo "create output directory by date and aws profile if not exists: "

dir=errors_${aws_profile}_$(date +"%d-%m-%Y")

mkdir -p $dir

echo "change work directory"

cd $dir

echo "set query variable"

searchquery=" fields @timestamp, @message, @logStream, @log, level | filter level like  /ERROR/  | sort @timestamp desc  " 

searchquerylambda=$(echo ${searchquery} |  sed  's/filter level/filter message/g' )

echo "the query that will be executed for ecs and lambda log group: "

echo $searchquery 

echo $searchquerylambda 

#ECS LOG:

for loggr in  $(aws ${aws_command_base_args} logs describe-log-groups --log-group-name-prefix /ecs | grep -i logGroupName | awk '{print $2}' | cut -d "\"" -f 2 | cut -d "\"" -f 1) ; do

#FOR TESTING ONLY:
#for loggr in  $(aws ${aws_command_base_args} logs describe-log-groups --log-group-name-prefix /ecs | grep -i logGroupName | awk '{print $2}' | cut -d "\"" -f 2 | cut -d "\"" -f 1 | grep push) ; do

aws ${aws_command_base_args} logs start-query  --log-group-name $loggr  --start-time `date -j -v-$time +%s000` --end-time `date +%s000`  --query-string "${searchquery}"  | awk '{print $2}' | cut -d "\"" -f 2 | cut -d "\"" -f 1 > query &&

aws ${aws_command_base_args} logs get-query-results --query-id $(cat query) --output text > result$(echo $loggr | sed 's/\//_/g').txt && echo $loggr has been verified ;

done

#LAMBDA LOG

for loggrlb in $(aws logs ${aws_command_base_args} describe-log-groups --log-group-name-prefix /aws/lambda | grep -i logGroupName | awk '{print $2}' | cut -d "\"" -f 2 | cut -d "\"" -f 1); do

#FOR TESTING ONLY:
#for loggrlb in $(aws ${aws_command_base_args} logs describe-log-groups --log-group-name-prefix /aws/lambda | grep -i logGroupName | awk '{print $2}' | cut -d "\"" -f 2 | cut -d "\"" -f 1 | grep -i push); do

aws ${aws_command_base_args} logs start-query  --log-group-name $loggrlb  --start-time `date -j -v-1H +%s000` --end-time `date +%s000`  --query-string "${searchquerylambda}"  | awk '{print $2}' | cut -d "\"" -f 2 | cut -d "\"" -f 1 > query &&

aws ${aws_command_base_args} logs get-query-results --query-id $(cat query) --output text > result$(echo $loggrlb | sed 's/\//_/g').txt && echo $loggrlb has been verified ;

done 

#REPORT:

echo "delete file report if already exists"

file="report.txt"

if [ -f "$file" ] ; then
    rm "$file"
fi

echo "####REPORT VIOLATIONS $(date)####" > report.txt

for rep in $(ls | grep result) ; do echo "Errors in log-group $rep : $(grep -i result $rep | grep -i message | wc -l)" >> report.txt ;

done

echo "report done, correcting syntax..."

sed -i '' 's/result//g' report.txt && sed -i '' 's/_/\//g' report.txt  && sed -i ''  's/\.txt//g' report.txt

echo "remove useless files"

rm query

echo "all done"
