import boto3
import os

ec2 = boto3.resource('ec2')

def lambda_handler(event, context):

    tag_name = os.environ['StopEc2FunctionTagName']
    tag_value = os.environ['StopEc2FunctionTagValue']

    filter = [{
        'Name': 'tag:' + tag_name,
        'Values': [tag_value]
    }]

    for instance in ec2.instances.filter(Filters=filter):
        instance_id = instance.id
        instance_type = instance.instance_type
        instance_state = instance.state['Name']
        instance.stop()
        print(f"EC2 Instance that will be stopped: {instance_id} ({instance_type}) - State: {instance_state}")

    return 'Successfully identified EC2 instances and stopping it'
