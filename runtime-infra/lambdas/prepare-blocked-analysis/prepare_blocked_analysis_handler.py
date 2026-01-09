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
    
    # Allow override of environment variables from event
    database = event.get('database', database)
    table = event.get('table', table)
    workgroup = event.get('workgroup', workgroup)
    
    # Calculate script timeout based on remaining Lambda execution time
    # Leave 60 seconds buffer for cleanup and file upload
    if 'timeout' in event:
        # Allow explicit override from event
        timeout = event['timeout']
        print(f"Using timeout from event: {timeout} seconds")
    else:
        # Calculate dynamically: remaining time - 60 seconds buffer
        remaining_time_ms = context.get_remaining_time_in_millis()
        timeout = max(60, int(remaining_time_ms / 1000) - 60)
        print(f"Calculated timeout: {timeout} seconds (Lambda remaining: {remaining_time_ms/1000:.0f}s - 60s buffer)")
    
    cmd = [
        sys.executable,
        script_path,
        "--database", database,
        "--table", table,
        "--workgroup", workgroup,
        "--output-location", f"s3://{athena_results_bucket}/",
        "--s3-result-bucket", s3_result_bucket,
        "--timeout", str(timeout)
    ]
    
    # Add optional parameters from event
    if event.get('start_time'):
        cmd.extend(["--start-time", event['start_time']])
        print(f"Using custom start_time: {event['start_time']}")
    
    if event.get('end_time'):
        cmd.extend(["--end-time", event['end_time']])
        print(f"Using custom end_time: {event['end_time']}")
    
    if event.get('full_analysis', False):
        cmd.append("--full-analysis")
        print("Using full-analysis mode")
    
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
        
        # Script saves files directly to S3, download them to read metrics
        print("Downloading result files from S3 for metrics publishing...")
        s3_client = boto3.client('s3', region_name=region)
        bucket_name = s3_result_bucket.replace('s3://', '').split('/')[0]
        s3_prefix = '/'.join(s3_result_bucket.replace('s3://', '').split('/')[1:])
        
        # Create local result directory
        result_dir = "/tmp/prepare_blocked_results"
        os.makedirs(result_dir, exist_ok=True)
        
        # Download statistics.json and analysis.json from S3
        required_files = ['statistics.json', 'analysis.json']
        downloaded_files = []
        
        for filename in required_files:
            s3_key = f"{s3_prefix}/{filename}".lstrip('/')
            local_path = os.path.join(result_dir, filename)
            try:
                print(f"Downloading s3://{bucket_name}/{s3_key} to {local_path}")
                s3_client.download_file(bucket_name, s3_key, local_path)
                downloaded_files.append(filename)
                print(f"Successfully downloaded {filename}")
            except Exception as e:
                print(f"ERROR: Failed to download {filename} from S3: {e}")
        
        # Read and send metrics to CloudWatch if we have the required files
        if 'statistics.json' in downloaded_files:
            print(f"Publishing metrics from downloaded files...")
            publish_metrics_to_cloudwatch(result_dir, cloudwatch, region, cloudwatch_namespace,
                                         metric_name_total_open_case, metric_name_resolved_case, 
                                         metric_name_new_case, metric_name_affected)
        else:
            print("ERROR: statistics.json not found on S3, cannot publish CloudWatch metrics")
        
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
            
            # Try to download and publish metrics even after timeout
            try:
                print("Attempting to download results from S3 after timeout...")
                s3_client = boto3.client('s3', region_name=region)
                bucket_name = s3_result_bucket.replace('s3://', '').split('/')[0]
                s3_prefix = '/'.join(s3_result_bucket.replace('s3://', '').split('/')[1:])
                
                result_dir = "/tmp/prepare_blocked_results_timeout"
                os.makedirs(result_dir, exist_ok=True)
                
                # Try to download statistics.json and analysis.json
                required_files = ['statistics.json', 'analysis.json']
                downloaded_files = []
                
                for filename in required_files:
                    s3_key = f"{s3_prefix}/{filename}".lstrip('/')
                    local_path = os.path.join(result_dir, filename)
                    try:
                        s3_client.download_file(bucket_name, s3_key, local_path)
                        downloaded_files.append(filename)
                        print(f"Downloaded {filename} after timeout")
                    except Exception as download_error:
                        print(f"ERROR: Could not download {filename} from S3 after timeout: {download_error}")
                
                # Publish metrics if we have statistics.json
                if 'statistics.json' in downloaded_files:
                    publish_metrics_to_cloudwatch(result_dir, cloudwatch, region, cloudwatch_namespace,
                                                 metric_name_total_open_case, metric_name_resolved_case, 
                                                 metric_name_new_case, metric_name_affected)
                else:
                    print("ERROR: statistics.json not available after timeout, cannot publish metrics")
            except Exception as metrics_error:
                print(f"ERROR: Failed to download and publish metrics after timeout: {metrics_error}")
            
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
        
        # Use timestamp from analysis (last_update) to maintain temporal consistency
        # The metric values represent the state at the time of analysis, not publication time
        try:
            timestamp = datetime.strptime(last_update, '%Y-%m-%d %H:%M:%S')
        except:
            timestamp = datetime.utcnow()
        
        print(f"Publishing metrics with analysis timestamp: {timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
        
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
        affected_count = 0
        analysis_file = os.path.join(result_dir, 'analysis.json')
        if os.path.exists(analysis_file):
            with open(analysis_file, 'r', encoding='utf-8') as f:
                analysis_data = json.load(f)
            
            affected_count = len(analysis_data.get('analysis', []))
            
            # Log each affected case for CloudWatch Logs Insights table visualization
            for case in analysis_data.get('analysis', []):
                log_entry = {
                    'type': 'AFFECTED_PREPARE_CASE',
                    'timestamp': case.get('timestamp', ''),
                    'iun': case.get('iun', ''),
                    'timelineElementId': case.get('timelineElementId', ''),
                    'hasResult': case.get('hasResult', False),
                    'isInPaperRequestError': case.get('isInPaperRequestError', False)
                }
                print(json.dumps(log_entry))
        else:
            print("WARNING: analysis.json not found, setting affected count to 0")
        
        # Always publish the affected prepare metric (even if 0)
        metrics.append({
            'MetricName': metric_name_affected,
            'Value': float(affected_count),
            'Unit': 'Count',
            'Timestamp': timestamp
        })
        
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
