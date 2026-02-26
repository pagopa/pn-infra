import boto3
import os
import logging
from datetime import datetime
from datetime import timedelta

def lambda_handler(event, context):
    dynamodb = boto3.client('dynamodb')
    dynamo_table_names = os.environ['DynamoDbExportTableNames'].split(',')
    s3_bucket = os.environ['S3Bucket']
    prefix = os.environ['Prefix']
    region = os.environ['Region']
    accountid = os.environ['AccountID']
    current_date = datetime.now().strftime('%Y%m%d')
    yesterday_date= (datetime.strptime(current_date, '%Y%m%d') - timedelta(days=1)).strftime('%Y%m%d')

    for dynamo_table_name in dynamo_table_names:
        dynamo_table_arn = f"arn:aws:dynamodb:{region}:{accountid}:table/{dynamo_table_name}"
        s3_full_prefix = dynamo_table_name + "/" + prefix + "/" + yesterday_date
        now = datetime.now()
        to_time = now.replace(hour=0, minute=0, second=0, microsecond=0)
        from_time = to_time - timedelta(days=1)
        try:
            dynamodb.export_table_to_point_in_time(
                        TableArn=dynamo_table_arn,
                        S3Bucket=s3_bucket,
                        S3Prefix=s3_full_prefix,
                        ExportFormat='DYNAMODB_JSON',
                        ExportType='INCREMENTAL_EXPORT',
                        IncrementalExportSpecification={
                            'ExportFromTime': from_time,
                            'ExportToTime': to_time,
                            'ExportViewType': 'NEW_IMAGE'
                        }
                    )
            print(f"Tabella '{dynamo_table_name}' export start.")
        except Exception as e:
            print(f"Error during l'export of table '{dynamo_table_name}': {e}")
