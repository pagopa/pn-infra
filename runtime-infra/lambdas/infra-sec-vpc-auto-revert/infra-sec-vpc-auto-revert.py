import json
import json
import os
from datetime import datetime, timezone

import boto3

ec2 = boto3.client("ec2")
sns = boto3.client("sns")
ssm = boto3.client("ssm")

SNS_TOPIC_ARN = os.environ.get("SNS_TOPIC_ARN")
ENVIRONMENT = os.environ.get("ENVIRONMENT", "Missing")

# Optional SSM Parameter Store path holding a JSON denylist that OVERRIDES the
# env defaults below at runtime. This lets the rules be enriched without a
# redeploy. Expected JSON shape (all keys optional):
#   {
#     "dangerousPorts": [22, 3389],
#     "publicCidrs": ["0.0.0.0/0", "::/0"],
#     "revertAllPortsPublic": true,
#     "monitoredSecurityGroups": ["sg-123", "sg-456"]
#   }
RULES_SSM_PARAMETER = os.environ.get("RULES_SSM_PARAMETER", "").strip()


def _default_config():
    """Baseline denylist config from environment variables."""
    return {
        "dangerousPorts": [
            int(p.strip())
            for p in os.environ.get("DANGEROUS_PORTS", "22,3389").split(",")
            if p.strip().isdigit()
        ],
        "publicCidrs": [
            c.strip()
            for c in os.environ.get("PUBLIC_CIDRS", "0.0.0.0/0").split(",")
            if c.strip()
        ],
        "revertAllPortsPublic": os.environ.get("REVERT_ALL_PORTS_PUBLIC", "false").lower()
        == "true",
        "monitoredSecurityGroups": [
            sg.strip()
            for sg in os.environ.get("MONITORED_SECURITY_GROUPS", "").split(",")
            if sg.strip()
        ],
    }


def _load_config():
    """Return the effective denylist config: env defaults overridden by the
    optional SSM parameter (read at every invocation so changes apply live)."""
    config = _default_config()
    if not RULES_SSM_PARAMETER:
        return config
    try:
        raw = ssm.get_parameter(Name=RULES_SSM_PARAMETER)["Parameter"]["Value"]
        overrides = json.loads(raw)
    except ssm.exceptions.ParameterNotFound:
        return config
    except Exception as exc:  # noqa: BLE001 - fall back to defaults on any error
        print(f"Could not load rules from SSM {RULES_SSM_PARAMETER}: {exc}")
        return config

    if isinstance(overrides.get("dangerousPorts"), list):
        config["dangerousPorts"] = [int(p) for p in overrides["dangerousPorts"]]
    if isinstance(overrides.get("publicCidrs"), list):
        config["publicCidrs"] = [str(c) for c in overrides["publicCidrs"]]
    if isinstance(overrides.get("revertAllPortsPublic"), bool):
        config["revertAllPortsPublic"] = overrides["revertAllPortsPublic"]
    if isinstance(overrides.get("monitoredSecurityGroups"), list):
        config["monitoredSecurityGroups"] = [
            str(sg) for sg in overrides["monitoredSecurityGroups"]
        ]
    return config


def _now():
    return datetime.now(timezone.utc).isoformat()


def _notify(subject, body):
    if not SNS_TOPIC_ARN:
        print("SNS_TOPIC_ARN not configured, skipping notification")
        return
    sns.publish(TopicArn=SNS_TOPIC_ARN, Subject=subject[:100], Message=body)


def _is_dangerous_rule(item, config):
    """Evaluate a created security group rule (from CloudTrail responseElements)
    and return (is_dangerous, reason)."""
    cidr = item.get("cidrIpv4") or item.get("cidrIpv6")
    if not cidr or cidr not in config["publicCidrs"]:
        return False, None

    protocol = str(item.get("ipProtocol"))
    from_port = item.get("fromPort")
    to_port = item.get("toPort")
    revert_all = config["revertAllPortsPublic"]

    # All protocols/all ports open to the world.
    if protocol == "-1":
        if revert_all:
            return True, f"all traffic open to {cidr}"
        return False, None

    # Missing port range on a specific protocol means all ports for that protocol.
    if from_port is None or to_port is None:
        if revert_all:
            return True, f"all {protocol} ports open to {cidr}"
        return False, None

    for port in config["dangerousPorts"]:
        if from_port <= port <= to_port:
            return True, f"port {port} ({protocol}) open to {cidr}"

    # A very wide public port range is also treated as dangerous.
    if revert_all and from_port == 0 and to_port >= 65535:
        return True, f"full port range open to {cidr}"

    return False, None


def _collect_dangerous_rule_ids(detail, config):
    """Return (ingress_ids, egress_ids, reasons) for the created rules that match
    the dangerous denylist criteria."""
    ingress_ids = []
    egress_ids = []
    reasons = []
    response = detail.get("responseElements") or {}
    rule_set = (response.get("securityGroupRuleSet") or {}).get("items") or []
    for item in rule_set:
        rule_id = item.get("securityGroupRuleId")
        if not rule_id:
            continue
        dangerous, reason = _is_dangerous_rule(item, config)
        if not dangerous:
            continue
        reasons.append(f"{rule_id}: {reason}")
        if item.get("isEgress"):
            egress_ids.append(rule_id)
        else:
            ingress_ids.append(rule_id)
    return ingress_ids, egress_ids, reasons


