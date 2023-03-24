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

echo -n "insert start time: "
read start_time

echo -n "insert end time: "
read end_time


dir=monitoring_${aws_profile}_$(date +"%d-%m-%Y")

mkdir -p $dir

echo "change work directory"

cd $dir

echo time is $start_time $end_time

echo "start export CPU  metrics for ECS"

echo "==> start export CPU  metrics for ECS"

for cpumetrics in  $(aws ${aws_command_base_args} cloudwatch list-metrics --metric-name CPUUtilization --namespace AWS/ECS  --output text | grep ServiceName | awk '{print $2",Value="$3}') ; do
aws ${aws_command_base_args} cloudwatch get-metric-statistics --metric-name CPUUtilization  --start-time $start_time --end-time $end_time --period 60 --statistics Maximum --dimensions Name=$cpumetrics Name=ClusterName,Value=pn-core-ecs-cluster --namespace AWS/ECS >> cpu_metrics_$(echo $cpumetrics  | cut -d "=" -f 2).json && echo  cpu metrics export for: $( echo $cpumetrics  | cut -d "=" -f 2); 
done

echo "==> cpu metrics done"
echo "==> start export RAM metrics for ECS"

for rammetrics in  $(aws ${aws_command_base_args} cloudwatch list-metrics --metric-name MemoryUtilization --namespace AWS/ECS   --output text | grep ServiceName | awk '{print $2",Value="$3}') ; do
aws ${aws_command_base_args} cloudwatch get-metric-statistics --metric-name MemoryUtilization  --start-time $start_time --end-time $end_time --period 60 --statistics Maximum --dimensions Name=$rammetrics Name=ClusterName,Value=pn-core-ecs-cluster --namespace AWS/ECS >> ram_metrics_$(echo $rammetrics  | cut -d "=" -f 2).json && echo  ram metrics export for: $( echo $rammetrics  | cut -d "=" -f 2);
done

echo "==> ram metrics done"
echo "==> start export OutofMemory_Error"

aws ${aws_command_base_args} cloudwatch get-metric-statistics --metric-name pn-ECSOutOfMemory  --start-time $start_time --end-time $end_time --period 60 --statistics Maximum  --namespace OutOfMemoryErrors >> oom_metrics.json ;

echo "==> OutofMemory_Error metrics done" 
echo "==> start lambda memory_utilization":

for lam_mem in  $(aws ${aws_command_base_args} cloudwatch list-metrics --metric-name memory_utilization --namespace LambdaInsights  --output text | grep DIMENSIONS | awk '{print $2",Value="$3}') ; do
aws ${aws_command_base_args} cloudwatch get-metric-statistics --metric-name memory_utilization  --start-time $start_time --end-time $end_time --period 60 --statistics Maximum --dimensions Name=$lam_mem --namespace LambdaInsights >> lambda_mem_utlizations_metrics_$(echo $lam_mem  | cut -d "=" -f 2).json && echo  lambda_memory_utilizations  metrics export for: $( echo $lam_mem  | cut -d "=" -f 2);
done

echo "==> lambda memory_utilization metrics done"
echo "==> start lambda rx_bytes  metrics"

for lam_rx in  $(aws ${aws_command_base_args} cloudwatch list-metrics --metric-name rx_bytes --namespace LambdaInsights  --output text | grep DIMENSIONS | awk '{print $2",Value="$3}') ; do
aws ${aws_command_base_args} cloudwatch get-metric-statistics --metric-name rx_bytes  --start-time $start_time --end-time $end_time --period 60 --statistics Maximum --dimensions Name=$lam_rx --namespace LambdaInsights >> lambda_rx_bytes_metrics_$(echo $lam_mem  | cut -d "=" -f 2).json && echo  lambda_rx_bytes_utilizations  metrics export for: $( echo $lam_rx  | cut -d "=" -f 2);
done

echo "==> lambda rx_bytes metrics done"
echo "==> start lambda cpu_total_time  metrics"

