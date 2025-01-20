import json
import logging
from typing import Dict, List, Tuple

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def create_oncall_base_alarms(
    monitoring_groups: Dict[str, List[dict]],
    api_name: str,
    api_stage: str,
    microservice_name: str,
    intended_usage: str,
    alarm_on_4xx: str,
    oncall_5xx_datapoints: int,
    oncall_5xx_periods: int,
    oncall_4xx_datapoints: int,
    oncall_4xx_periods: int,
    oncall_api_error_count_threshold: int,
    oncall_api_error_5xx_threshold: float,
    oncall_api_error_4xx_threshold: float,
    oncall_api_error_period: int,
    oncall_api_error_stat: str,
    oncall_api_error_count_stat: str,
    oncall_api_error_comparison_operator: str,
    oncall_api_error_missing_data: str,
    oncall_api_error_threshold: int
) -> Tuple[Dict[str, dict], Dict[str, Dict[str, List[str]]]]:
    """
    Creates on-call base CloudWatch alarms for critical API monitoring.

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
    oncall_5xx_datapoints : int
        Number of datapoints to alarm for 5XX errors.
    oncall_5xx_periods : int
        Number of evaluation periods for 5XX errors.
    oncall_4xx_datapoints : int
        Number of datapoints to alarm for 4XX errors.
    oncall_4xx_periods : int
        Number of evaluation periods for 4XX errors.
    oncall_api_error_count_threshold : int
        Minimum request count threshold.
    oncall_api_error_5xx_threshold : float
        Error rate threshold for 5XX errors.
    oncall_api_error_4xx_threshold : float
        Error rate threshold for 4XX errors.
    oncall_api_error_period : int
        Period over which the metric is evaluated.
    oncall_api_error_stat : str
        Statistic to apply to error metrics.
    oncall_api_error_count_stat : str
        Statistic to apply to count metrics.
    oncall_api_error_comparison_operator : str
        Comparison operator for the alarm.
    oncall_api_error_missing_data : str
        How to treat missing data.
    oncall_api_error_threshold : int
        Threshold for triggering the alarm.

    Returns
    -------
    Tuple[Dict[str, dict], Dict[str, Dict[str, List[str]]]]
        - `oncall_alarms`: Dictionary of CloudFormation alarm resources.
        - `oncall_alarm_names_map`: Mapping of subgroup names to alarm names.

    Notes
    -----
    - Generates on-call alarms that monitor error rates exceeding specified thresholds, considering the request count.
    - Uses mathematical expressions to combine metrics for complex alarm conditions.

    Examples
    --------
    For 5XX errors, the expression might be:

    ```python
    "((FILL(count5xx_operation1,0) > 10) * (FILL(error5xx_operation1,0) > 0.1))"
    ```
    """
    oncall_alarms = {}
    oncall_alarm_names_map = {}
    MAX_OPERATIONS_PER_ALARM = 3
    for group_name, endpoints in monitoring_groups.items():
        alarm_names_5xx = []
        alarm_names_4xx = []
        for j in range(0, len(endpoints), MAX_OPERATIONS_PER_ALARM):
            chunk = endpoints[j: j + MAX_OPERATIONS_PER_ALARM]
            suffix = f"-{str(j // MAX_OPERATIONS_PER_ALARM).zfill(2)}" if j > 0 else ""
            current_group_name = f"{group_name}{suffix}"
            cleaned_group_name = "".join(c for c in current_group_name if c.isalnum())
            oncall_5xx_metrics = []
            condition_ids = []
            for i, endpoint in enumerate(chunk):
                operation_id = endpoint.get("operationId", f"{endpoint['method']}{endpoint['path']}")
                operation_id_clean = "".join(c for c in operation_id if c.isalnum())
                if not operation_id_clean:
                    operation_id_clean = f"op"
                oncall_5xx_metrics.append({
                    "Id": f"error5xx_{operation_id_clean}",
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
                        "Period": oncall_api_error_period,
                        "Stat": oncall_api_error_stat,
                    },
                    "ReturnData": False,
                })
                oncall_5xx_metrics.append({
                    "Id": f"count5xx_{operation_id_clean}",
                    "MetricStat": {
                        "Metric": {
                            "Namespace": "AWS/ApiGateway",
                            "MetricName": "Count",
                            "Dimensions": [
                                {"Name": "ApiName", "Value": api_name},
                                {"Name": "Stage", "Value": api_stage},
                                {"Name": "Resource", "Value": endpoint["path"]},
                                {"Name": "Method", "Value": endpoint["method"]},
                            ],
                        },
                        "Period": oncall_api_error_period,
                        "Stat": oncall_api_error_count_stat,
                    },
                    "ReturnData": False,
                })
                oncall_5xx_metrics.append({
                    "Id": f"e_{operation_id_clean}",
                    "Expression": f"((FILL(count5xx_{operation_id_clean},0) > {oncall_api_error_count_threshold}) * (FILL(error5xx_{operation_id_clean},0) > {oncall_api_error_5xx_threshold}))",
                    "Label": operation_id if operation_id else f"Operation {i}",
                    "ReturnData": False,
                })
                condition_ids.append(f"e_{operation_id_clean}")

            oncall_5xx_metrics.append({
                "Id": "error_condition",
                "Expression": f"MAX([{', '.join(condition_ids)}])",
                "Label": "5XX Error Condition",
                "ReturnData": True,
            })

            oncall_alarm_name = f"oncall5xxAlarm{cleaned_group_name}"
            oncall_alarm_full_name = f"childOC-{microservice_name}-{intended_usage}-{current_group_name}-5xx-ApiGwAlarm"
            oncall_alarms[oncall_alarm_name] = {
                "Type": "AWS::CloudWatch::Alarm",
                "Properties": {
                    "AlarmName": oncall_alarm_full_name,
                    "AlarmDescription": f"On-call 5XX alarm for {current_group_name} endpoints",
                    "Metrics": oncall_5xx_metrics,
                    "EvaluationPeriods": oncall_5xx_periods,
                    "DatapointsToAlarm": oncall_5xx_datapoints,
                    "Threshold": oncall_api_error_threshold,
                    "ComparisonOperator": oncall_api_error_comparison_operator,
                    "TreatMissingData": oncall_api_error_missing_data,
                },
            }
            alarm_names_5xx.append(oncall_alarm_full_name)

            oncall_4xx_metrics = []
            condition_ids_4xx = []
            for i, endpoint in enumerate(chunk):
                operation_id = endpoint.get("operationId", f"{endpoint['method']}{endpoint['path']}")
                operation_id_clean = "".join(c for c in operation_id if c.isalnum())
                if not operation_id_clean:
                    operation_id_clean = f"op"
                oncall_4xx_metrics.append({
                    "Id": f"error4xx_{operation_id_clean}",
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
                        "Period": oncall_api_error_period,
                        "Stat": oncall_api_error_stat,
                    },
                    "ReturnData": False,
                })
                oncall_4xx_metrics.append({
                    "Id": f"count4xx_{operation_id_clean}",
                    "MetricStat": {
                        "Metric": {
                            "Namespace": "AWS/ApiGateway",
                            "MetricName": "Count",
                            "Dimensions": [
                                {"Name": "ApiName", "Value": api_name},
                                {"Name": "Stage", "Value": api_stage},
                                {"Name": "Resource", "Value": endpoint["path"]},
                                {"Name": "Method", "Value": endpoint["method"]},
                            ],
                        },
                        "Period": oncall_api_error_period,
                        "Stat": oncall_api_error_count_stat,
                    },
                    "ReturnData": False,
                })
                oncall_4xx_metrics.append({
                    "Id": f"e_{operation_id_clean}",
                    "Expression": f"((FILL(count4xx_{operation_id_clean},0) > {oncall_api_error_count_threshold}) * (FILL(error4xx_{operation_id_clean},0) > {oncall_api_error_4xx_threshold}))",
                    "Label": operation_id if operation_id else f"Operation {i}",
                    "ReturnData": False,
                })
                condition_ids_4xx.append(f"e_{operation_id_clean}")

            oncall_4xx_metrics.append({
                "Id": "error_condition",
                "Expression": f"MAX([{', '.join(condition_ids_4xx)}])",
                "Label": "4XX Error Condition",
                "ReturnData": True,
            })

            oncall_4xx_alarm_name = f"oncall4xxAlarm{cleaned_group_name}"
            oncall_4xx_alarm_full_name = f"childOC-{microservice_name}-{intended_usage}-{current_group_name}-4xx-ApiGwAlarm"
            oncall_alarms[oncall_4xx_alarm_name] = {
                "Type": "AWS::CloudWatch::Alarm",
                "Properties": {
                    "AlarmName": oncall_4xx_alarm_full_name,
                    "AlarmDescription": f"On-call 4XX alarm for {current_group_name} endpoints",
                    "Metrics": oncall_4xx_metrics,
                    "EvaluationPeriods": oncall_4xx_periods,
                    "DatapointsToAlarm": oncall_4xx_datapoints,
                    "Threshold": oncall_api_error_threshold,
                    "ComparisonOperator": oncall_api_error_comparison_operator,
                    "TreatMissingData": oncall_api_error_missing_data,
                },
            }
            alarm_names_4xx.append(oncall_4xx_alarm_full_name)
        oncall_alarm_names_map[group_name] = {
            "5xx": alarm_names_5xx,
            "4xx": alarm_names_4xx,
        }
    logger.info(
        f"Created on-call base alarms structure: {json.dumps(oncall_alarms, indent=2)}"
    )
    logger.info(
        f"On-call alarm names map: {json.dumps(oncall_alarm_names_map, indent=2)}"
    )
    logger.info(f"Total on-call base alarms created: {len(oncall_alarms)}")
    return oncall_alarms, oncall_alarm_names_map