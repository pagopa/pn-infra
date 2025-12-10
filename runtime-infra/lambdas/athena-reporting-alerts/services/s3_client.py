"""S3 service layer for CSV export"""
import boto3
import csv
from io import StringIO
from datetime import datetime, timezone
from config import logger, OUTPUT_S3_BUCKET, CSV_S3_PREFIX

s3 = boto3.client('s3')


def export_results_to_csv(query_id, results, execution_date, alert_name=None):
    """
    Export query results to CSV on S3
    
    Args:
        query_id: Query identifier
        results: List of result rows (list of dicts)
        execution_date: Execution date string (YYYY-MM-DD)
        alert_name: Optional alert name for alerts mode
    
    Returns:
        Dict with s3_path and presigned_url
    """
    logger.info(f"Exporting {len(results)} rows to CSV for query: {query_id}")
    
    # Build filename automatically
    timestamp = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')
    
    if alert_name:
        filename = f"{query_id}-{alert_name}-{execution_date}.csv"
    else:
        filename = f"{query_id}-{execution_date}.csv"
    
    # Build S3 path: prefix/query_id/YYYY/MM/DD/filename
    date_parts = execution_date.split('-')
    year, month, day = date_parts[0], date_parts[1], date_parts[2]
    
    s3_key = f"{CSV_S3_PREFIX}/{query_id}/{year}/{month}/{day}/{filename}"
    
    # Generate CSV content
    csv_buffer = StringIO()
    
    if results:
        # Use keys from first row as headers
        fieldnames = results[0].keys()
        writer = csv.DictWriter(csv_buffer, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)
    else:
        # Empty results, just write headers if available
        logger.warning(f"No results to export for query: {query_id}")
        csv_buffer.write("# No results\n")
    
    # Upload to S3
    try:
        s3.put_object(
            Bucket=OUTPUT_S3_BUCKET,
            Key=s3_key,
            Body=csv_buffer.getvalue().encode('utf-8'),
            ContentType='text/csv',
            Metadata={
                'query_id': query_id,
                'execution_date': execution_date,
                'record_count': str(len(results)),
                'timestamp': timestamp
            }
        )
        
        s3_path = f"s3://{OUTPUT_S3_BUCKET}/{s3_key}"
        
        # Generate presigned URL (valid for 3 days)
        presigned_url = s3.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': OUTPUT_S3_BUCKET,
                'Key': s3_key
            },
            ExpiresIn=259200  # 3 days (72 hours)
        )
        
        logger.info(f"CSV exported successfully to: {s3_path}")
        
        return {
            's3_path': s3_path,
            'presigned_url': presigned_url
        }
        
    except Exception as e:
        logger.error(f"Failed to export CSV to S3: {e}")
        raise RuntimeError(f"CSV export failed: {e}")