for lam_cputt in  $(aws ${aws_command_base_args} cloudwatch list-metrics --metric-name cpu_total_time --namespace LambdaInsights  --output text | grep DIMENSIONS | awk '{print $2",Value="$3}') ; do
aws ${aws_command_base_args} cloudwatch get-metric-statistics --metric-name cpu_total_time  --start-time $start_time --end-time $end_time --period 60 --statistics Maximum --dimensions Name=$lam_cputt --namespace LambdaInsights >> lambda_cpu_total_time_metrics_$(echo $lam_cputt  | cut -d "=" -f 2).json && echo  lambda_cpu_total_time_utilizations  metrics export for: $( echo $lam_cputt  | cut -d "=" -f 2);
done

echo "==> lambda cpu_total_time  metrics done"
echo "==> start AWS-lambda IteratorAge  metrics"

for iteage in  $(aws ${aws_command_base_args} cloudwatch list-metrics --metric-name IteratorAge --namespace AWS/Lambda  --output text | grep DIMENSIONS | awk '{print $2",Value="$3}') ; do
aws ${aws_command_base_args} cloudwatch get-metric-statistics --metric-name IteratorAge  --start-time $start_time --end-time $end_time --period 60 --statistics Maximum --dimensions Name=$iteage --namespace AWS/Lambda  >> lambda_aws_IteratorAge_$(echo $iteage  | cut -d "=" -f 2).json && echo  lambda_aws_IteratorAge metrics export for: $( echo $iteage  | cut -d "=" -f 2);
done

echo "==> AWS-lambda IteratorAge  metrics done"
echo "==> start AWS-lambda Throttles  metrics"

for lamthr in  $(aws ${aws_command_base_args} cloudwatch list-metrics --metric-name Throttles --namespace AWS/Lambda  --output text | grep DIMENSIONS | awk '{print $2",Value="$3}') ; do
aws ${aws_command_base_args} cloudwatch get-metric-statistics --metric-name Throttles  --start-time $start_time --end-time $end_time --period 60 --statistics Maximum --dimensions Name=$lamthr --namespace AWS/Lambda  >> lambda_aws_Throttles_$(echo $lamthr  | cut -d "=" -f 2).json && echo  lambda_aws_Throttles metrics export for: $( echo $lamthr  | cut -d "=" -f 2);
done

echo "==> AWS-lambda Throttles  metrics done"
echo "==> start AWS-lambda Duration  metrics"

for lamdur in  $(aws ${aws_command_base_args} cloudwatch list-metrics --metric-name Duration --namespace AWS/Lambda  --output text | grep DIMENSIONS | awk '{print $2",Value="$3}') ; do
aws ${aws_command_base_args} cloudwatch get-metric-statistics --metric-name Duration  --start-time $start_time --end-time $end_time --period 60 --statistics Maximum --dimensions Name=$lamdur --namespace AWS/Lambda  >> lambda_aws_Duration_$(echo $lamdur  | cut -d "=" -f 2).json && echo  lambda_aws_Duration metrics export for: $( echo $lamdur  | cut -d "=" -f 2);
done

echo "==> AWS-lambda Duration  metrics done"
echo "==> start AWS-lambda Invocations  metrics"

for laminv in  $(aws ${aws_command_base_args} cloudwatch list-metrics --metric-name Invocations --namespace AWS/Lambda  --output text | grep DIMENSIONS | awk '{print $2",Value="$3}') ; do
aws ${aws_command_base_args} cloudwatch get-metric-statistics --metric-name Invocations  --start-time $start_time --end-time $end_time --period 60 --statistics Maximum --dimensions Name=$laminv --namespace AWS/Lambda  >> lambda_aws_Invocations_$(echo $laminv  | cut -d "=" -f 2).json && echo  lambda_aws_Invocations metrics export for: $( echo $laminv  | cut -d "=" -f 2);
done

echo "==> AWS-lambda Invocations  metrics done"
echo "==> start AWS/SQS  metrics"

