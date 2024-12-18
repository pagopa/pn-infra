import json
import logging
from typing import Dict, List, Tuple

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def create_standard_base_alarms(
    monitoring_groups: Dict[str, List[dict]],
    api_name: str,
    api_stage: str,
    microservice_name: str,
    intended_usage: str,
    alarm_on_4xx: str,
    standard_datapoints: int,
    standard_periods: int,
    standard_api_error_threshold: int,
    standard_api_error_period: int,
    standard_api_error_stat: str,
    standard_api_error_comparison_operator: str,
    standard_api_error_missing_data: str
) -> Tuple[Dict[str, dict], Dict[str, Dict[str, List[str]]]]:
    """
    Creates standard base CloudWatch alarms for API endpoints.

    Parameters
    ----------
    monitoring_groups : Dict[str, List[dict]]
        Mapping of subgroup names to their endpoints.
    api_name : str
        The name of the API Gateway.
    api_stage : str
        The stage of the API Gateway.
    microservice_name : str
        Unique name of the microservice.
    intended_usage : str
        Intended usage description.
    alarm_on_4xx : str
        Flag to determine if 4XX alarms should be created ('true' or 'false').
    standard_datapoints : int
        Number of datapoints to alarm.
    standard_periods : int
        Number of evaluation periods.
    standard_api_error_threshold : int
        Threshold for triggering the alarm.
    standard_api_error_period : int
        Period over which the metric is evaluated.
    standard_api_error_stat : str
        Statistic to apply (e.g., 'Sum').
    standard_api_error_comparison_operator : str
        Comparison operator (e.g., 'GreaterThanThreshold').
    standard_api_error_missing_data : str
        How to treat missing data.

    Returns
    -------
    Tuple[Dict[str, dict], Dict[str, Dict[str, List[str]]]]
        - `standard_alarms`: Dictionary of CloudFormation alarm resources.
        - `standard_alarm_names_map`: Mapping of subgroup names to alarm names.

    Notes
    -----
    - Generates standard alarms for 5XX (and optionally 4XX) errors for each endpoint.
    - Groups endpoints into manageable chunks to stay within CloudWatch limits.

    Examples
    --------
    For 5XX errors, the expression might be:

    ```python
    "MAX([FILL(m_endpoint1, 0), FILL(m_endpoint2, 0), ...])"
    ```
    """
    standard_alarms = {}
    standard_alarm_names_map = {}
    MAX_OPERATIONS_PER_ALARM = 8
    for group_name, endpoints in monitoring_groups.items():
        alarm_names_5xx = []
        alarm_names_4xx = []
        for j in range(0, len(endpoints), MAX_OPERATIONS_PER_ALARM):
            chunk = endpoints[j: j + MAX_OPERATIONS_PER_ALARM]
            suffix = f"-{str(j // MAX_OPERATIONS_PER_ALARM).zfill(2)}" if j > 0 else ""
            current_group_name = f"{group_name}{suffix}"
            cleaned_group_name = "".join(c for c in current_group_name if c.isalnum())
            
            metrics_5xx = []
            metric_ids = []
            for endpoint in chunk:
                operation_id = endpoint.get("operationId", f"{endpoint['method']}{endpoint['path']}")
                operation_id_clean = "".join(c for c in operation_id if c.isalnum())
                metric_id = f"m_{operation_id_clean}"
                metric_ids.append(metric_id)
                
                metrics_5xx.append({
                    "Id": metric_id,
                    "MetricStat": {
                        "Metric": {
                            "Namespace": "AWS/ApiGateway",
                            "MetricName": "5XXError",
                            "Dimensions": [
                                {"Name": "ApiName", "Value": api_name},
                                {"Name": "Stage", "Value": api_stage},
                                {"Name": "Resource", "Value": endpoint["path"]},
                                {"Name": "Method", "Value": endpoint["method"]},
                            ],
                        },
                        "Period": standard_api_error_period,
                        "Stat": standard_api_error_stat,
                    },
                    "ReturnData": False,
                })

            standard_5xx_metrics = metrics_5xx.copy()
            standard_5xx_metrics.append({
                "Id": "max_errors",
                "Expression": f"MAX([{','.join(f'FILL({metric_id}, 0)' for metric_id in metric_ids)}])",
                "Label": "Max 5XX Errors",
                "ReturnData": True,
            })

            standard_alarm_name = f"Standard5xxAlarm{cleaned_group_name}"
            standard_alarm_full_name = f"child-{microservice_name}-{intended_usage}-{current_group_name}-5xx-ApiGwAlarm"
            standard_alarms[standard_alarm_name] = {
                "Type": "AWS::CloudWatch::Alarm",
                "Properties": {
                    "AlarmName": standard_alarm_full_name,
                    "AlarmDescription": f"Standard 5XX alarm for {current_group_name} endpoints",
                    "Metrics": standard_5xx_metrics,
                    "EvaluationPeriods": standard_periods,
                    "DatapointsToAlarm": standard_datapoints,
                    "Threshold": standard_api_error_threshold,
                    "ComparisonOperator": standard_api_error_comparison_operator,
                    "TreatMissingData": standard_api_error_missing_data,
                },
            }
            alarm_names_5xx.append(standard_alarm_full_name)

            if alarm_on_4xx.lower() == "true":
                metrics_4xx = []
                metric_ids_4xx = []
                for endpoint in chunk:
                    operation_id = endpoint.get("operationId", f"{endpoint['method']}{endpoint['path']}")
                    operation_id_clean = "".join(c for c in operation_id if c.isalnum())
                    metric_id = f"m_{operation_id_clean}"
                    metric_ids_4xx.append(metric_id)
                    
                    metrics_4xx.append({
                        "Id": metric_id,
                        "MetricStat": {
                            "Metric": {
                                "Namespace": "AWS/ApiGateway",
                                "MetricName": "4XXError",
                                "Dimensions": [
                                    {"Name": "ApiName", "Value": api_name},
                                    {"Name": "Stage", "Value": api_stage},
                                    {"Name": "Resource", "Value": endpoint["path"]},
                                    {"Name": "Method", "Value": endpoint["method"]},
                                ],
                            },
                            "Period": standard_api_error_period,
                            "Stat": standard_api_error_stat,
                        },
                        "ReturnData": False,
                    })

                standard_4xx_metrics = metrics_4xx.copy()
                standard_4xx_metrics.append({
                    "Id": "max_errors",
                    "Expression": f"MAX([{','.join(f'FILL({metric_id}, 0)' for metric_id in metric_ids_4xx)}])",
                    "Label": "Max 4XX Errors",
                    "ReturnData": True,
                })

                standard_4xx_alarm_name = f"Standard4xxAlarm{cleaned_group_name}"
                standard_alarm_full_name = f"child-{microservice_name}-{intended_usage}-{current_group_name}-4xx-ApiGwAlarm"
                standard_alarms[standard_4xx_alarm_name] = {
                    "Type": "AWS::CloudWatch::Alarm",
                    "Properties": {
                        "AlarmName": standard_alarm_full_name,
                        "AlarmDescription": f"Standard 4XX alarm for {current_group_name} endpoints",
                        "Metrics": standard_4xx_metrics,
                        "EvaluationPeriods": standard_periods,
                        "DatapointsToAlarm": standard_datapoints,
                        "Threshold": standard_api_error_threshold,
                        "ComparisonOperator": standard_api_error_comparison_operator,
                        "TreatMissingData": standard_api_error_missing_data,
                    },
                }
                alarm_names_4xx.append(standard_alarm_full_name)
        standard_alarm_names_map[group_name] = {
            "5xx": alarm_names_5xx,
            "4xx": alarm_names_4xx,
        }
    logger.info(
        f"Created standard base alarms structure: {json.dumps(standard_alarms, indent=2)}"
    )
    logger.info(
        f"Standard alarm names map: {json.dumps(standard_alarm_names_map, indent=2)}"
    )
    logger.info(f"Total standard base alarms created: {len(standard_alarms)}")
    return standard_alarms, standard_alarm_names_map