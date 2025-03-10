#!/usr/bin/env python3
"""
Script to update CDC tables in Parquet format from JSON sources.
Supports processing by year, specific months, or specific days within a single month.
"""
import boto3
import argparse
import logging
import sys
import time
#import json
import datetime
from concurrent.futures import ThreadPoolExecutor
from botocore.exceptions import ClientError

#configure logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger()

def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description='Update CDC cache tables from JSON to Parquet')
    
    #required parameters
    parser.add_argument('--envName', required=True, help='Environment (dev, uat, prod)')
    parser.add_argument('--table', required=True, help='Base table name (e.g. pn_userattributes)')
    parser.add_argument('--year', type=int, required=True, help='Year to process (YYYY)')
    
    #optional parameters
    parser.add_argument('--database', default='cdc_analytics_database', help='Glue database name')
    parser.add_argument('--workgroup', default='cdc_analytics_workgroup', help='Athena workgroup')
    parser.add_argument('--region', default='eu-south-1', help='AWS region')
    parser.add_argument('--workers', type=int, default=12, help='Maximum concurrent workers')
    parser.add_argument('--months', help='Specific months to process (comma-separated, e.g. "01,02,03")')
    parser.add_argument('--days', help='Specific days to process (comma-separated, e.g. "01,15,30")')
    
    return parser.parse_args()

def parse_csv_param(value, width=2):
    """Convert a CSV parameter to a properly formatted list"""
    if not value:
        return None
    return [str(item).strip().zfill(width) for item in value.split(',')]

def setup_aws_session(env_name, region):
    """Set up AWS session and clients"""
    profile = f"sso_pn-core-{env_name}"
    try:
        session = boto3.Session(profile_name=profile, region_name=region)
        account_id = session.client('sts').get_caller_identity()['Account']
        logger.info(f"Authenticated with profile {profile} (Account: {account_id})")
        return session, account_id
    except Exception as e:
        logger.error(f"AWS authentication error: {e}")
        logger.error(f"Please run: aws sso login --profile {profile}")
        return None, None

def get_table_info(glue, database, base_name, crawler_list, account_id, region):
    """Verify tables and crawler tags"""
    view_name = f"{base_name}_json_view"
    cache_name = f"{base_name}_parsed_cache"
    
    #check if tables exist
    for table_name in [view_name, cache_name]:
        try:
            glue.get_table(DatabaseName=database, Name=table_name)
        except ClientError as e:
            if e.response['Error']['Code'] == 'EntityNotFoundException':
                logger.error(f"Table {table_name} does not exist in database {database}")
                return None, None
    
    # check crawler tags
    for crawler_name in crawler_list:
        try:
            tags = glue.get_tags(ResourceArn=f"arn:aws:glue:{region}:{account_id}:crawler/{crawler_name}").get('Tags', {})
            if (tags.get('PnHasView') == 'true' and tags.get('PnView') == view_name and tags.get('PnViewCache') == cache_name):
                return view_name, cache_name
        except Exception:
            pass
    
    logger.error(f"No crawler with PnHasView tag found for {base_name}")
    return None, None

