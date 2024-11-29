from typing import Dict

def create_outputs_for_composite_alarms(
    composite_alarms: Dict[str, dict]
) -> Dict[str, dict]:
    """
    Creates CloudFormation outputs for the composite alarms.

    Parameters
    ----------
    composite_alarms : Dict[str, dict]
        Dictionary of composite alarm resources.

    Returns
    -------
    Dict[str, dict]
        `outputs`: Dictionary of CloudFormation outputs.

    Notes
    -----
    - Generates outputs that export the ARNs of the composite alarms for use in other stacks or resources.
    """
    outputs = {}
    for alarm_key, alarm_resource in composite_alarms.items():
        output_key = "".join(c for c in alarm_key if c.isalnum())
        outputs[output_key] = {
            "Description": f"ARN of the alarm {alarm_key}",
            "Value": {"Fn::GetAtt": [alarm_key, "Arn"]},
            "Export": {"Name": {"Fn::Sub": f"${{AWS::StackName}}-{output_key}"}},
        }
    return outputs