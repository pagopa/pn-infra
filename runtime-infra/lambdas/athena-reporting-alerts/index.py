"""Lambda entry point for Athena Query Executor"""
from handler import lambda_handler

def handler(event, context):
    """Lambda entry point - delegates to business logic handler"""
    return lambda_handler(event, context)