for sqsa in  $(aws ${aws_command_base_args} cloudwatch list-metrics --metric-name ApproximateAgeOfOldestMessage --namespace AWS/SQS  --output text | grep DIMENSIONS | awk '{print $2",Value="$3}') ; do
aws ${aws_command_base_args} cloudwatch get-metric-statistics --metric-name ApproximateAgeOfOldestMessage  --start-time $start_time --end-time $end_time --period 60 --statistics Maximum --dimensions Name=$sqsa --namespace AWS/SQS  >> sqs_apprx_age_oldest_$(echo $sqsa  | cut -d "=" -f 2).json && echo  sqs_apprx_age_oldest metrics export for: $( echo $sqsa  | cut -d "=" -f 2);
done

echo "==> AWS/SQS  metrics done"
echo "==> start AWS/SQS DLQ  metrics"

for sqsdlq in  $(aws ${aws_command_base_args} cloudwatch list-metrics --metric-name ApproximateNumberOfMessagesVisible --namespace AWS/SQS  --output text | grep DIMENSIONS | awk '{print $2",Value="$3}') ; do
aws ${aws_command_base_args} cloudwatch get-metric-statistics --metric-name ApproximateNumberOfMessagesVisible  --start-time $start_time --end-time $end_time --period 60 --statistics Maximum --dimensions Name=$sqsdlq --namespace AWS/SQS  >> sqs_dlq_message_visible_number_$(echo $sqsdlq  | cut -d "=" -f 2).json && echo  sqs_dlq_message_visible_number metrics export for: $( echo $sqsdlq  | cut -d "=" -f 2);
done

echo "==> AWS/SQS  DLQ metrics done"
 echo "==> start Microservice Response Time metrics"

 for mcresp in  $(aws ${aws_command_base_args} cloudwatch list-metrics --metric-name TargetResponseTime --namespace AWS/ApplicationELB   --output text | grep TargetGroup | awk '{print $2",Value="$3}') ; do
 aws ${aws_command_base_args} cloudwatch get-metric-statistics --metric-name TargetResponseTime  --start-time $start_time --end-time $end_time --period 60 --statistics Maximum --dimensions Name=$mcresp Name=LoadBalancer,Value=app/pn-in-Appli-1HXGA7HK0CJQ3/2ae27258c1ba9aff --namespace AWS/ApplicationELB >> Microservice_response_time_$(echo $mcresp  | cut -d "/" -f 2).json && echo  Microservice_response_time_metrics export for: $( echo $mcresp  | cut -d "=" -f 2);
 done

echo "==> Microservice metrics done"
echo "==> start Microservice 4xx Count Time metrics"

for mc4 in  $(aws ${aws_command_base_args} cloudwatch list-metrics --metric-name HTTPCode_Target_4XX_Count --namespace AWS/ApplicationELB   --output text | grep TargetGroup | awk '{print $2",Value="$3}') ; do
aws ${aws_command_base_args} cloudwatch get-metric-statistics --metric-name HTTPCode_Target_4XX_Count  --start-time $start_time --end-time $end_time --period 60 --statistics Maximum --dimensions Name=$mc4 Name=LoadBalancer,Value=app/pn-in-Appli-1HXGA7HK0CJQ3/2ae27258c1ba9aff --namespace  AWS/ApplicationELB >> Microservice_4xx_Count_$(echo $mc4  | cut -d "/" -f 2).json && echo  Microservice_4xx_Count metrics export for: $( echo $mc4  | cut -d "=" -f 2);
done

echo "==> Microservice 4xx Count metrics done"
echo "==> start Microservice 5xx Count Time metrics"

for mc5 in  $(aws ${aws_command_base_args} cloudwatch list-metrics --metric-name HTTPCode_Target_5XX_Count --namespace AWS/ApplicationELB   --output text | grep TargetGroup | awk '{print $2",Value="$3}') ; do
aws ${aws_command_base_args} cloudwatch get-metric-statistics --metric-name HTTPCode_Target_5XX_Count  --start-time $start_time --end-time $end_time --period 60 --statistics Maximum --dimensions Name=$mc5 Name=LoadBalancer,Value=app/pn-in-Appli-1HXGA7HK0CJQ3/2ae27258c1ba9aff --namespace  AWS/ApplicationELB>> Microservice_5xx_Count_$(echo $mc5  | cut -d "/" -f 2).json && echo  Microservice_5xx_Count metrics export for: $( echo $mc5  | cut -d "=" -f 2);
done

