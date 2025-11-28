"""Lambda entry point for Athena Schedule Manager"""
from schedule_manager import lambda_handler

def handler(event, context):
    """Lambda entry point - delegates to reconciliation logic"""
    return lambda_handler(event, context)