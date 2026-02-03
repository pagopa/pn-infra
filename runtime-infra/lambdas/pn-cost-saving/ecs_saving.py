import boto3
import json
import os
import re
import urllib.request

def get_github_token():
    secret_name = "github-token"
    region_name = os.environ.get('AWS_REGION', 'eu-south-1')
    client = boto3.client(service_name='secretsmanager', region_name=region_name)
    try:
        get_secret_value_response = client.get_secret_value(SecretId=secret_name)
        return get_secret_value_response['SecretString']
    except Exception as e:
        print(f"ERROR retrieving github-token secret: {e}")
        return None

def get_config_from_github(token, env, service_dir):
    url = f"https://api.github.com/repos/pagopa/pn-configuration/contents/{env}/{service_dir}/scripts/aws/cfn/microservice-{env}-cfg.json"
    req = urllib.request.Request(url)
    req.add_header('Authorization', f'token {token}')
    req.add_header('Accept', 'application/vnd.github.v3.raw')
    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode('utf-8'))
    except Exception as e:
        print(f"INFO: Could not find or fetch config for {service_dir} in {env} from GitHub: {e}")
        return None

def handle_stop(ecs_client, s3_client, cluster_name, env_type, s3bucket_name, account_id):
    print(f"==> STOPPING services for cluster: {cluster_name}")
    try:
        services_response = ecs_client.list_services(cluster=cluster_name, maxResults=100)
        service_arns = services_response['serviceArns']
    except Exception as e:
        print(f"ERROR list_services for {cluster_name}: {e}")
        return False

    if not service_arns:
        print(f"No services found in cluster {cluster_name}.")
        return True

    # In DEV, save current counts to S3 before stopping
    if env_type == 'dev':
        service_counts = {}
        for service_arn in service_arns:
            service_name = service_arn.split('/')[-1]
            try:
                desc = ecs_client.describe_services(cluster=cluster_name, services=[service_name])
                count = desc['services'][0]['desiredCount']
                if "pn-external-channels-microsvc-test-ExternalChannelsMicroservice" in service_name or "mockconsolidatore-ExternalChannelsMicroservice" in service_name:
                    count = 7
                service_counts[service_name] = count
            except Exception as e:
                print(f"ERROR getting count for {service_name}: {e}")
        
        if service_counts:
            object_key = f'desire_count_ecs_{cluster_name}_{account_id}.json'
            try:
                s3_client.put_object(
                    Bucket=s3bucket_name,
                    Key=object_key,
                    Body=json.dumps(service_counts),
                    ContentType='application/json'
                )
                print(f"SUCCESS: Counts saved to S3: {object_key}")
            except Exception as e:
                print(f"ERROR saving to S3: {e}")

    # Set desiredCount to 0 for all services
    success = True
    for service_arn in service_arns:
        service_name = service_arn.split('/')[-1]
        try:
            ecs_client.update_service(cluster=cluster_name, service=service_name, desiredCount=0)
            print(f"SUCCESS: {service_name} set to 0")
        except Exception as e:
            print(f"ERROR stopping {service_name}: {e}")
            success = False
    return success

def handle_start(ecs_client, s3_client, cluster_name, env_type, s3bucket_name, account_id, github_token):
    print(f"==> STARTING services for cluster: {cluster_name}")
    service_counts = {}
    
    if env_type == 'dev':
        object_key = f'desire_count_ecs_{cluster_name}_{account_id}.json'
        try:
            response = s3_client.get_object(Bucket=s3bucket_name, Key=object_key)
            service_counts = json.loads(response['Body'].read().decode('utf-8'))
        except Exception as e:
            print(f"ERROR retrieving {object_key} from S3: {e}")
            return False
    else:
        if not github_token:
            print("ERROR: GitHub token missing")
            return False
        try:
            services_response = ecs_client.list_services(cluster=cluster_name, maxResults=100)
            for service_arn in services_response['serviceArns']:
                service_name = service_arn.split("/")[-1]
                if "pn-external-channels-microsvc-test-ExternalChannelsMicroservice" in service_name or "mockconsolidatore-ExternalChannelsMicroservice" in service_name:
                    service_counts[service_name] = 7
                    continue
                
                service_dir = re.sub(r'-microsvc.*', '', service_name)
                config = get_config_from_github(github_token, env_type, service_dir)
                min_tasks = config.get('Parameters', {}).get('MinTasksNumber') if config else None
                service_counts[service_name] = int(min_tasks) if min_tasks else 1
        except Exception as e:
            print(f"ERROR building start counts: {e}")
            return False

    success = True
    for service_name, count in service_counts.items():
        try:
            ecs_client.update_service(cluster=cluster_name, service=service_name, desiredCount=count)
            print(f"SUCCESS: {service_name} set to {count}")
        except Exception as e:
            print(f"ERROR starting {service_name}: {e}")
            success = False
    return success

def lambda_handler(event, context):
    action = event.get('action')
    if action not in ['start', 'stop']:
        print(f"ERROR: Invalid or missing action '{action}'")
        return {'statusCode': 400, 'body': f"Invalid action: {action}"}

    ecs_cluster_names = os.environ.get('ECSClusterName', '').split(',')
    env_type = os.environ.get('EnvironmentType', 'dev')
    s3bucket_name = os.environ.get('EcsDesireCountBucket')
    account_id = os.environ.get('AwsAccountId')

    ecs_client = boto3.client('ecs')
    s3_client = boto3.client('s3')
    
    github_token = None
    if action == 'start' and env_type != 'dev':
        github_token = get_github_token()

    overall_success = True
    for cluster in ecs_cluster_names:
        cluster = cluster.strip()
        if not cluster: continue
        
        if action == 'stop':
            res = handle_stop(ecs_client, s3_client, cluster, env_type, s3bucket_name, account_id)
        else:
            res = handle_start(ecs_client, s3_client, cluster, env_type, s3bucket_name, account_id, github_token)
        
        if not res: overall_success = False

    return {
        'statusCode': 200 if overall_success else 500,
        'body': f"Action {action} completed {'successfully' if overall_success else 'with errors'}"
    }
