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

CONFIG_SSM_PARAM = os.environ['CONFIG_SSM_PARAMETER_NAME']
CONFIG_GIT_URL = os.environ.get('CONFIG_GIT_URL', '').strip()
CONFIG_GIT_REF = os.environ.get('CONFIG_GIT_REF', 'main').strip()
TABLE_LIST = os.environ['TABLE_LIST']
OUTPUT_BUCKET = os.environ['OUTPUT_S3_BUCKET']
ATHENA_RESULTS_BUCKET = os.environ['ATHENA_RESULTS_BUCKET']
DATABASE = os.environ['ATHENA_DATABASE']
WORKGROUP = os.environ['ATHENA_WORKGROUP']
MAX_WORKERS = int(os.environ['MAX_WORKERS'])

if not all([CONFIG_SSM_PARAM, TABLE_LIST, OUTPUT_BUCKET, ATHENA_RESULTS_BUCKET, DATABASE, WORKGROUP]):
    raise ValueError("Missing required environment variables")