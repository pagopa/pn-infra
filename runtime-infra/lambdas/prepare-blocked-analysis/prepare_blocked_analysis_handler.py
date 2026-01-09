import os
import boto3
import subprocess
import sys
import shutil
import urllib.request
import zipfile
import json
from pathlib import Path
from datetime import datetime

def lambda_handler(event, context):
    print("Starting PrepareBlockedAnalysis Lambda")
    
    # Get environment variables
    region = os.environ['Region']
    database = os.environ.get('AthenaDatabase', 'cdc_analytics_database')
    table = os.environ.get('AthenaTable', 'pn_timelines_json_view')
    workgroup = os.environ.get('AthenaWorkgroup', 'primary')
    s3_result_bucket = os.environ['S3ResultBucket']
    athena_results_bucket = os.environ['AthenaResultsBucket']
    repo_zip_url = os.environ['RepoZipUrl']
    cloudwatch_namespace = os.environ['CloudWatchNamespace']
    
    # CloudWatch metric names
    metric_name_total_open_case = os.environ['MetricNameTotalOpenCases']
    metric_name_resolved_case = os.environ['MetricNameResolvedInLastRun']
    metric_name_new_case = os.environ['MetricNameNewInLastRun']
    metric_name_affected = os.environ['MetricNameAffectedPrepare']
    
    # Initialize CloudWatch client
    cloudwatch = boto3.client('cloudwatch', region_name=region)
    
    # Download pn-troubleshooting repository as ZIP
    zip_path = "/tmp/pn-troubleshooting.zip"
    repo_path = "/tmp/pn-troubleshooting"
    
    # Clean up if exists
    if os.path.exists(repo_path):
        shutil.rmtree(repo_path)
    if os.path.exists(zip_path):
        os.remove(zip_path)
    
    print(f"Downloading pn-troubleshooting repository from {repo_zip_url}...")
    try:
        urllib.request.urlretrieve(repo_zip_url, zip_path)
        print("Repository downloaded successfully")
        
        # Extract ZIP
        print("Extracting ZIP...")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall("/tmp")
        
        # Find extracted folder (works with any branch name)
        import glob
        extracted_folders = glob.glob("/tmp/pn-troubleshooting-*")
        if extracted_folders:
            extracted_folder = extracted_folders[0]
            print(f"Found extracted folder: {extracted_folder}")
            if os.path.exists(repo_path):
                shutil.rmtree(repo_path)
            os.rename(extracted_folder, repo_path)
        else:
            raise FileNotFoundError("Extracted folder not found")
        
        print("Repository extracted successfully")
    except Exception as e:
        print(f"ERROR: Failed to download/extract repository: {e}")
        raise
    
    # Change to script directory
    script_dir = os.path.join(repo_path, "prepare_blocked_analisys")
    script_path = os.path.join(script_dir, "prepare_blocked_analisys.py")
    
    if not os.path.exists(script_path):
        print(f"ERROR: Script not found at {script_path}")
        raise FileNotFoundError(f"Script not found at {script_path}")
    
    print(f"Found script at {script_path}")
    
    # Execute the script
    print("Executing prepare_blocked_analisys.py...")
    
    cmd = [
        sys.executable,
        script_path,
        "--database", database,
        "--table", table,
        "--workgroup", workgroup,
        "--output-location", f"s3://{athena_results_bucket}/",
        "--s3-result-bucket", s3_result_bucket,
        "--timeout", "840"  # 60 secondi meno del timeout Lambda per salvare i progressi
    ]
    
    print(f"Running command: {' '.join(cmd)}")
    
    try:
        # Run the script
        result = subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
            cwd=script_dir,
            env={**os.environ, 'AWS_DEFAULT_REGION': region}
        )
        print("Script output:")
        print(result.stdout)
        if result.stderr:
            print("Script stderr:")
            print(result.stderr)
        
        # Copy result files to S3
        result_dir = os.path.join(script_dir, "result")
        if os.path.exists(result_dir):
            print(f"Copying result files from {result_dir} to S3...")
            s3_client = boto3.client('s3', region_name=region)
            bucket_name = s3_result_bucket.replace('s3://', '').split('/')[0]
            s3_prefix = '/'.join(s3_result_bucket.replace('s3://', '').split('/')[1:])
            
            uploaded_files = []
            for filename in os.listdir(result_dir):
                file_path = os.path.join(result_dir, filename)
                if os.path.isfile(file_path):
                    s3_key = f"{s3_prefix}/{filename}".lstrip('/')
                    print(f"Uploading {filename} to s3://{bucket_name}/{s3_key}")
                    s3_client.upload_file(file_path, bucket_name, s3_key)
                    uploaded_files.append(filename)
            
            print(f"Successfully uploaded {len(uploaded_files)} files to S3: {uploaded_files}")
            
            # Read and send metrics to CloudWatch
            publish_metrics_to_cloudwatch(result_dir, cloudwatch, region, cloudwatch_namespace,
                                         metric_name_total_open_case, metric_name_resolved_case, 
                                         metric_name_new_case, metric_name_affected)
        else:
            print(f"Result directory not found at {result_dir}")
        
        return {
            'statusCode': 200,
            'body': 'PrepareBlockedAnalysis completed successfully'
        }
    except subprocess.CalledProcessError as e:
        print(f"ERROR: Script execution failed with return code {e.returncode}")
        print(f"stdout: {e.stdout}")
        print(f"stderr: {e.stderr}")
        
        # Return code 2 means timeout, which is acceptable
        if e.returncode == 2:
            print("Script reached timeout but saved progress")
            
            # Try to upload any result files even after timeout
            result_dir = os.path.join(script_dir, "result")
            if os.path.exists(result_dir):
                print(f"Attempting to copy result files after timeout...")
                try:
                    s3_client = boto3.client('s3', region_name=region)
                    bucket_name = s3_result_bucket.replace('s3://', '').split('/')[0]
                    s3_prefix = '/'.join(s3_result_bucket.replace('s3://', '').split('/')[1:])
                    
                    uploaded_files = []
                    for filename in os.listdir(result_dir):
                        file_path = os.path.join(result_dir, filename)
                        if os.path.isfile(file_path):
                            s3_key = f"{s3_prefix}/{filename}".lstrip('/')
                            s3_client.upload_file(file_path, bucket_name, s3_key)
                            uploaded_files.append(filename)
                    
                    print(f"Uploaded {len(uploaded_files)} files after timeout: {uploaded_files}")
                except Exception as upload_error:
                    print(f"ERROR: Failed to upload files after timeout: {upload_error}")
            
            return {
                'statusCode': 200,
                'body': 'PrepareBlockedAnalysis reached timeout but progress was saved'
            }
        
        # For other errors, log and re-raise
        print(f"ERROR: Script execution failed, re-raising exception")
        raise


