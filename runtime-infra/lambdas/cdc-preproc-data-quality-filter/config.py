"""Logging configuration for Firehose preprocessing Lambda."""

import logging
import sys


logger = logging.getLogger()


def setup_logger(aws_request_id):
    """
    Configure the log format required by lambda-alarms.

    Output format:
    timestamp aws_request_id level message

    Compatible with the metric filter:
    [w1, w2, w3="ERROR", w4]
    """
    root_logger = logging.getLogger()

    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    formatter = logging.Formatter(
        fmt="%(asctime)s %(aws_request_id)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setLevel(logging.INFO)
    stream_handler.setFormatter(formatter)

    stream_handler.addFilter(
        lambda record: setattr(
            record,
            "aws_request_id",
            aws_request_id,
        ) or True
    )

    root_logger.addHandler(stream_handler)
    root_logger.setLevel(logging.INFO)