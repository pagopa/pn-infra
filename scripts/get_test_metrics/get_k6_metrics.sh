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
    Usage: $(basename "${BASH_SOURCE[0]}") [-h] [-v] [-p <aws-profile>] -r <aws-region>  [-P <period>] -c <aws-profile-confinfo> -f <k6-run-file>
    [-h]                        : this help message
    [-v]                        : verbose mode
    [-p <aws-profile>]          : aws cli profile (optional)
    -r <aws-region>             : aws region as eu-south-1
    [-P <period>]               : aws cloudwatch get metrics period of sampling (optional - default=60)
    -c <aws-profile-confinfo>   : aws cli profile for confinfo account
    -f <k6-run-file>            : local path of k6 run file with all parameters
EOF
  exit 1
}

parse_params() {
  # default values of variables set from params
  project_name=pn
  work_dir=$HOME/tmp/deploy
  aws_profile=""
  aws_region=""
  period=""
  aws_confinfo=""
  k6_run_file=""

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
    -P | --period) 
      period="${2-}"
      shift
      ;;
    -c | --profile-confinfo) 
      aws_confinfo="${2-}"
      shift
      ;;
    -f | --file) 
      k6_run_file="${2-}"
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
  echo "Project Name:               ${project_name}"
  echo "Work directory:             ${work_dir}"
  echo "AWS region:                 ${aws_region}"
  echo "AWS profile:                ${aws_profile}"
  echo "AWS cloudwatch period       ${period}"
  echo "AWS confidential profile:   ${aws_confinfo}"
  echo "K6 local run file:          ${k6_run_file}"
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
echo ""
echo "=== Base AWS command parameters for confinfo"
aws_command_base_args_confinfo=""
if ( [ ! -z "${aws_confinfo}" ] ) then
  aws_command_base_args_confinfo="${aws_command_base_args_confinfo} --profile $aws_confinfo"
fi
if ( [ ! -z "${aws_region}" ] ) then
  aws_command_base_args_confinfo="${aws_command_base_args_confinfo} --region  $aws_region"
fi
echo ${aws_command_base_args_confinfo}
echo ""

echo "purge DLQ queue for core account"
for i in $(aws ${aws_command_base_args} sqs list-queues  --output text | grep DLQ | awk '{print $2}'); do
aws ${aws_command_base_args} sqs purge-queue  --queue-url $i  ; echo "queue DLQ $i purged";
done 
echo "purge DLQ for core account completed"

echo "purge DLQ queue for confinfo account"
for i in $(aws ${aws_command_base_args_confinfo} sqs list-queues  --output text | grep DLQ | awk '{print $2}'); do
aws ${aws_command_base_args_confinfo} sqs purge-queue --queue-url $i ; echo "queue DLQ $i purged";
done
echo "purge DLQ for confinfo account completed"

echo "launch k6 test...."

echo "remove repo pn-load-test if exist:"

rm -rf pn-load-test

echo "clone repo pn-load-test"

git clone https://github.com/pagopa/pn-load-test.git

echo "create directory for k6 test"

dir=monitoring_$(date '+%Y-%m-%d-%s')

mkdir -p $dir

echo "change work directory"

cd $dir


source "$k6_run_file"

echo "k6 test is is over.... start collection of metrics:"

## assign default value for period if not assigned:

echo "start script"

period="${period:=60}"

echo "take start_time and end_time from k6 output"

start_time=$(head -1 http-output.json | jq | grep time | sed -E 's/"time": "//g' | sed -E 's/"//g' | sed -E 's/ //g' | sed -E 's/,//g' )
end_time=$(tail -1 http-output.json | jq | grep time | sed -E 's/"time": "//g' | sed -E 's/"//g' | sed -E 's/ //g' )


echo  TIME interval is: $start_time   "<====>"    $end_time   &&  echo PERIOD of sampling is: $period 

#ARRAY STATISTICS:
statistics=(Maximum Sum)

