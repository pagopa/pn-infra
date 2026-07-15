import json
import os
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError

ec2 = boto3.client("ec2")
sns = boto3.client("sns")
ssm = boto3.client("ssm")

SNS_TOPIC_ARN = os.environ.get("SNS_TOPIC_ARN")
ENVIRONMENT = os.environ.get("ENVIRONMENT", "Missing")

# SSM Parameter Store path holding the JSON denylist config. This is the ONLY
# source of configuration: it can be edited at runtime to enrich the rules
# without redeploying the Lambda. Expected JSON shape (all keys optional except
# that dangerousPorts/publicCidrs must be set for anything to be reverted):
#   {
#     "dangerousPorts": [22],
#     "publicCidrs": ["0.0.0.0/0", "::/0"],
#     "revertAllPortsPublic": true,
#     "monitoredSecurityGroups": ["sg-123", "sg-456"]
#   }
RULES_SSM_PARAMETER = os.environ.get("RULES_SSM_PARAMETER", "").strip()


def _parse_config(raw):
    """Normalize the JSON denylist read from SSM into the internal config shape."""
    data = json.loads(raw)
    return {
        "dangerousPorts": [int(p) for p in data.get("dangerousPorts", [])],
        "publicCidrs": [str(c) for c in data.get("publicCidrs", [])],
        "revertAllPortsPublic": bool(data.get("revertAllPortsPublic", False)),
        "monitoredSecurityGroups": [
            str(sg) for sg in data.get("monitoredSecurityGroups", [])
        ],
    }


def _load_config():
    """Return the denylist config read from the SSM parameter, or None if it is
    not configured / missing / invalid. In that case the caller must skip the
    revert and a clear error is logged."""
    if not RULES_SSM_PARAMETER:
        print(
            "ERROR: RULES_SSM_PARAMETER env var is not set. Cannot load the "
            "auto-revert denylist. No rule will be reverted."
        )
        return None
    try:
        raw = ssm.get_parameter(Name=RULES_SSM_PARAMETER)["Parameter"]["Value"]
        return _parse_config(raw)
    except ssm.exceptions.ParameterNotFound:
        print(
            f"ERROR: SSM parameter '{RULES_SSM_PARAMETER}' not found. Create it "
            f"with the denylist JSON (e.g. "
            f'{{"dangerousPorts":[22],"publicCidrs":["0.0.0.0/0","::/0"]}}). '
            f"No rule will be reverted until it exists."
        )
        return None
    except Exception as exc:  # noqa: BLE001 - never revert on config problems
        print(
            f"ERROR: could not load/parse SSM parameter '{RULES_SSM_PARAMETER}': "
            f"{exc}. No rule will be reverted."
        )
        return None


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
    """Return (ingress_ids, reasons) for the created INGRESS rules that match the
    dangerous denylist criteria. Egress rules are intentionally ignored: opening
    outbound traffic to 0.0.0.0/0 is legitimate and must never be reverted."""
    ingress_ids = []
    reasons = []
    response = detail.get("responseElements") or {}
    rule_set = (response.get("securityGroupRuleSet") or {}).get("items") or []
    for item in rule_set:
        rule_id = item.get("securityGroupRuleId")
        if not rule_id:
            continue
        # Skip egress rules entirely.
        if item.get("isEgress"):
            continue
        dangerous, reason = _is_dangerous_rule(item, config)
        if not dangerous:
            continue
        reasons.append(f"{rule_id}: {reason}")
        ingress_ids.append(rule_id)
    return ingress_ids, reasons


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

    # Only ingress rule additions are in scope for auto-revert. Egress rules
    # (typically 0.0.0.0/0 on all ports) are legitimate and never reverted.
    if event_name != "AuthorizeSecurityGroupIngress":
        print(f"Event {event_name} is not revertable, ignoring")
        return {"reverted": False, "reason": "event-not-revertable"}

    config = _load_config()

    # No usable config (SSM parameter missing/invalid): a clear error was already
    # logged. Notify and skip the revert so we never act on an unknown policy.
    if config is None:
        _notify(
            f"[{ENVIRONMENT}] VPC SG Auto-Revert MISCONFIGURED (no revert)",
            (
                f"Auto-revert could not run because the SSM denylist parameter "
                f"'{RULES_SSM_PARAMETER}' is missing or invalid.\n"
                f"Create/fix it with the denylist JSON. No rule was reverted.\n"
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
        return {"reverted": False, "reason": "config-missing"}

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

    ingress_ids, reasons = _collect_dangerous_rule_ids(detail, config)

    # No dangerous rule matched the denylist: notify only, do NOT revert.
    if not ingress_ids:
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
        ec2.revoke_security_group_ingress(
            GroupId=group_id, SecurityGroupRuleIds=ingress_ids
        )
        reverted.extend(ingress_ids)
    except ClientError as exc:
        # The rule is already gone (e.g. duplicate EventBridge delivery, or it was
        # revoked in the meantime): treat as an idempotent no-op, not a failure.
        if exc.response.get("Error", {}).get("Code") == "InvalidSecurityGroupRuleId.NotFound":
            print(f"Rule(s) already revoked on {group_id}, nothing to do: {exc}")
            return {"reverted": False, "reason": "already-reverted"}
        errors.append(str(exc))
        print(f"Error reverting rules on {group_id}: {exc}")
    except Exception as exc:  # noqa: BLE001 - report any other failure via SNS
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
