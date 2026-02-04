import boto3
import json
import os
import re
import urllib.request

def get_github_token():
    secret_name = "github-token"
    region_name = os.environ.get('AWS_REGION', 'eu-south-1')
    print(f"INFO: Retrieving authentication token from Secrets Manager in region {region_name}")
    client = boto3.client(service_name='secretsmanager', region_name=region_name)
    try:
        get_secret_value_response = client.get_secret_value(SecretId=secret_name)
        print("SUCCESS: Token retrieved successfully")
        return get_secret_value_response['SecretString']
    except Exception as e:
        print("ERROR: Failed to retrieve authentication token")
        return None

def get_config_from_github(token, env, service_dir):
    url = f"https://api.github.com/repos/pagopa/pn-configuration/contents/{env}/{service_dir}/scripts/aws/cfn/microservice-{env}-cfg.json"
    print(f"INFO: Fetching configuration for '{service_dir}' from GitHub repository (env: {env})")
    req = urllib.request.Request(url)
    req.add_header('Authorization', f'token {token}')
    req.add_header('Accept', 'application/vnd.github.v3.raw')
    try:
        with urllib.request.urlopen(req) as response:
            config = json.loads(response.read().decode('utf-8'))
            print(f"SUCCESS: Configuration for '{service_dir}' fetched successfully")
            return config
    except Exception as e:
        # Se l'errore è un 404 (file mancante), restituiamo un dizionario vuoto per usare i default
        if hasattr(e, 'code') and e.code == 404:
            print(f"INFO: Config file not found for {service_dir} (404).")
            return {}
        # Per altri errori (es. 401 token scaduto, 500 GitHub down), solleviamo l'eccezione per attivare il fallback
        print(f"ERROR: GitHub API error for {service_dir}: {e}")
        raise

def get_official_counts(ecs_client, cluster_name, env_type, github_token):
    """Recupera i conteggi ufficiali da GitHub per tutti i servizi del cluster."""
    print(f"INFO: Building official counts for cluster {cluster_name} from GitHub")
    if not github_token:
        print("ERROR: GitHub token missing, cannot fetch official counts")
        return None

    service_counts = {}
    try:
        services_response = ecs_client.list_services(cluster=cluster_name, maxResults=100)
        for service_arn in services_response['serviceArns']:
            service_name = service_arn.split("/")[-1]
            # Override manuali per servizi specifici
            if "pn-external-channels-microsvc-test-ExternalChannelsMicroservice" in service_name or "mockconsolidatore-ExternalChannelsMicroservice" in service_name:
                service_counts[service_name] = 7
                continue
            
            # Determina la directory del servizio su GitHub (es. pn-delivery-push)
            service_dir = re.sub(r'-microsvc.*', '', service_name)
            try:
                config = get_config_from_github(github_token, env_type, service_dir)
            except Exception:
                # In caso di errore critico di rete o autenticazione su GitHub, 
                # restituiamo None per forzare il fallback su S3 nel chiamante
                return None
            
            min_tasks = 1 # Fallback di default
            if config:
                min_tasks_val = config.get('Parameters', {}).get('MinTasksNumber')
                if min_tasks_val is not None:
                    min_tasks = int(min_tasks_val)
            
            service_counts[service_name] = min_tasks
        return service_counts
    except Exception as e:
        print(f"ERROR list_services or fetching config: {e}")
        return None

def save_counts_to_s3(s3_client, bucket, cluster_name, account_id, counts):
    """Sovrascrive il file su S3 con i conteggi forniti."""
    object_key = f'desire_count_ecs_{cluster_name}_{account_id}.json'
    try:
        print(f"INFO: Overwriting S3 file '{object_key}' with official settings")
        s3_client.put_object(
            Bucket=bucket,
            Key=object_key,
            Body=json.dumps(counts),
            ContentType='application/json'
        )
        print(f"SUCCESS: S3 file updated")
        return True
    except Exception as e:
        print(f"ERROR updating S3: {e}")
        return False

def handle_stop(ecs_client, s3_client, cluster_name, env_type, s3bucket_name, account_id):
    print(f"==> STOPPING services for cluster: {cluster_name} (Env: {env_type})")
    
    # In DEV, salviamo i valori ATTUALI dei microservizi su S3 prima di spegnere
    if env_type == 'dev':
        service_counts = {}
        try:
            services_response = ecs_client.list_services(cluster=cluster_name, maxResults=100)
            for service_arn in services_response['serviceArns']:
                service_name = service_arn.split('/')[-1]
                desc = ecs_client.describe_services(cluster=cluster_name, services=[service_name])
                count = desc['services'][0]['desiredCount']
                if "pn-external-channels-microsvc-test-ExternalChannelsMicroservice" in service_name or "mockconsolidatore-ExternalChannelsMicroservice" in service_name:
                    count = 7
                service_counts[service_name] = count
            
            if service_counts:
                save_counts_to_s3(s3_client, s3bucket_name, cluster_name, account_id, service_counts)
        except Exception as e:
            print(f"ERROR processing current counts for DEV: {e}")

    # Spegnimento effettivo per tutti gli ambienti
    try:
        services_response = ecs_client.list_services(cluster=cluster_name, maxResults=100)
        service_arns = services_response['serviceArns']
        if not service_arns:
            print(f"No services found in cluster {cluster_name}.")
            return True
        
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
    except Exception as e:
        print(f"ERROR during stop execution: {e}")
        return False

def handle_start(ecs_client, s3_client, cluster_name, env_type, s3bucket_name, account_id, github_token):
    print(f"==> STARTING services for cluster: {cluster_name} (Env: {env_type})")
    service_counts = {}
    
    if env_type == 'dev':
        # In DEV prendiamo i valori salvati precedentemente su S3
        object_key = f'desire_count_ecs_{cluster_name}_{account_id}.json'
        try:
            print(f"INFO: Retrieving desired counts from S3 (bucket: {s3bucket_name}, key: {object_key})")
            response = s3_client.get_object(Bucket=s3bucket_name, Key=object_key)
            service_counts = json.loads(response['Body'].read().decode('utf-8'))
            print(f"SUCCESS: Previous counts retrieved from S3")
        except Exception as e:
            print(f"ERROR retrieving {object_key} from S3: {e}")
            return False
    else:
        # Negli altri ambienti proviamo GitHub con fallback su S3
        github_counts = get_official_counts(ecs_client, cluster_name, env_type, github_token)
        
        if github_counts:
            service_counts = github_counts
            print(f"SUCCESS: Official counts fetched from GitHub for cluster {cluster_name}")
            # Aggiorniamo S3 per allineamento
            save_counts_to_s3(s3_client, s3bucket_name, cluster_name, account_id, service_counts)
        else:
            # FALLBACK
            print(f"WARNING: GitHub fetch failed (bad token, network down, etc.). Falling back to S3 for cluster {cluster_name}")
            object_key = f'desire_count_ecs_{cluster_name}_{account_id}.json'
            try:
                response = s3_client.get_object(Bucket=s3bucket_name, Key=object_key)
                service_counts = json.loads(response['Body'].read().decode('utf-8'))
                print(f"SUCCESS: Fallback to S3 successful for {cluster_name}")
            except Exception as e:
                print(f"ERROR: GitHub failed AND S3 fallback failed for {cluster_name}: {e}")
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
    
    # Il token GitHub serve solo se NON siamo in DEV e stiamo facendo START
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
