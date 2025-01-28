import logging
import boto3
import yaml

logger = logging.getLogger()
logger.setLevel(logging.INFO)
s3_client = boto3.client("s3")

def get_openapi_from_s3(bucket: str, key: str) -> dict:
    """
    Retrieves an OpenAPI specification file from an S3 bucket and parses it into a dictionary.

    Parameters
    ----------
    bucket : str
        The name of the S3 bucket.
    key : str
        The key (path) to the OpenAPI file within the S3 bucket.

    Returns
    -------
    dict
        The parsed OpenAPI specification as a dictionary.

    Raises
    ------
    Exception
        If there is an error reading the OpenAPI file from S3.
    """
    try:
        response = s3_client.get_object(Bucket=bucket, Key=key)
        file_content = response["Body"].read().decode("utf-8")
        return yaml.safe_load(file_content)
    except Exception as e:
        logger.error(f"Error reading OpenAPI file from S3: {str(e)}")
        raise