#ARRAY METRICS LIST:
awsecs=(MemoryUtilization CPUUtilization)
lambdainsight=(memory_utilization rx_bytes cpu_total_time)
aws_lambda_max=(IteratorAge Duration)
aws_lambda_sum=(Throttles Invocations Errors)
aws_sqs_max=(ApproximateAgeOfOldestMessage)
aws_sqs_sum=(ApproximateNumberOfMessagesVisible NumberOfMessagesSent NumberOfMessagesReceived)
msvc_max=(TargetResponseTime)
msvc_sum=(HTTPCode_Target_4XX_Count HTTPCode_Target_5XX_Count RequestCount)
api_gw_max=(Latency  Count )
api_gw_sum=(5XXError 4XXError )
wf_nf=(pn-activeSlaViolations)

echo "==> start export ECS metrics"
for i in ${awsecs[@]}; do
for ecsmetrics in  $(aws ${aws_command_base_args} cloudwatch list-metrics --metric-name $i --namespace AWS/ECS  --output text | grep ServiceName | awk '{print $2",Value="$3}') ; do
aws ${aws_command_base_args} cloudwatch get-metric-statistics --metric-name $i --start-time $start_time --end-time $end_time --period $period --statistics ${statistics[0]}  --dimensions Name=$ecsmetrics Name=ClusterName,Value=pn-core-ecs-cluster --namespace AWS/ECS >> ecs_$(echo $i  | cut -d "=" -f 2)_$(echo $ecsmetrics  | cut -d "=" -f 2).json && echo  ecs export for: $( echo $i  | cut -d "=" -f 2)_$(echo $ecsmetrics  | cut -d "=" -f 2);
done
done
echo "==> ECS metrics done"

echo "==> start export ECS metrics for Confidential Account"
for i in ${awsecs[@]}; do
for ecsmetrics in  $(aws ${aws_command_base_args_confinfo} cloudwatch list-metrics --metric-name $i --namespace AWS/ECS  --output text | grep ServiceName | awk '{print $2",Value="$3}') ; do
aws ${aws_command_base_args} cloudwatch get-metric-statistics --metric-name $i --start-time $start_time --end-time $end_time --period $period --statistics ${statistics[0]}  --dimensions Name=$ecsmetrics Name=ClusterName,Value=pn-confidential-ecs-cluster --namespace AWS/ECS >> ecs_$(echo $i  | cut -d "=" -f 2)_$(echo $ecsmetrics  | cut -d "=" -f 2).json && echo  ecs export for: $( echo $i  | cut -d "=" -f 2)_$(echo $ecsmetrics  | cut -d "=" -f 2);
done
done
echo "==> ECS metrics for Confidential Account done"

echo "==> start export OutofMemory_Error"
aws ${aws_command_base_args} cloudwatch get-metric-statistics --metric-name pn-ECSOutOfMemory  --start-time $start_time --end-time $end_time --period $period --statistics ${statistics[1]}  --namespace OutOfMemoryErrors >> oom_metrics.json && echo  "OutofMemory_error export done";
echo "==> OutofMemory_Error metrics done" 

echo "==> start export Lambda_Insights metrics":
for i in ${lambdainsight[@]}; do
for lambdametrics in  $(aws ${aws_command_base_args} cloudwatch list-metrics --metric-name $i --namespace LambdaInsights  --output text | grep DIMENSIONS | awk '{print $2",Value="$3}' | sort | uniq -c | awk '{print $2}') ; do
aws ${aws_command_base_args} cloudwatch get-metric-statistics --metric-name $i --start-time $start_time --end-time $end_time --period $period --statistics ${statistics[0]} --dimensions Name=$lambdametrics --namespace LambdaInsights  >> lambda_insights_$(echo $i  | cut -d "=" -f 2)_$(echo $lambdametrics  | cut -d "=" -f 2).json && echo  Lambda_Insights export for: $( echo $i  | cut -d "=" -f 2)_$(echo $lambdametrics  | cut -d "=" -f 2);
done
done
echo "==> Lambda_Insights metrics done"


