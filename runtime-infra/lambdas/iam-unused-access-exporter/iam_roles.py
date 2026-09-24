"""IAM role metadata and trust-policy helpers."""

import json
from urllib.parse import unquote


def parse_role_name(resource):
    """Extract the IAM role name from a role ARN."""
    value = str(resource or "")
    marker = ":role/"
    if marker in value:
        role_part = value.split(marker, 1)[1]
        return role_part.strip("/").split("/")[-1]
    return ""


def get_role_trusted_services(*, iam_client, role_name, cache, logger):
    """Return service principals allowed by a role trust policy."""
    if role_name in cache:
        return cache[role_name]

    services = set()
    try:
        response = iam_client.get_role(RoleName=role_name)
        policy = (response.get("Role") or {}).get("AssumeRolePolicyDocument") or {}
        if isinstance(policy, str):
            policy = json.loads(unquote(policy))
        if not isinstance(policy, dict):
            raise ValueError("AssumeRolePolicyDocument is not an object")

        statements = policy.get("Statement", [])
        if isinstance(statements, dict):
            statements = [statements]
        if not isinstance(statements, list):
            raise ValueError("trust policy Statement is not an array")

        for statement in statements:
            if not isinstance(statement, dict) or str(statement.get("Effect", "")).casefold() != "allow":
                continue
            principal = statement.get("Principal")
            if not isinstance(principal, dict):
                continue
            service_principals = principal.get("Service", [])
            if isinstance(service_principals, str):
                service_principals = [service_principals]
            if isinstance(service_principals, list):
                services.update(
                    service.strip().casefold()
                    for service in service_principals
                    if isinstance(service, str) and service.strip()
                )
    except Exception as exc:
        logger.warning(json.dumps({
            "msg": "get_role failed during fine-grained exclusion check",
            "role_name": role_name,
            "error": str(exc),
        }))

    cache[role_name] = services
    return services


def resolve_microservice_tag(*, iam_client, resource, cache, enabled, logger):
    """Resolve and cache the microservice tag for an IAM role ARN."""
    if not enabled:
        return "no-tag"

    role_name = parse_role_name(resource)
    if not role_name:
        return "no-tag"
    if role_name in cache:
        return cache[role_name]

    microservice = ""
    try:
        response = iam_client.list_role_tags(RoleName=role_name)
        for tag in response.get("Tags", []):
            if str(tag.get("Key", "")).lower() == "microservice":
                microservice = str(tag.get("Value") or "").strip()
                break
    except Exception as exc:
        logger.warning(json.dumps({
            "msg": "list_role_tags failed",
            "role_name": role_name,
            "error": str(exc),
        }))

    if not microservice:
        microservice = "no-tag"
    cache[role_name] = microservice
    return microservice


def has_exclude_tag(*, iam_client, role_name, cache, tag_key, logger):
    """Check and cache whether a role has the configured exclusion tag."""
    cache_key = f"__exclude__{role_name}"
    if cache_key in cache:
        return cache[cache_key]

    result = False
    try:
        response = iam_client.list_role_tags(RoleName=role_name)
        for tag in response.get("Tags", []):
            if (
                str(tag.get("Key", "")) == tag_key
                and str(tag.get("Value", "")).lower() == "true"
            ):
                result = True
                break
    except Exception as exc:
        logger.warning(json.dumps({
            "msg": "list_role_tags failed (exclude check)",
            "role_name": role_name,
            "error": str(exc),
        }))

    cache[cache_key] = result
    return result
