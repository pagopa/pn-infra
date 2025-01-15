import logging
import json
import boto3

# Import functions from modules
from monitoring.standard import create_standard_base_alarms
from monitoring.oncall import create_oncall_base_alarms
from monitoring.composite import create_composite_alarms
from monitoring.outputs import create_outputs_for_composite_alarms
from services.s3 import get_openapi_from_s3
from services.openapi import extract_monitoring_groups

logger = logging.getLogger()
logger.setLevel(logging.INFO)
apigateway_client = boto3.client("apigateway")

def handler(event, context):
    """
    Main handler function for the Lambda.

    Parameters
    ----------
    event : dict
        The event data passed to the Lambda function.
    context
        The runtime information of the Lambda function.

    Returns
    -------
    dict
        Response containing `requestId`, `status`, and `fragment` or `errorMessage`.

    Notes
    -----
    - Parses parameters from the event.
    - Retrieves the OpenAPI specification.
    - Extracts monitoring groups and composite mappings.
    - Creates standard and on-call alarms.
    - Creates composite alarms.
    - Returns the appropriate CloudFormation fragment based on the action parameter.
    """
    try:
        params = event.get("params", {})
        action = params.get("Action", "Resources").lower()
        bucket_name = params.get("OpenApiBucketName")
        bucket_key = params.get("OpenApiBucketKey")
        api_id = params.get("ApiGatewayId")
        api_stage = params.get("PublicRestApiStage")
        topic_arn = params.get("AlarmSNSTopicArn")
        microservice_name = params.get("MicroServiceUniqueName")
        intended_usage = params.get("IntendedUsage")
        alarm_on_4xx = params.get("AlarmOn4xx", "false")
        
        # Standard Alarms Parameters
        standard_api_error_threshold = int(params.get("StandardApiErrorThreshold", 1))
        standard_api_error_period = int(params.get("StandardApiErrorPeriod", 60))
        standard_api_error_stat = params.get("StandardApiErrorStat", "Sum")
        standard_api_error_comparison_operator = params.get("StandardApiErrorComparisonOperator", "GreaterThanThreshold")
        standard_api_error_missing_data = params.get("StandardApiErrorMissingData", "notBreaching")
        standard_datapoints = int(params.get("StandardApiErrorDataPointsToAlarm", 1))
        standard_periods = int(params.get("StandardApiErrorEvaluationPeriods", 5))

        # On-call Alarms Parameters
        oncall_api_error_count_threshold = int(params.get("OncallApiErrorCountThreshold", 25))
        oncall_api_error_5xx_threshold = float(params.get("OncallApiError5xxThreshold", 0.1))
        oncall_api_error_4xx_threshold = float(params.get("OncallApiError4xxThreshold", 0.9))
        oncall_api_error_period = int(params.get("OncallApiErrorPeriod", 300))
        oncall_api_error_stat = params.get("OncallApiErrorStat", "Average")
        oncall_api_error_count_stat = params.get("OncallApiErrorCountStat", "Sum")
        oncall_api_error_comparison_operator = params.get("OncallApiErrorComparisonOperator", "GreaterThanThreshold")
        oncall_api_error_missing_data = params.get("OncallApiErrorMissingData", "notBreaching")
        oncall_api_error_threshold = int(params.get("OncallApiErrorThreshold", 0))
        oncall_5xx_datapoints = int(params.get("OncallApiError5xxDataPointsToAlarm", 4))
        oncall_5xx_periods = int(params.get("OncallApiError5xxEvaluationPeriods", 12))
        oncall_4xx_datapoints = int(params.get("OncallApiError4xxDataPointsToAlarm", 4))
        oncall_4xx_periods = int(params.get("OncallApiError4xxEvaluationPeriods", 12))

        if not all([bucket_name, bucket_key, api_id, api_stage, microservice_name, intended_usage]):
            raise ValueError("Missing required parameters")

        response = apigateway_client.get_rest_api(restApiId=api_id)
        api_name = response.get('name')
        logger.info(f"Retrieved ApiName: {api_name}")

        openapi_dict = get_openapi_from_s3(bucket_name, bucket_key)
        monitoring_groups, composite_mappings = extract_monitoring_groups(openapi_dict)

        standard_alarms, standard_alarm_names_map = create_standard_base_alarms(
            monitoring_groups,
            api_name,
            api_stage,
            microservice_name,
            intended_usage,
            alarm_on_4xx,
            standard_datapoints,
            standard_periods,
            standard_api_error_threshold,
            standard_api_error_period,
            standard_api_error_stat,
            standard_api_error_comparison_operator,
            standard_api_error_missing_data
        )

        oncall_alarms, oncall_alarm_names_map = create_oncall_base_alarms(
            monitoring_groups,
            api_name,
            api_stage,
            microservice_name,
            intended_usage,
            alarm_on_4xx,
            oncall_5xx_datapoints,
            oncall_5xx_periods,
            oncall_4xx_datapoints,
            oncall_4xx_periods,
            oncall_api_error_count_threshold,
            oncall_api_error_5xx_threshold,
            oncall_api_error_4xx_threshold,
            oncall_api_error_period,
            oncall_api_error_stat,
            oncall_api_error_count_stat,
            oncall_api_error_comparison_operator,
            oncall_api_error_missing_data,
            oncall_api_error_threshold
        )

        base_alarms = {**standard_alarms, **oncall_alarms}

        composite_alarms = create_composite_alarms(
            composite_mappings,
            base_alarms,
            microservice_name,
            intended_usage,
            topic_arn,
            alarm_on_4xx,
            standard_alarm_names_map,
            oncall_alarm_names_map,
        )

        if action == 'resources':
            all_resources = {**base_alarms, **composite_alarms}
            logger.info(f"Final resources structure: {json.dumps(all_resources, indent=2)}")
            logger.info(f"Total resources generated: {len(all_resources)}")
            return {
                "requestId": event["requestId"],
                "status": "success",
                "fragment": all_resources,
            }
        elif action == 'outputs':
            outputs = create_outputs_for_composite_alarms(composite_alarms)
            logger.info(f"Final outputs structure: {json.dumps(outputs, indent=2)}")
            logger.info(f"Total outputs generated: {len(outputs)}")
            return {
                "requestId": event["requestId"],
                "status": "success",
                "fragment": outputs,
            }
        else:
            raise ValueError(f"Invalid Action parameter: {action}")
    except Exception as e:
        logger.error(f"Error in alarm creation: {str(e)}", exc_info=True)
        return {
            "requestId": event["requestId"],
            "status": "failure",
            "errorMessage": str(e),
        }