echo "==> start export AWS/Lambda metrics":
for awslambdametrics in  $(aws ${aws_command_base_args} cloudwatch list-metrics  --namespace AWS/Lambda  --output text | grep FunctionName | awk '{print $2",Value="$3}' | sort | uniq -c | awk '{print $2}' ) ; do
for i in ${aws_lambda_max[@]}; do
aws ${aws_command_base_args} cloudwatch get-metric-statistics --metric-name $i --start-time $start_time --end-time $end_time --period $period --statistics ${statistics[0]} --dimensions Name=$awslambdametrics --namespace AWS/Lambda  >> aws_lambda_$(echo $i  | cut -d "=" -f 2)_$(echo $awslambdametrics  | cut -d "=" -f 2).json && echo  aws_lambda export for: $( echo $i  | cut -d "=" -f 2)_$(echo $awslambdametrics  | cut -d "=" -f 2); done
for j in ${aws_lambda_sum[@]}; do
aws ${aws_command_base_args} cloudwatch get-metric-statistics --metric-name $j --start-time $start_time --end-time $end_time --period $period --statistics ${statistics[1]} --dimensions Name=$awslambdametrics --namespace AWS/Lambda  >> aws_lambda_$(echo $j  | cut -d "=" -f 2)_$(echo $awslambdametrics  | cut -d "=" -f 2).json && echo  aws_lambda export for: $( echo $j  | cut -d "=" -f 2)_$(echo $awslambdametrics  | cut -d "=" -f 2); done
done
echo "==> AWS/Lambda metrics done"

echo "==> start export AWS/SQS metrics":
for aws_sqs in  $(aws ${aws_command_base_args} cloudwatch list-metrics  --namespace AWS/SQS  --output text | grep QueueName | awk '{print $2",Value="$3}' | sort | uniq -c | awk '{print $2}' ) ; do
for not_dlq in $(echo $aws_sqs | grep -v DLQ); do
for i in ${aws_sqs_max[@]}; do
aws ${aws_command_base_args} cloudwatch get-metric-statistics --metric-name $i --start-time $start_time --end-time $end_time --period $period --statistics ${statistics[0]} --dimensions Name=$not_dlq --namespace AWS/SQS  >> aws_sqs_$(echo $i  | cut -d "=" -f 2)_$(echo $not_dlq  | cut -d "=" -f 2).json && echo  aws_sqs export for: $( echo $i  | cut -d "=" -f 2)_$(echo $not_dlq  | cut -d "=" -f 2); done
for k in ${aws_sqs_sum[@]}; do
aws ${aws_command_base_args} cloudwatch get-metric-statistics --metric-name $k --start-time $start_time --end-time $end_time --period $period --statistics ${statistics[1]} --dimensions Name=$not_dlq --namespace AWS/SQS  >> aws_sqs_$(echo $k  | cut -d "=" -f 2)_$(echo $not_dlq  | cut -d "=" -f 2).json && echo  aws_sqs export for: $( echo $k  | cut -d "=" -f 2)_$(echo $not_dlq  | cut -d "=" -f 2); done
done
for dlq in $(echo $aws_sqs | grep DLQ); do
for j in ${aws_sqs_sum[0]}; do
aws ${aws_command_base_args} cloudwatch get-metric-statistics --metric-name $j --start-time $start_time --end-time $end_time --period $period --statistics ${statistics[1]} --dimensions Name=$dlq --namespace AWS/SQS  >> aws_sqs_dlq_$(echo $j  | cut -d "=" -f 2)_$(echo $dlq  | cut -d "=" -f 2).json && echo  aws_sqs_dql export for: $( echo $j  | cut -d "=" -f 2)_$(echo $dlq  | cut -d "=" -f 2); done
done
done
echo "==> AWS/SQS metrics done"