def execute_query(session, params):
    """Execute an Athena query and monitor its completion"""
    athena = session.client('athena')
    database, workgroup = params['database'], params['workgroup']
    view, table = params['view'], params['table']
    year, month, day = params['year'], params.get('month'), params.get('day')
    output_location = params.get('output_location')
    
    #build WHERE conditions
    conditions = [f"p_year = '{year}'"]
    if month: conditions.append(f"p_month = '{month}'")
    if day: conditions.append(f"p_day = '{day}'")
    where_clause = " AND ".join(conditions)
    
    #build the query
    query = f"""
    INSERT INTO "{database}"."{table}" 
    (
      SELECT * FROM "{database}"."{view}" 
      WHERE {where_clause}
      EXCEPT 
      SELECT * FROM "{database}"."{table}" 
      WHERE {where_clause}
    )
    """
    
    #ID for logging
    partition_id = f"{year}" + (f"-{month}" if month else "") + (f"-{day}" if day else "")
    start_time = time.time()
    logger.info(f"Starting query for partition: {partition_id}")
    
    #execution configurationn
    config = {
        'QueryString': query,
        'WorkGroup': workgroup,
        'QueryExecutionContext': {'Database': database}
    }
    
    if output_location:
        output_path = f"{output_location}/cache_updates/{table}/{year}"
        if month: output_path += f"/{month}"
        if day: output_path += f"/{day}"
        config['ResultConfiguration'] = {'OutputLocation': output_path}
    
    #debug API call with timestamp
    #now = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
    #logger.info(f"DEBUG API CALL [{now}]:\n{json.dumps(config, indent=2)}")
    
    #execute query
    query_id = athena.start_query_execution(**config)['QueryExecutionId']
    logger.info(f"Query ID: {query_id}")
    
    #monitor completion
    while True:
        response = athena.get_query_execution(QueryExecutionId=query_id)
        state = response['QueryExecution']['Status']['State']
        
        if state == 'SUCCEEDED':
            duration = time.time() - start_time
            logger.info(f"Query completed successfully: {partition_id} ({duration:.2f}s)")
            return {'partition': partition_id, 'status': 'SUCCESS', 'id': query_id, 'duration': duration}
        
        if state in ['FAILED', 'CANCELLED']:
            duration = time.time() - start_time
            error = response['QueryExecution']['Status'].get('StateChangeReason', 'Unknown error')
            logger.error(f"Query failed for {partition_id}: {error}")
            return {'partition': partition_id, 'status': state, 'error': error, 'id': query_id, 'duration': duration}
        
        time.sleep(5)

def should_process_partition(year, month=None, day=None, now=None):
    """Determine if a partition should be processed based on current date"""
    if not now: now = datetime.datetime.now(datetime.timezone.utc)
    
    year = str(year)
    current_year, current_month, current_day = str(now.year), f"{now.month:02d}", f"{now.day:02d}"
    
    #skip future years
    if year > current_year:
        return False, "future year"
    #skip future months in current year
    if year == current_year and month and month > current_month:
        return False, "future month"
    #skip current day in current month/year
    if year == current_year and month == current_month and day == current_day:
        return False, "current day"
    return True, None

def generate_partitions(args, view_name, cache_name, output_location):
    """Generate partitions to process based on args and current date"""
    now = datetime.datetime.now(datetime.timezone.utc)
    year = str(args.year)
    current_year, current_month, current_day = str(now.year), f"{now.month:02d}", f"{now.day:02d}"
    
    #base params for all queries
    base_params = {
        'database': args.database, 'workgroup': args.workgroup,
        'view': view_name, 'table': cache_name,
        'year': year, 'output_location': output_location
    }
    
    #parse months and days
    months = parse_csv_param(args.months)
    days = parse_csv_param(args.days)

    #validate parameter combinations
    if days and (not months or len(months) > 1):
        logger.error("Error: When specifying days, you must specify exactly one month")
        return [], None, None
    
    query_params = []
    
    if days:
        #process specific days in a single month
        month = months[0]
        for day in days:
            should_process, reason = should_process_partition(year, month, day, now)
            if not should_process:
                logger.warning(f"Skipping {year}-{month}-{day} ({reason}) - Today's data will be processed by UpdateCdcJsonViewsLambda after midnight")
                continue
                
            params = base_params.copy()
            params.update({'month': month, 'day': day})
            query_params.append(params)
        
        day_count = len([d for d in days if should_process_partition(year, month, d, now)[0]])
        logger.info(f"Scheduled {day_count} queries for specific days in {year}-{month}")
    else:
        #process specific months or full year
        month_list = months if months else [f"{m:02d}" for m in range(1, 13)]
        for month in month_list:
            should_process, reason = should_process_partition(year, month, None, now)
            if not should_process:
                logger.info(f"Skipping {year}-{month} ({reason})")
                continue
                
            #handling for current month - process by day
            if year == current_year and month == current_month:
                for day in [f"{d:02d}" for d in range(1, now.day)]:
                    params = base_params.copy()
                    params.update({'month': month, 'day': day})
                    query_params.append(params)
                logger.warning(f"For current month {year}-{month}, only processing days 01 to {int(current_day)-1:02d} (skipping today)")
            else:
                #process entire month
                params = base_params.copy()
                params['month'] = month
                query_params.append(params)
        
        logger.info(f"Scheduled queries for {len(query_params)} partitions in {year}" + 
                   (" (with special handling for current month)" if year == current_year else ""))
    
    return query_params, months, days

