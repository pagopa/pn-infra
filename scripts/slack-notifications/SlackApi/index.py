import os
import json
from urllib import response
import boto3
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

logs_client = boto3.client('logs')
secrets_manager_client = boto3.client('secretsmanager')

def lambda_handler(event, context):
    success = {}

    if(event is not None):
        try:
            print(event)
            success = publish_message(event)
            
        except Exception as e:
            print(e)
            success = {
                'statusCode': 400,
                'body': json.dumps("Check error logs.")
            }
    else:
        success = {
            'statusCode': 500,
            'body': json.dumps('Message event is empty.')
        }
        
    return success

def get_slack_token():
    """
        This function authenticates your slack bot with the lambda function to post message
        Returns: Slack Token
    """
    slack_bot_token = ''
    try:
        response = secrets_manager_client.get_secret_value(
            SecretId= os.environ['SlackTokenArn']
        )
        if response is not None:
            secret_object = json.loads(response['SecretString'])
            slack_bot_token = secret_object['SlackToken']
        else:
            print("Unable to get secret string value.")
            slack_bot_token = ''
            
    except Exception as e:
        print("Exception in get_slack_token: ", e)

    return slack_bot_token
    
def publish_message(event):
    statusCode = 0  
    body = ''
    
    if event is not None:
        try:
            body = json.loads(event['Records'][0]['body'])
            fixed_json_string = fix_JSON(body['Message'])
            dumped_json = json.dumps(fixed_json_string)
            sqs_message = json.loads(dumped_json)
            region = event['Records'][0]['awsRegion']
            print("Input message: ", sqs_message)
            blocks = ""
            cloud_watch_location = ""
            slack_channel = os.environ['SlackChannelId']
            token = get_slack_token()

            if 'AlarmName' in sqs_message:
                #Message type is an Alarm message
                metric_name = sqs_message['Trigger']['MetricName']
                metric_namespace = sqs_message['Trigger']['Namespace']
                log_group_response_name = get_log_group_name(metric_name, metric_namespace)
                print("Log group name: ", log_group_response_name)
                detail_type = "AWS CloudWatch " + sqs_message['AlarmName'] + " triggered."
                if log_group_response_name == "NotFound":
                    #No log groups found - Send message with no enrichment
                    cloud_watch_location = "No Logs Found"
                else:
                    #Log group found - Create enriched message
                    log_stream_response_id = get_log_stream_id(log_group_response_name)
                    log_name = does_log_start_with_hash(log_group_response_name)
                    cloud_watch_location = "https://"+region+".console.aws.amazon.com/cloudwatch/home?region="+region+"#logsV2:log-groups/log-group/"+log_name+"/log-events/"+encode_string(log_stream_response_id)
                    print("CloudWatch link: ", cloud_watch_location) 

                _message = {
                    "detail-type": detail_type,
                    "AlarmDescription": sqs_message['AlarmDescription'],
                    "resourceLink": cloud_watch_location,
                    "alarmStatus": sqs_message['NewStateValue'],
                    "timestamp": sqs_message['StateChangeTime'],
                    "region": sqs_message['Region'],
                    "MetricName": sqs_message['Trigger']['MetricName'],
                    "accountId":  sqs_message['AWSAccountId']
                }

                blocks = alarm_notification_template(_message)

            else:
                #Message not Alarm type - Handle CodeBuild/CodePipeline
                resource_source = sqs_message['source']
                account_id = sqs_message['account']
                timestamp = sqs_message['time']
                region = sqs_message['region']
        
                if resource_source == "aws.codebuild":
                    resource_name = sqs_message['detail']['project-name']
                    resource_link = "https://"+region+".console.aws.amazon.com/codesuite/codebuild/"+account_id+"/projects/"+resource_name
                    resource_message = "CodeBuild has failed"
                    
                elif resource_source == "aws.codepipeline":
                    resource_name = sqs_message['detail']['pipeline']
                    resource_message = "CodePipeline has failed"
                    resource_link = "https://"+region+".console.aws.amazon.com/codesuite/codepipeline/pipelines/"+resource_name+"/view?region="+region

                _message = {
                    "detail-type":resource_message,
                    "account":account_id,
                    "timestamp":timestamp,
                    "region": region,
                    "resourceName": resource_name,
                    "resourceLink": resource_link,
                }

                blocks = devops_tools_notification_template(_message)
            
            print("Slack message: ", json.dumps(_message))
    
            slack_response = post_message_to_slack(token, slack_channel, _message, blocks)
            if(slack_response == "Success"):
                statusCode = 200
                body = "Slack_message_sent"
            else:
                statusCode = 500
                body = "Failed_to_Send_Message. See logs"

        except Exception as e:
            print("Exception in publishing message: ", e)
            statusCode = 400
            body = "Client_Error"
    else:
        print("Event is empty")
        statusCode = 500
        body = "Server_Error"
        
    data = {
        'statusCode': statusCode,
        'body': json.dumps(body)
    }
    
    return data

