import json
import boto3
import os
import urllib.parse

sns_client = boto3.client('sns')
logs_client = boto3.client('logs')
cloud_watch_client = boto3.client('cloudwatch')
ssm_client = boto3.client('ssm')
my_session = boto3.session.Session()

def lambda_handler(event, context):
    print(json.dumps(event, indent=4))
    my_region = my_session.region_name
    print(my_region)
    for record in event['Records']:
        payload = record["body"]
        result = json.loads(payload)
        metric_name = result["detail"]["configuration"]["metrics"][0]["metricStat"]["metric"]["name"]
        metric_namespace = result["detail"]["configuration"]["metrics"][0]["metricStat"]["metric"]["namespace"]
        log_group_response_name = get_log_group_name(metric_name, metric_namespace)
        print(log_group_response_name)
        if log_group_response_name != "NotFound":
            log_stream_response_id = get_log_stream_id(log_group_response_name)
            metric_alarm_details_response = get_alarm_details(metric_name, metric_namespace)
            log_name = does_log_start_with_hash(log_group_response_name)
            print(log_name)
            cloud_watch_location = "https://"+my_region+".console.aws.amazon.com/cloudwatch/home?region="+my_region+"#logsV2:log-groups/log-group/"+log_name+"/log-events/"+encode_string(log_stream_response_id)
            #https://eu-south-1.console.aws.amazon.com/cloudwatch/home?region=eu-south-1#logsV2:log-groups/log-group/{Log-group-name}/log-events/ID

        else:
            cloud_watch_location = "No CloudWatch logs found for this alarm."

        message= {
            "AlarmName": result["detail"]["alarmName"],
            "AlarmDescription": result["detail"]["configuration"]["description"],
            "AWSAccountId": result["account"],
            "AlarmConfigurationUpdatedTimestamp": result["detail"]["state"]["timestamp"],
            "NewStateValue": result["detail"]["state"]["value"],
            "NewStateReason": result["detail"]["state"]["reason"],
            "StateChangeTime": result["detail"]["state"]["timestamp"],
            "Region": "EU (Milan)",
            "AlarmURL": cloud_watch_location,
            "AlarmArn": result["resources"][0],
            "OldStateValue": result["detail"]["previousState"]["value"],
            "Trigger": {
                "MetricName": metric_name,
                "Namespace": cloud_watch_location,
                "Statistic": result["detail"]["configuration"]["metrics"][0]["metricStat"]["stat"],
                "Dimensions": [],
                "Period": result["detail"]["configuration"]["metrics"][0]["metricStat"]["period"],
                "EvaluationPeriods": metric_alarm_details_response["MetricAlarms"][0]["EvaluationPeriods"],
                "DatapointsToAlarm": 1,
                "ComparisonOperator": metric_alarm_details_response["MetricAlarms"][0]["ComparisonOperator"],
                "Threshold": 1,
                "TreatMissingData": metric_alarm_details_response["MetricAlarms"][0]["TreatMissingData"],
                "EvaluateLowSampleCountPercentile": ""
            }
        }

        response = sns_client.publish(
            TopicArn='arn:aws:sns:'+my_region+':' +result["account"] +':'+os.environ['AlarmSNSTopicName'],
            Message=json.dumps(message),
            Subject='CloudWatch Alarm',
        )

# This function will return the CloudWatch Log group name
def get_log_group_name(metric_name, metric_namespace):
    log_group_name = ''
    try:
        response = logs_client.describe_metric_filters(
            metricName=metric_name,
            metricNamespace=metric_namespace
        )
        print(response["metricFilters"])

        log_group_name = response["metricFilters"][0]["logGroupName"]
    except:
        log_group_name = "NotFound"

    return log_group_name

# This function will return the CloudWatch Log Stream ID triggered by the alarm 
def get_log_stream_id(log_group_name):
    response = logs_client.describe_log_streams(
        logGroupName=log_group_name,
        orderBy="LastEventTime",
        limit=1,
        descending=True
    )
    log_stream_id = response["logStreams"][0]["logStreamName"]

    return log_stream_id

# This function will return the Cloudwatch Alarm details     
def get_alarm_details(metric_name, metric_namespace):
    response = cloud_watch_client.describe_alarms_for_metric(
        MetricName=metric_name,
        Namespace=metric_namespace
    )

    return response

#This function checks whether the log group being with a "/"
def does_log_start_with_hash(log_group_name):
    if log_group_name[0] == '/':
        result = encode_string(log_group_name)
        return result
    else:
        return log_group_name

# This function is used to generate the URL to the Log group
# It will return an encoded string of the URL
def encode_string(log_group_name):
    return log_group_name.replace("/", "$252F")