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
    Usage: $(basename "${BASH_SOURCE[0]}") [-h] [-v] [-p <aws-profile>] -r <aws-region> -s <start-time> -e <end-time> [-P <period>]
    [-h]                      : this help message
    [-v]                      : verbose mode
    [-p <aws-profile>]        : aws cli profile (optional)
    -r <aws-region>           : aws region as eu-south-1
    -s <start-time>           : aws cloudwatch get metrics start time
    -e <end-time>             : aws cloudwatch get metrics end time
    [-P <period>]             : aws cloudwatch get metrics period of sampling (optional - default=60)
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
  start_time=""
  end_time=""
  period=""

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
    -s | --start-time) 
      start_time="${2-}"
      shift
      ;;
    -e | --end-time) 
      end_time="${2-}"
      shift
      ;;
    -P | --period) 
      period="${2-}"
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
  echo "AWS cloudwatch start time:  ${start_time}"
  echo "AWS cloudwatch end time     ${end_time}"
  echo "AWS cloudwatch period       ${period}"
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

## assign default value for period if not assigned:
period="${period:=60}"

dir=monitoring_${aws_profile}_$(date +"%d-%m-%Y")

mkdir -p $dir

echo "change work directory"

cd $dir

echo  TIME interval is: $start_time   "<====>"    $end_time   &&  echo PERIOD of sampling is: $period 

echo $start_time
echo $end_time

#ARRAY STATISTICS:
statistics=(Maximum Sum)

#ARRAY METRICS LIST:
awsecs=(MemoryUtilization CPUUtilization)
lambdainsight=(memory_utilization rx_bytes cpu_total_time)
aws_lambda_max=(IteratorAge Duration)
aws_lambda_sum=(Throttles Invocations Errors)
aws_sqs_max=(ApproximateAgeOfOldestMessage)
aws_sqs_sum=(ApproximateNumberOfMessagesVisible)
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
done
for dlq in $(echo $aws_sqs | grep DLQ); do
for j in ${aws_sqs_sum[@]}; do
aws ${aws_command_base_args} cloudwatch get-metric-statistics --metric-name $j --start-time $start_time --end-time $end_time --period $period --statistics ${statistics[1]} --dimensions Name=$dlq --namespace AWS/SQS  >> aws_sqs_dlq_$(echo $j  | cut -d "=" -f 2)_$(echo $dlq  | cut -d "=" -f 2).json && echo  aws_sqs_dql export for: $( echo $j  | cut -d "=" -f 2)_$(echo $dlq  | cut -d "=" -f 2); done
done
done
echo "==> AWS/SQS metrics done"

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

echo "==> ALL DONE <=="