def publish_metrics_to_cloudwatch(result_dir, cloudwatch, region, namespace,
                                  metric_name_total_open_case, metric_name_resolved_case,
                                  metric_name_new_case, metric_name_affected):
    """
    Reads statistics.json and analysis.json and publishes metrics to CloudWatch
    """
    try:
        # Read statistics.json
        stats_file = os.path.join(result_dir, 'statistics.json')
        if not os.path.exists(stats_file):
            print("ERROR: statistics.json not found, skipping metrics")
            return
        
        with open(stats_file, 'r', encoding='utf-8') as f:
            stats_data = json.load(f)
        
        summary = stats_data.get('summary', {})
        last_update = stats_data.get('last_update', datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'))
        
        # Parse last_update timestamp
        try:
            timestamp = datetime.strptime(last_update, '%Y-%m-%d %H:%M:%S')
        except:
            timestamp = datetime.utcnow()
        
        # Prepare metrics
        metrics = [
            {
                'MetricName': metric_name_total_open_case,
                'Value': float(summary.get('total_open_cases', 0)),
                'Unit': 'Count',
                'Timestamp': timestamp
            },
            {
                'MetricName': metric_name_resolved_case,
                'Value': float(summary.get('resolved_in_last_run', 0)),
                'Unit': 'Count',
                'Timestamp': timestamp
            },
            {
                'MetricName': metric_name_new_case,
                'Value': float(summary.get('new_in_last_run', 0)),
                'Unit': 'Count',
                'Timestamp': timestamp
            }
        ]
        
        # Read analysis.json for affected prepare count
        analysis_file = os.path.join(result_dir, 'analysis.json')
        if os.path.exists(analysis_file):
            with open(analysis_file, 'r', encoding='utf-8') as f:
                analysis_data = json.load(f)
            
            affected_count = len(analysis_data.get('analysis', []))
            metrics.append({
                'MetricName': metric_name_affected,
                'Value': float(affected_count),
                'Unit': 'Count',
                'Timestamp': timestamp
            })
        else:
            print("WARNING: analysis.json not found")
        
        # Publish metrics to CloudWatch (namespace passed as parameter)
        
        for metric in metrics:
            try:
                cloudwatch.put_metric_data(
                    Namespace=namespace,
                    MetricData=[metric]
                )
                print(f"Published metric {metric['MetricName']}: {metric['Value']}")
            except Exception as e:
                print(f"ERROR: Failed to publish metric {metric['MetricName']}: {e}")
        
        print(f"Successfully published {len(metrics)} metrics to CloudWatch namespace '{namespace}'")
        
    except Exception as e:
        print(f"ERROR: Failed to publish metrics to CloudWatch: {e}")
