"""Athena service layer"""
import boto3
import time
from config import logger, ATHENA_RESULTS_BUCKET

athena = boto3.client('athena')


def execute_athena_query(query, database, workgroup, timeout=300):
    """
    Execute Athena query and wait for completion
    Returns list of result rows as dictionaries
    """
    logger.info(f"Starting Athena query execution in database: {database}")
    logger.debug(f"Query: {query}")
    
    # Start query execution
    response = athena.start_query_execution(
        QueryString=query,
        QueryExecutionContext={'Database': database},
        ResultConfiguration={'OutputLocation': f"s3://{ATHENA_RESULTS_BUCKET}/query_results/"},
        WorkGroup=workgroup
    )
    query_execution_id = response['QueryExecutionId']
    
    logger.info(f"Query execution started: {query_execution_id}")
    
    # Wait for query completion
    start_time = time.time()
    while True:
        execution = athena.get_query_execution(QueryExecutionId=query_execution_id)
        status = execution['QueryExecution']['Status']['State']
        
        if status in ['SUCCEEDED', 'FAILED', 'CANCELLED']:
            break
        
        # Check timeout
        if time.time() - start_time > timeout:
            raise RuntimeError(f"Query execution timeout after {timeout} seconds")
        
        time.sleep(2)
    
    elapsed = time.time() - start_time
    logger.info(f"Query execution finished with status: {status} (elapsed: {elapsed:.1f}s)")
    
    if status != 'SUCCEEDED':
        reason = execution['QueryExecution']['Status'].get('StateChangeReason', 'Unknown')
        raise RuntimeError(f"Query {query_execution_id} failed: {reason}")
    
    # Get query results
    results = []
    next_token = None
    
    while True:
        if next_token:
            response = athena.get_query_results(
                QueryExecutionId=query_execution_id,
                NextToken=next_token
            )
        else:
            response = athena.get_query_results(QueryExecutionId=query_execution_id)
        
        result_set = response['ResultSet']
        rows = result_set['Rows']
        
        # Extract column names from first row (header)
        if not results and rows:
            column_info = result_set.get('ResultSetMetadata', {}).get('ColumnInfo', [])
            column_names = [col['Name'] for col in column_info]
            
            # Skip header row, process data rows
            for row in rows[1:]:
                row_dict = {}
                for idx, col in enumerate(row['Data']):
                    col_name = column_names[idx] if idx < len(column_names) else f'col_{idx}'
                    row_dict[col_name] = col.get('VarCharValue', '')
                results.append(row_dict)
        else:
            # For subsequent pages, all rows are data
            column_info = result_set.get('ResultSetMetadata', {}).get('ColumnInfo', [])
            column_names = [col['Name'] for col in column_info]
            
            for row in rows:
                row_dict = {}
                for idx, col in enumerate(row['Data']):
                    col_name = column_names[idx] if idx < len(column_names) else f'col_{idx}'
                    row_dict[col_name] = col.get('VarCharValue', '')
                results.append(row_dict)
        
        # Check for more results
        next_token = response.get('NextToken')
        if not next_token:
            break
    
    logger.info(f"Retrieved {len(results)} result rows")
    return results