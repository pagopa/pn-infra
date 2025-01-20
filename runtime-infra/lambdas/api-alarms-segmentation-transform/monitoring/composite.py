import json
import logging
from typing import Dict, List, Set

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def create_composite_alarms(
    composite_mappings: Dict[str, Set[str]],
    base_alarms: Dict[str, dict],
    microservice_name: str,
    intended_usage: str,
    topic_arn: str,
    alarm_on_4xx: str,
    standard_alarm_names_map: Dict[str, Dict[str, List[str]]],
    oncall_alarm_names_map: Dict[str, Dict[str, List[str]]],
) -> Dict[str, dict]:
    """
    Creates composite CloudWatch alarms that aggregate multiple base alarms.

    Parameters
    ----------
    composite_mappings : Dict[str, Set[str]]
        Mapping of composite group names to subgroups.
    base_alarms : Dict[str, dict]
        Dictionary of all base alarms.
    microservice_name : str
        Unique name of the microservice.
    intended_usage : str
        Intended usage description.
    topic_arn : str
        SNS Topic ARN for alarm notifications.
    alarm_on_4xx : str
        Flag to determine if 4XX alarms should be created ('true' or 'false').
    standard_alarm_names_map : Dict[str, Dict[str, List[str]]]
        Mapping of subgroup names to standard alarm names.
    oncall_alarm_names_map : Dict[str, Dict[str, List[str]]]
        Mapping of subgroup names to on-call alarm names.

    Returns
    -------
    Dict[str, dict]
        `composite_alarms`: Dictionary of CloudFormation composite alarm resources.

    Notes
    -----
    - Aggregates multiple base alarms into composite alarms using logical OR conditions.
    - Sets up dependencies and actions for the composite alarms.
    """
    composite_alarms = {}
    for composite_group, subgroups in composite_mappings.items():
        cleaned_composite_name = "".join(c for c in composite_group if c.isalnum())
        # Composite 5XX Standard Alarm
        standard_5xx_alarm_names = []
        standard_dependencies = []
        for subgroup in subgroups:
            alarm_names = standard_alarm_names_map.get(subgroup, {}).get("5xx", [])
            standard_5xx_alarm_names.extend(alarm_names)
            cleaned_subgroup_name = "".join(c for c in subgroup if c.isalnum())
            for j in range(len(alarm_names)):
                suffix = f"{str(j).zfill(2)}" if j > 0 else ""
                standard_dependencies.append(
                    f"Standard5xxAlarm{cleaned_subgroup_name}{suffix}"
                )
        alarm_rules_5xx = [f'ALARM("{name}")' for name in standard_5xx_alarm_names]
        alarm_rule_5xx = f"({' OR '.join(alarm_rules_5xx)})"
        composite_alarm_name = f"Composite5xxAlarm{cleaned_composite_name}"
        composite_alarms[composite_alarm_name] = {
            "Type": "AWS::CloudWatch::CompositeAlarm",
            "DependsOn": standard_dependencies,
            "Properties": {
                "AlarmName": f"{microservice_name}-{intended_usage}-{composite_group}-comp-5xx-ApiGwAlarm",
                "AlarmDescription": f"Composite 5XX alarm for {composite_group} group",
                "AlarmRule": alarm_rule_5xx,
                "ActionsEnabled": True,
                "AlarmActions": [topic_arn],
                "OKActions": [topic_arn],
                "InsufficientDataActions": [topic_arn],
            },
        }
        # Composite 5XX On-call Alarm
        oncall_5xx_alarm_names = []
        oncall_dependencies = []
        for subgroup in subgroups:
            alarm_names = oncall_alarm_names_map.get(subgroup, {}).get("5xx", [])
            oncall_5xx_alarm_names.extend(alarm_names)
            cleaned_subgroup_name = "".join(c for c in subgroup if c.isalnum())
            for j in range(len(alarm_names)):
                suffix = f"{str(j).zfill(2)}" if j > 0 else ""
                oncall_dependencies.append(
                    f"oncall5xxAlarm{cleaned_subgroup_name}{suffix}"
                )
        oncall_alarm_rules_5xx = [f'ALARM("{name}")' for name in oncall_5xx_alarm_names]
        oncall_alarm_rule_5xx = f"({' OR '.join(oncall_alarm_rules_5xx)})"
        composite_oncall_alarm_name = f"oncallComposite5xxAlarm{cleaned_composite_name}"
        composite_alarms[composite_oncall_alarm_name] = {
            "Type": "AWS::CloudWatch::CompositeAlarm",
            "DependsOn": oncall_dependencies,
            "Properties": {
                "AlarmName": f"oncall-{microservice_name}-{intended_usage}-{composite_group}-comp-5xx-ApiGwAlarm",
                "AlarmDescription": f"On-call composite 5XX alarm for {composite_group} group",
                "AlarmRule": oncall_alarm_rule_5xx,
                "ActionsEnabled": True,
                "AlarmActions": [topic_arn],
                "OKActions": [topic_arn],
                "InsufficientDataActions": [topic_arn],
            },
        }
        # Standard 4XX composite alarms: only if alarm_on_4xx is true
        if alarm_on_4xx.lower() == "true":
            standard_4xx_alarm_names = []
            standard_4xx_dependencies = []
            for subgroup in subgroups:
                alarm_names = standard_alarm_names_map.get(subgroup, {}).get("4xx", [])
                standard_4xx_alarm_names.extend(alarm_names)
                cleaned_subgroup_name = "".join(c for c in subgroup if c.isalnum())
                for j in range(len(alarm_names)):
                    suffix = f"{str(j).zfill(2)}" if j > 0 else ""
                    standard_4xx_dependencies.append(
                        f"Standard4xxAlarm{cleaned_subgroup_name}{suffix}"
                    )
            alarm_rules_4xx = [f'ALARM("{name}")' for name in standard_4xx_alarm_names]
            alarm_rule_4xx = f"({' OR '.join(alarm_rules_4xx)})"
            composite_alarm_name_4xx = f"Composite4xxAlarm{cleaned_composite_name}"
            composite_alarms[composite_alarm_name_4xx] = {
                "Type": "AWS::CloudWatch::CompositeAlarm",
                "DependsOn": standard_4xx_dependencies,
                "Properties": {
                    "AlarmName": f"{microservice_name}-{intended_usage}-{composite_group}-comp-4xx-ApiGwAlarm",
                    "AlarmDescription": f"Composite 4XX alarm for {composite_group} group",
                    "AlarmRule": alarm_rule_4xx,
                    "ActionsEnabled": True,
                    "AlarmActions": [topic_arn],
                    "OKActions": [topic_arn],
                    "InsufficientDataActions": [topic_arn],
                },
            }
        oncall_4xx_alarm_names = []
        oncall_4xx_dependencies = []
        for subgroup in subgroups:
            alarm_names = oncall_alarm_names_map.get(subgroup, {}).get("4xx", [])
            oncall_4xx_alarm_names.extend(alarm_names)
            cleaned_subgroup_name = "".join(c for c in subgroup if c.isalnum())
            for j in range(len(alarm_names)):
                suffix = f"{str(j).zfill(2)}" if j > 0 else ""
                oncall_4xx_dependencies.append(
                    f"oncall4xxAlarm{cleaned_subgroup_name}{suffix}"
                )
        oncall_alarm_rules_4xx = [f'ALARM("{name}")' for name in oncall_4xx_alarm_names]
        oncall_alarm_rule_4xx = f"({' OR '.join(oncall_alarm_rules_4xx)})"
        composite_oncall_alarm_name_4xx = f"oncallComposite4xxAlarm{cleaned_composite_name}"
        composite_alarms[composite_oncall_alarm_name_4xx] = {
            "Type": "AWS::CloudWatch::CompositeAlarm",
            "DependsOn": oncall_4xx_dependencies,
            "Properties": {
                "AlarmName": f"oncall-{microservice_name}-{intended_usage}-{composite_group}-comp-4xx-ApiGwAlarm",
                "AlarmDescription": f"On-call composite 4XX alarm for {composite_group} group",
                "AlarmRule": oncall_alarm_rule_4xx,
                "ActionsEnabled": True,
                "AlarmActions": [topic_arn],
                "OKActions": [topic_arn],
                "InsufficientDataActions": [topic_arn],
            },
        }
    logger.info(
        f"Created composite alarms structure: {json.dumps(composite_alarms, indent=2)}"
    )
    logger.info(f"Total composite alarms created: {len(composite_alarms)}")
    return composite_alarms