import os
import boto3
import csv
import io
from datetime import datetime
from botocore.config import Config

s3 = boto3.client(
    's3',
    region_name=os.environ['Region'],
    config=Config(s3={'addressing_style': 'virtual'})
)
sns = boto3.client('sns')
sqs = boto3.client('sqs', region_name=os.environ['Region'])

def lambda_handler(event, context):
    s3_bucket = os.environ['S3Bucket']
    prefix = os.environ['Prefix']
    region = os.environ['Region']
    sns_topic_arn = os.environ['SnsTopicArn']
    presignedurltime = int(os.environ['PresignedUrlTime'])
    timestamp = datetime.now().strftime('%Y%m%d_%H%M')

    queue_name = os.environ['SqsDumpQueueName']
    visibility_timeout = int(os.environ.get('SqsDumpVisibilityTimeoutInSeconds', '300'))

    try:
        queue_url = sqs.get_queue_url(QueueName=queue_name)['QueueUrl']
    except Exception as e:
        print(f"Error getting URL for queue {queue_name}: {e}")
        queue_url = None

    all_messages = []
    presigned_url = None
    if queue_url:
        print(f"Reading messages from queue: {queue_name}")
        while True:
            response = sqs.receive_message(
                QueueUrl=queue_url,
                MaxNumberOfMessages=10,
                VisibilityTimeout=visibility_timeout,
                WaitTimeSeconds=10
            )
            msgs = response.get('Messages', [])
            if not msgs:
                break

            for m in msgs:
                all_messages.append({
                    'MessageId': m['MessageId'],
                    'Body': m['Body']
                })

        print(f"Found {len(all_messages)} messages.")

        if all_messages:
            csv_buffer = io.StringIO()
            # If all_messages is empty, DictWriter would fail, so we check here.
            headers = all_messages[0].keys()
            writer = csv.DictWriter(csv_buffer, fieldnames=headers)
            writer.writeheader()
            for msg in all_messages:
                writer.writerow(msg)

            safe_queue_name = queue_name.replace('/', '_')
            s3_key = f"{prefix}/CSV_{safe_queue_name}_{timestamp}.csv"
            s3.put_object(Bucket=s3_bucket, Key=s3_key, Body=csv_buffer.getvalue())

            presigned_url = s3.generate_presigned_url(
                ClientMethod='get_object',
                Params={'Bucket': s3_bucket, 'Key': s3_key},
                ExpiresIn=presignedurltime
            )

    subject = f"CSV {queue_name} {timestamp}"
    message = (
        f"SQS dump completed.\n\n"
        f"Messages found: {len(all_messages)}\n"
        f"CSV file: {presigned_url if (all_messages and presigned_url) else 'No messages available.'}"
    )

    sns.publish(
        TopicArn=sns_topic_arn,
        Subject=subject,
        Message=message
    )

    return {
        'statusCode': 200,
        'body': message
    }