def alarm_notification_template(message):
    """
        This function is used to enrich the CloudWatch Alarm Notification.
        It will publish messages when CloudWatch Alarm is in Alarm or Ok state
        Returns: Enriched message block
    """
    
    if message['alarmStatus'] == 'ALARM':
        notification_emoji = 'rotating_light'
    else:
        notification_emoji = 'white_check_mark'
        
    blocks= [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "You have a new notification :"+notification_emoji+":\n*" + message['detail-type'] + "*"
            }
        },
        {
            "type": "section",
            "fields": [
                {
                    "type": "mrkdwn",
                    "text": "*Alarm Description*\n"+ message['AlarmDescription']
                },
                {
                    "type": "mrkdwn",
                    "text": "*Metric Alarm Name*\n"+ message['MetricName']
                },
                {
                    "type": "mrkdwn",
                    "text": "*Alarm Status*\n"+message['alarmStatus']
                },
                {
                    "type": "mrkdwn",
                    "text": "*Region*\n"+message['region']
                },
                {
                    "type": "mrkdwn",
                    "text": "*Account Id*\n"+message['accountId']
                },
                {
                    "type": "mrkdwn",
                    "text": "*Timestamp*\n"+message['timestamp']
                }
            ]
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*Resource Link*\n" + message['resourceLink']
            }
        }
    ]

    return blocks

def devops_tools_notification_template(message):
    """
        This function is used to enrich the notification message from CodeBuild and CodePipeline
        Returns: Enriched message block
    """
    blocks= [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "You have a new notification :rotating_light: \n*" + message['detail-type'] + "*"
                }
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": "*Region:*\n"+ message['region']
                    },
                    {
                        "type": "mrkdwn",
                        "text": "*Account:*\n"+message['account']
                    },
                    {
                        "type": "mrkdwn",
                        "text": "*Project Name:*\n"+message['resourceName']
                    },
                    {
                        "type": "mrkdwn",
                        "text": "*Timestamp:*\n"+message['timestamp']
                    }
                ]
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Resource Link*\n" + message['resourceLink']
                }
            }
        ]
    return blocks

def get_log_group_name(metric_name, metric_namespace):
    """
        This function checks if the AWS CloudWatch logs for the alarm causing resource are available.
        Returns: log group name
    """
    log_group_name = ''
    try:
        response = logs_client.describe_metric_filters(
            metricName=metric_name,
            metricNamespace=metric_namespace
        )
        
        log_group_name = response["metricFilters"][0]["logGroupName"]
    except Exception as e:
        print("Exception raised: ", e)
        log_group_name = "NotFound"
        
    return log_group_name
    
def get_log_stream_id(log_group_name):
    """
        This function checks if the AWS CloudWatch logs for the alarm causing resource are available.
        Returns: return the CloudWatch Log Stream ID
    """
    log_stream_id = ''
    try:
        response = logs_client.describe_log_streams(
            logGroupName=log_group_name,
            orderBy="LastEventTime",
            limit=1,
            descending=True
            )
            
        if response["logStreams"] is not None:
            log_stream_id = response["logStreams"][0]["logStreamName"]
        else:
            log_stream_id = 'NotFound'
    
    except Exception as e:
        print("Exception raised: ", e)
        log_stream_id = 'NotFound'
    
    return log_stream_id
    
def does_log_start_with_hash(log_group_name):
    """
        This function checks whether the log group begins with a "/".
        If it does, it will encode the string to conform to URL encoding
        Returns: An encdoded log group name
    """ 
    if log_group_name[0] == '/':
        result = encode_string(log_group_name)
        return result
    else:
        return log_group_name
    
def encode_string(log_group_name):
    """
        This function is used to generate the URL to the Log group
        Returns: an encoded string of the URL
    """ 
    return log_group_name.replace("/", "$252F")

#This function 
def fix_JSON(json_message=None):
    """
        This function is is used to fix Escape Formatting errors
        from the incoming message event. It will remove the 
        character causing the error.
        Returns: a new python object 
    """ 
    result = None
    try:        
        result = json.loads(json_message)
    except Exception as e:      
        # Find the offending character index:
        idx_to_replace = int(str(e).split(' ')[-1].replace(')', ''))        
        # Remove the offending character:
        json_message = list(json_message)
        json_message[idx_to_replace] = ' '
        new_message = ''.join(json_message)     
        return fix_JSON(json_message=new_message)
    return result


def post_message_to_slack(token, channel, text, blocks):
    """
        This function is used to post a message to a slack channel
        Returns: Success if message is posted, else Failed if message fails.
    """ 
    try:
        slack_client = WebClient(token=token)
        # Call the chat.postMessage method using the WebClient
        result = slack_client.chat_postMessage(
            token=token,
            channel=channel, 
            text=json.dumps(text),
            blocks=blocks
        )
        print(result)
        return "Success"

    except SlackApiError as e:
        print(f"Error posting message: {e}")
        return "Failed"