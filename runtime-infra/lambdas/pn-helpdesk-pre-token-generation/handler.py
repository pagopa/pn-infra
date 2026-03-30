import os
import boto3
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource('dynamodb')
TABLE_NAME = os.environ.get('USER_ROLES_TABLE')

def handler(event, context):
    logger.info("Event received: %s", event)
    
    # Pre-Token Generation only supports V2.0 triggers for modifying claims in ID Token
    # We check if we are in the right block
    if event['triggerSource'] not in ["TokenGeneration_HostedAuth", "TokenGeneration_Authentication", "TokenGeneration_NewPasswordChallenge"]:
        logger.info("Trigger source %s not handled. Skipping.", event['triggerSource'])
        return event

    email = event['request']['userAttributes'].get('email')
    
    if not email:
        logger.warning("No email found in user attributes")
        return event

    try:
        table = dynamodb.Table(TABLE_NAME)
        response = table.get_item(Key={'email': email})
        
        item = response.get('item') or response.get('Item')
        
        if item and 'backoffice_tags' in item:
            tags = item['backoffice_tags']
            logger.info("Found backoffice_tags for user %s: %s", email, tags)
            
            # For V1.0 (old) and V2.0 (new) the structure differs slightly
            # Cognito Sync/Amplify prefers claims in the ID Token
            event['response']['claimsOverrideDetails'] = {
                'claimsToAddOrOverride': {
                    'custom:backoffice_tags': tags
                }
            }
        else:
            logger.info("No profiling found for user %s", email)
            
    except Exception as e:
        logger.error("Error querying DynamoDB for user %s: %s", email, str(e))
        # We don't block login if profiling fails, but we don't add claims
        
    return event