def lambda_handler(event, context):
    detail = event.get("detail", {}) if isinstance(event, dict) else {}
    event_name = detail.get("eventName", "")
    group_id = (detail.get("requestParameters") or {}).get("groupId")
    user_identity = detail.get("userIdentity") or {}
    actor_arn = user_identity.get("arn", "Unknown")
    source_ip = detail.get("sourceIPAddress", "Unknown")
    region = detail.get("awsRegion", "Unknown")
    event_id = detail.get("eventID", "Unknown")

    print(f"Processing {event_name} on {group_id} by {actor_arn}")

    if event_name not in ("AuthorizeSecurityGroupIngress", "AuthorizeSecurityGroupEgress"):
        print(f"Event {event_name} is not revertable, ignoring")
        return {"reverted": False, "reason": "event-not-revertable"}

    config = _load_config()
    monitored_sgs = config["monitoredSecurityGroups"]

    # Out-of-scope security groups: notify only.
    if monitored_sgs and group_id not in monitored_sgs:
        _notify(
            f"[{ENVIRONMENT}] VPC SG Change (out of scope - not reverted)",
            (
                f"Security Group change detected on a group that is not in the auto-revert scope.\n"
                f"Environment: {ENVIRONMENT}\n"
                f"Security Group: {group_id}\n"
                f"Operation: {event_name}\n"
                f"Principal: {actor_arn}\n"
                f"Source IP: {source_ip}\n"
                f"Region: {region}\n"
                f"Time: {_now()}\n"
                f"CloudTrail Event ID: {event_id}\n"
            ),
        )
        return {"reverted": False, "reason": "out-of-scope"}

    ingress_ids, egress_ids, reasons = _collect_dangerous_rule_ids(detail, config)

    # No dangerous rule matched the denylist: notify only, do NOT revert.
    if not ingress_ids and not egress_ids:
        _notify(
            f"[{ENVIRONMENT}] VPC SG Change detected (no revert - not dangerous)",
            (
                f"Security Group change detected but NOT reverted (does not match the dangerous denylist).\n"
                f"Environment: {ENVIRONMENT}\n"
                f"Security Group: {group_id}\n"
                f"Operation: {event_name}\n"
                f"Principal: {actor_arn}\n"
                f"Source IP: {source_ip}\n"
                f"Region: {region}\n"
                f"Time: {_now()}\n"
                f"CloudTrail Event ID: {event_id}\n"
            ),
        )
        return {"reverted": False, "reason": "not-dangerous"}

    reverted = []
    errors = []
    try:
        if ingress_ids:
            ec2.revoke_security_group_ingress(
                GroupId=group_id, SecurityGroupRuleIds=ingress_ids
            )
            reverted.extend(ingress_ids)
        if egress_ids:
            ec2.revoke_security_group_egress(
                GroupId=group_id, SecurityGroupRuleIds=egress_ids
            )
            reverted.extend(egress_ids)
    except Exception as exc:  # noqa: BLE001 - report any failure via SNS
        errors.append(str(exc))
        print(f"Error reverting rules on {group_id}: {exc}")

    if errors:
        _notify(
            f"[{ENVIRONMENT}] VPC SG Auto-Revert FAILED",
            (
                f"Attempted to revert a DANGEROUS Security Group rule but FAILED.\n"
                f"Manual investigation required.\n"
                f"Environment: {ENVIRONMENT}\n"
                f"Security Group: {group_id}\n"
                f"Operation: {event_name}\n"
                f"Principal: {actor_arn}\n"
                f"Source IP: {source_ip}\n"
                f"Region: {region}\n"
                f"Dangerous rules: {'; '.join(reasons)}\n"
                f"Errors: {'; '.join(errors)}\n"
                f"Time: {_now()}\n"
                f"CloudTrail Event ID: {event_id}\n"
            ),
        )
        return {"reverted": False, "reason": "revoke-error", "errors": errors}

    _notify(
        f"[{ENVIRONMENT}] VPC SG Auto-Revert executed (dangerous rule)",
        (
            f"A DANGEROUS Security Group rule was automatically reverted.\n"
            f"Environment: {ENVIRONMENT}\n"
            f"Security Group: {group_id}\n"
            f"Operation: {event_name}\n"
            f"Principal: {actor_arn}\n"
            f"Source IP: {source_ip}\n"
            f"Region: {region}\n"
            f"Reverted (reason): {'; '.join(reasons)}\n"
            f"Time: {_now()}\n"
            f"CloudTrail Event ID: {event_id}\n"
        ),
    )
    print(f"Reverted dangerous rules on {group_id}: {reverted}")
    return {"reverted": True, "ruleIds": reverted, "reasons": reasons}