echo "==> Microservice 5xx Count metrics done"
echo "==> start Api-Gateway Latency metrics"

for apilat in  $(aws ${aws_command_base_args} cloudwatch list-metrics --metric-name Latency --namespace AWS/ApiGateway  --output text | grep ApiName | awk '{print $2",Value="$3}') ; do
aws ${aws_command_base_args} cloudwatch get-metric-statistics --metric-name Latency  --start-time $start_time --end-time $end_time --period 60 --statistics Maximum --dimensions Name=$apilat --namespace AWS/ApiGateway  >> api_gateway_latency_metrics_$(echo $apilat  | cut -d "=" -f 2).json && echo  api_gateway_latency_metrics metrics export for: $( echo $apilat  | cut -d "=" -f 2);
done

echo "==> Api-Gateway Latency metrics done"
echo "==> start Api-Gateway 5XXError metrics"

for api5 in  $(aws ${aws_command_base_args} cloudwatch list-metrics --metric-name 5XXError --namespace AWS/ApiGateway  --output text | grep ApiName | awk '{print $2",Value="$3}') ; do
aws ${aws_command_base_args} cloudwatch get-metric-statistics --metric-name 5XXError  --start-time $start_time --end-time $end_time --period 60 --statistics Maximum --dimensions Name=$api5 --namespace AWS/ApiGateway  >> api_5XXError_metrics_$(echo $api5  | cut -d "=" -f 2).json && echo  api_5XXError_metrics metrics export for: $( echo $api5  | cut -d "=" -f 2);
done

echo "==> Api-Gateway 5XXError metrics done"
echo "==> start Api-Gateway 4XXError metrics"

for api4 in  $(aws ${aws_command_base_args} cloudwatch list-metrics --metric-name 4XXError --namespace AWS/ApiGateway  --output text | grep ApiName | awk '{print $2",Value="$3}') ; do
aws ${aws_command_base_args} cloudwatch get-metric-statistics --metric-name 4XXError  --start-time $start_time --end-time $end_time --period 60 --statistics Maximum --dimensions Name=$api4 --namespace AWS/ApiGateway  >> api_4XXError_metrics_$(echo $api4  | cut -d "=" -f 2).json && echo  api_4XXError_metrics metrics export for: $( echo $api4  | cut -d "=" -f 2);
done

echo "==> Api-Gateway 4XXError metrics done"
echo "==> start Api-Gateway Count metrics"

for apicount in  $(aws ${aws_command_base_args} cloudwatch list-metrics --metric-name Count --namespace AWS/ApiGateway  --output text | grep ApiName | awk '{print $2",Value="$3}') ; do
aws ${aws_command_base_args} cloudwatch get-metric-statistics --metric-name Count  --start-time $start_time --end-time $end_time --period 60 --statistics Maximum --dimensions Name=$apicount --namespace AWS/ApiGateway  >> api_Count_metrics_$(echo $apicount  | cut -d "=" -f 2).json && echo  api_Count_metrics metrics export for: $( echo $apicount  | cut -d "=" -f 2);
done

echo "==> Api-Gateway Count metrics done"
echo "==> start OER SLA Violations metrics"

for sla in  $(aws ${aws_command_base_args} cloudwatch list-metrics --metric-name pn-activeSLAViolations --namespace OER  --output text | grep type | awk '{print $2",Value="$3}') ; do
aws ${aws_command_base_args} cloudwatch get-metric-statistics --metric-name pn-activeSLAViolations  --start-time $start_time --end-time $end_time --period 60 --statistics Maximum --dimensions Name=$sla --namespace AWS/ApiGateway  >> sla_violations_metrics_$(echo $sla  | cut -d "=" -f 2).json && echo  sla_violations metrics export for: $( echo $sla  | cut -d "=" -f 2);
done

echo "==> OER SLA Violations metrics done"

echo "==> ALL DONE <=="