def print_summary(results, start_time, args, months, days):
    """Print execution summary and statistics"""
    now = datetime.datetime.now(datetime.timezone.utc)
    current_year, current_month, current_day = str(now.year), f"{now.month:02d}", f"{now.day:02d}"
    total_execution_time = time.time() - start_time
    successes = len([r for r in results if r.get('status') == 'SUCCESS'])
    failures = len(results) - successes

    print("\n" + "=" * 100)
    print(f"CDC PARQUET UPDATE - {now.strftime('%Y-%m-%d %H:%M:%S')} UTC")
    print(f"Table: {args.table} | Environment: {args.envName} | Region: {args.region}")
    print(f"Total execution time: {total_execution_time:.2f} seconds")
    print("=" * 100)
    print(f"{'PARTITION':<12} {'QUERY ID':<38} {'STATUS':<10} {'DURATION':<10} {'DETAILS'}")
    print("-" * 100)
    
    # Print results
    for result in sorted(results, key=lambda r: r.get('partition', '')):
        partition = result.get('partition', 'Unknown')
        query_id = result.get('id', 'N/A')
        status = result.get('status', 'Unknown')
        duration = f"{result.get('duration', 0):.2f}s"
        details = result.get('error', '') if status != 'SUCCESS' else ''
        
        print(f"{partition:<12} {query_id:<38} {status:<10} {duration:<10} {details}")
    
    print("-" * 100)
    print(f"SUMMARY: {successes}/{len(results)} successful | {failures}/{len(results)} failed")
    
    #show execution time stats if we have multiple queries
    if len(results) > 1:
        durations = [r.get('duration', 0) for r in results if 'duration' in r]
        if durations:
            avg_duration = sum(durations) / len(durations)
            print(f"Query times: avg={avg_duration:.2f}s | min={min(durations):.2f}s | max={max(durations):.2f}s")
    
    print("=" * 100)
    
    #print reminder about today's data, but ONLY if relevant
    show_today_message = False
    
    #check if we're processing the current year
    if int(args.year) == now.year:
        #check if processing all months (no specific months) or current month is included
        if not months or current_month in months:
            show_today_message = True
        #check if processing specific days and current day is included
        elif days and current_day in days:
            show_today_message = True
    
    if show_today_message:
        print(f"\nNOTE: In order of avoiding incomplete parquet partitions, data for today ({current_year}-{current_month}-{current_day})")
        print(f" will be skipped and processed by UpdateCdcJsonViewsLambda scheduled after midnight.")
    
    return 0 if failures == 0 else 1

def main():
    """Main function"""
    args = parse_args()
    execution_start = time.time()
    
    #setup AWS session and clients
    session, account_id = setup_aws_session(args.envName, args.region)
    if not session: return 1
    glue = session.client('glue')
    athena = session.client('athena')
    
    #verify tables and get table info
    try:
        crawler_list = glue.list_crawlers(MaxResults=100).get('CrawlerNames', [])
        view_name, cache_name = get_table_info(glue, args.database, args.table, crawler_list, account_id, args.region)
        if not view_name or not cache_name: return 1
        logger.info(f"Tables verified: view={view_name}, cache={cache_name}")
    except Exception as e:
        logger.error(f"Error verifying tables: {e}")
        return 1
    
    #get workgroup output location
    output_location = None
    try:
        workgroup_info = athena.get_work_group(WorkGroup=args.workgroup)
        output_location = workgroup_info.get('WorkGroup', {}).get('Configuration', {}).get('ResultConfiguration', {}).get('OutputLocation')
        if output_location:
            logger.info(f"Using workgroup output location: {output_location}")
        else:
            logger.warning(f"No output location configured for workgroup {args.workgroup}")
    except Exception as e:
        logger.warning(f"Could not retrieve workgroup info: {e}")
    
    #generate partitions to process
    query_params, months, days = generate_partitions(args, view_name, cache_name, output_location)
    if not query_params:
        logger.warning("No queries to execute after applying current date filtering")
        return 0
    
    #execute queries
    results = []
    max_workers = min(args.workers, len(query_params))
    logger.info(f"Starting execution with {max_workers} parallel workers")
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(execute_query, session, params) for params in query_params]
        for future in futures:
            try:
                results.append(future.result())
            except Exception as e:
                logger.error(f"Error during execution: {str(e)}")
    
    #print summary and return status
    return print_summary(results, execution_start, args, months, days)

if __name__ == "__main__":
    sys.exit(main())