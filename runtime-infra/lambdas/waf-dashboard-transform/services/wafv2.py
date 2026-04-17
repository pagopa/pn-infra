import logging
from typing import List, Tuple

import boto3


logger = logging.getLogger(__name__)


def _parse_log_group_arn(destination_arn: str) -> Tuple[str, str]:
    if ":log-group:" not in destination_arn:
        return "", ""

    prefix, log_group_name = destination_arn.split(":log-group:", 1)
    prefix_parts = prefix.split(":")
    log_region = prefix_parts[3] if len(prefix_parts) > 3 else ""

    if log_group_name.endswith(":*"):
        log_group_name = log_group_name[:-2]

    return log_group_name, log_region


def discover_regional_web_acls(region: str) -> List[dict]:
    client = boto3.client("wafv2", region_name=region)

    discovered_acls = []
    next_marker = None

    while True:
        request = {
            "Scope": "REGIONAL",
            "Limit": 100,
        }
        if next_marker:
            request["NextMarker"] = next_marker

        response = client.list_web_acls(**request)

        for acl in response.get("WebACLs", []):
            log_group_name = ""
            log_region = region

            try:
                logging_configuration = client.get_logging_configuration(ResourceArn=acl["ARN"])
                destinations = (
                    logging_configuration.get("LoggingConfiguration", {})
                    .get("LogDestinationConfigs", [])
                )
                if destinations:
                    log_group_name, discovered_log_region = _parse_log_group_arn(destinations[0])
                    log_region = discovered_log_region or region
            except Exception as exc:
                logger.info(
                    "No log destination discovered for WAF %s in %s: %s",
                    acl.get("Name"),
                    region,
                    str(exc),
                )

            discovered_acls.append(
                {
                    "name": acl["Name"],
                    "web_acl_name": acl["Name"],
                    "region": region,
                    "has_logging": bool(log_group_name),
                    "log_group_name": log_group_name,
                    "log_region": log_region,
                }
            )

        next_marker = response.get("NextMarker")
        if not next_marker:
            break

    return sorted(discovered_acls, key=lambda item: item["name"].lower())
