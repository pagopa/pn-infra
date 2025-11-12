"""Configuration module for Athena Query Executor Lambda"""
import os
import sys
import logging

logger = logging.getLogger()

def setup_logger(aws_request_id):
    """
    Configure custom log formatter required by lambda-alarms metric filter.
    Produces format: timestamp aws_request_id level message
    The metric filter pattern [w1, w2, w3="ERROR", w4] requires ERROR at position 3.
    """
    root = logging.getLogger()
    for h in root.handlers[:]:
        root.removeHandler(h)
    
    fmt = "%(asctime)s %(aws_request_id)s %(levelname)s %(message)s"
    formatter = logging.Formatter(fmt=fmt, datefmt='%Y-%m-%dT%H:%M:%S')
    
    sh = logging.StreamHandler(sys.stdout)
    sh.setLevel(logging.INFO)
    sh.setFormatter(formatter)
    sh.addFilter(lambda record: setattr(record, 'aws_request_id', aws_request_id) or True)
    
    root.addHandler(sh)
    root.setLevel(logging.INFO)

# Module-level configuration from environment variables
CONFIG_GIT_URL = os.environ.get('CONFIG_GIT_URL', '').strip()
OUTPUT_S3_BUCKET = os.environ['OUTPUT_S3_BUCKET']
CSV_S3_PREFIX = os.environ.get('CSV_S3_PREFIX', 'athena_query_results')
ATHENA_RESULTS_BUCKET = os.environ['ATHENA_RESULTS_BUCKET']
ATHENA_DATABASE = os.environ['ATHENA_DATABASE']
ATHENA_WORKGROUP = os.environ['ATHENA_WORKGROUP']
MAX_WORKERS = int(os.environ.get('MAX_WORKERS', '10'))

# Validate required configuration at startup
if not all([CONFIG_GIT_URL, OUTPUT_S3_BUCKET, ATHENA_RESULTS_BUCKET, ATHENA_DATABASE, ATHENA_WORKGROUP]):
    raise ValueError("Missing required environment variables")