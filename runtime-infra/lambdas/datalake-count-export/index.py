from handler import process_daily_count

def handler(event, context):
    return process_daily_count(event, context)