echo "==> start export AWS/SQS metrics for confidentail account":
for aws_sqs in  $(aws ${aws_command_base_args_confinfo} cloudwatch list-metrics  --namespace AWS/SQS  --output text | grep QueueName | awk '{print $2",Value="$3}' | sort | uniq -c | awk '{print $2}' ) ; do
for not_dlq in $(echo $aws_sqs | grep -v DLQ); do
for i in ${aws_sqs_max[@]}; do
aws ${aws_command_base_args_confinfo} cloudwatch get-metric-statistics --metric-name $i --start-time $start_time --end-time $end_time --period $period --statistics ${statistics[0]} --dimensions Name=$not_dlq --namespace AWS/SQS  >> aws_sqs_$(echo $i  | cut -d "=" -f 2)_$(echo $not_dlq  | cut -d "=" -f 2).json && echo  aws_sqs export for: $( echo $i  | cut -d "=" -f 2)_$(echo $not_dlq  | cut -d "=" -f 2); done
for k in ${aws_sqs_sum[@]}; do
aws ${aws_command_base_args_confinfo} cloudwatch get-metric-statistics --metric-name $k --start-time $start_time --end-time $end_time --period $period --statistics ${statistics[1]} --dimensions Name=$not_dlq --namespace AWS/SQS  >> aws_sqs_$(echo $k  | cut -d "=" -f 2)_$(echo $not_dlq  | cut -d "=" -f 2).json && echo  aws_sqs export for: $( echo $k  | cut -d "=" -f 2)_$(echo $not_dlq  | cut -d "=" -f 2); done
done
for dlq in $(echo $aws_sqs | grep DLQ); do
for j in ${aws_sqs_sum[0]}; do
aws ${aws_command_base_args_confinfo} cloudwatch get-metric-statistics --metric-name $j --start-time $start_time --end-time $end_time --period $period --statistics ${statistics[1]} --dimensions Name=$dlq --namespace AWS/SQS  >> aws_sqs_dlq_$(echo $j  | cut -d "=" -f 2)_$(echo $dlq  | cut -d "=" -f 2).json && echo  aws_sqs_dlq export for: $( echo $j  | cut -d "=" -f 2)_$(echo $dlq  | cut -d "=" -f 2); done
done
done
echo "==> AWS/SQS metrics for confidentail account done"

echo "==> start export AWS/ApplicationELB metrics":
for mscv_metrics in  $(aws ${aws_command_base_args} cloudwatch list-metrics  --namespace AWS/ApplicationELB  --output text | grep TargetGroup | awk '{print $2",Value="$3}' | sort | uniq -c | awk '{print $2}' ) ; do
for i in ${msvc_max[@]}; do
aws ${aws_command_base_args} cloudwatch get-metric-statistics --metric-name $i --start-time $start_time --end-time $end_time --period $period --statistics ${statistics[0]} --dimensions Name=$mscv_metrics Name=LoadBalancer,Value=app/pn-in-Appli-1HXGA7HK0CJQ3/2ae27258c1ba9aff --namespace AWS/ApplicationELB  >> microservice_$(echo $i  | cut -d "/" -f 2)_$(echo $mscv_metrics  | cut -d "/" -f 2).json && echo  microservice export for: $( echo $i  | cut -d "/" -f 2)_$(echo $mscv_metrics  | cut -d "/" -f 2); done
for j in ${msvc_sum[@]}; do
aws ${aws_command_base_args} cloudwatch get-metric-statistics --metric-name $j --start-time $start_time --end-time $end_time --period $period --statistics ${statistics[1]} --dimensions Name=$mscv_metrics Name=LoadBalancer,Value=app/pn-in-Appli-1HXGA7HK0CJQ3/2ae27258c1ba9aff --namespace AWS/ApplicationELB  >> microservice_$(echo $j  | cut -d "/" -f 2)_$(echo $mscv_metrics  | cut -d "/" -f 2).json && echo  microservice export for: $( echo $j  | cut -d "/" -f 2)_$(echo $mscv_metrics  | cut -d "/" -f 2); done
done
echo "==> AWS/ApplicationELB metrics done"

echo "==> start export AWS/ApiGateway metrics":
for apigw in  $(aws ${aws_command_base_args} cloudwatch list-metrics  --namespace AWS/ApiGateway  --output text | grep ApiName | awk '{print $2",Value="$3}' | sort | uniq -c | awk '{print $2}' ) ; do
for i in ${api_gw_max[@]}; do
aws ${aws_command_base_args} cloudwatch get-metric-statistics --metric-name $i --start-time $start_time --end-time $end_time --period $period --statistics ${statistics[0]} --dimensions Name=$apigw  --namespace AWS/ApiGateway  >> api_gw_$(echo $i  | cut -d "/" -f 2)_$(echo $apigw  | cut -d "=" -f 2).json && echo  api_gw export for: $( echo $i  | cut -d "/" -f 2)_$(echo $apigw  | cut -d "/" -f 2); done
for j in ${api_gw_sum[@]}; do
aws ${aws_command_base_args} cloudwatch get-metric-statistics --metric-name $j --start-time $start_time --end-time $end_time --period $period --statistics ${statistics[1]} --dimensions Name=$apigw  --namespace AWS/ApiGateway  >> api_gw_$(echo $j  | cut -d "/" -f 2)_$(echo $apigw  | cut -d "=" -f 2).json && echo  api_gw export for: $( echo $j  | cut -d "/" -f 2)_$(echo $apigw  | cut -d "/" -f 2); done
done
echo "==> AWS/ApiGateway metrics done"

echo "==> start OER SLA Violations metrics"
for i in ${wf_nf[@]}; do
for sla in  $(aws ${aws_command_base_args} cloudwatch list-metrics --metric-name pn-activeSLAViolations --namespace OER  --output text | grep type | awk '{print $2",Value="$3}' | sort | uniq -c | awk '{print $2}') ; do
aws ${aws_command_base_args} cloudwatch get-metric-statistics --metric-name $i  --start-time $start_time --end-time $end_time --period 60 --statistics ${statistics[1]} --dimensions Name=$sla --namespace AWS/ApiGateway  >> sla_violations_metrics_$(echo $i  | cut -d "=" -f 2)_$(echo $sla  | cut -d "=" -f 2).json && echo  sla_violations metrics export for: $( echo $sla  | cut -d "=" -f 2); done
done
echo "==> OER SLA Violations metrics done"

echo "==> starting aws x-ray analisys:"

 if [[ $(ls | grep http-output.json) ]]; then
     echo "there is http-output.json file, creating directory" ;
     mkdir -p monitoring_xray ;
     echo "filtering http-output.json file" ;
     cat http-output.json| jq | grep -v gzip > http_filtered-output.json ;
     cat http_filtered-output.json | jq  -r  '.msg'  | grep -E "HTTP/2.0|X-Amzn-Requestid|X-Amzn-Trace-Id" > monitoring_xray/monitoring_xray_to_search.txt  ; cd monitoring_xray ;
     echo "==> converting timestamp in epoch time:" ;
     startepoch=$(date -j -f "%Y-%m-%dT%H:%M:%S" "${start_time%.*}+0000" +%s) ;
     endepoch=$(date -j -f "%Y-%m-%dT%H:%M:%S" "${end_time%.*}+0000" +%s) ;
     echo  TIME interval is: $startepoch  "<====>"    $endepoch ;
     echo starting get-trace-summaries from AWS X-RAY: ;
     aws ${aws_command_base_args} xray get-trace-summaries --start-time $startepoch --end-time $end_time > monitoring_xray.json ;

#### VERIFICA ID X-RAY 1 AD 1, AL MOMENTO NON PRATICABILE, TROPPI ID, RACCOLOGO SOLO DATI ########
#     echo "export json from AWS Xray:"
#     for traceid in $(cat monitoring_xray_search.txt | grep X-Amzn-Trace-Id   | sed -E 's/X-Amzn-Trace-Id: Root=//g') ; do  
#     aws ${aws_command_base_args} xray batch-get-traces --trace-ids $traceid > $traceid.json ; 
#     echo "export json from AWS Xray for TraceID: $traceid " ;
#     done
     cd .. ;
     echo get-trace-summaries from AWS X-RAY finished
#     echo "export json from AWS Xray done"
 else
     echo "no json files found, nothing to do"
 fi
echo "==> preparing for tarball"
echo "creating tarball"
echo "remove http-output.json"
rm http-output.json ;
tar cvzf "$(date '+%Y-%m-%d-%s').tar.gz"  * ; 
echo "tarball created"
echo "==> ALL DONE <=="

