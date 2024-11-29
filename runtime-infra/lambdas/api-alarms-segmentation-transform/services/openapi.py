import json
import logging
from typing import Dict, List, Set, Tuple

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def extract_monitoring_groups(
    openapi_dict: dict,
) -> Tuple[Dict[str, List[dict]], Dict[str, Set[str]]]:
    """
    Extracts monitoring groups and composite mappings from the OpenAPI specification.

    Parameters
    ----------
    openapi_dict : dict
        The OpenAPI specification as a dictionary.

    Returns
    -------
    Tuple[Dict[str, List[dict]], Dict[str, Set[str]]]
        - `monitoring_groups`: A mapping of subgroup names to a list of endpoints.
        - `composite_mappings`: A mapping of composite group names to sets of subgroups.

    Notes
    -----
    - Parses the OpenAPI paths and methods to organize endpoints into monitoring groups and composite groups based on custom extensions and tags.
    """
    monitoring_groups = {}
    composite_mappings = {}
    paths = openapi_dict.get("paths", {})
    valid_methods = ["GET", "POST", "PUT", "DELETE", "PATCH"]  # Methods to include
    for path, path_info in paths.items():
        for method, method_info in path_info.items():
            if method.upper() not in valid_methods:
                logger.info(f"Skipping method {method.upper()} for path {path}")
                continue
            monitoring_group = method_info.get("x-pagopa-monitoring-group", "")
            tags = method_info.get("tags", [])
            operation_id = method_info.get("operationId", "")
            if monitoring_group == "<none>":
                logger.info(
                    f"x-pagopa-monitoring-group is '<none>' for {path} {method}, skipping operation"
                )
                continue  # Skip the operation
            elif monitoring_group:
                group_parts = monitoring_group.split("-")
                if len(group_parts) < 2:
                    logger.warning(
                        f"Invalid monitoring group format: {monitoring_group}"
                    )
                    continue
                composite_group = group_parts[0]
                subgroup = monitoring_group
            elif tags:
                # Fallback to tags if no monitoring group is specified
                tag = tags[0]
                composite_group = f"noextension-{tag}"
                subgroup = f"noextension-{tag}"
                logger.info(
                    f"No x-pagopa-monitoring-group for {path} {method}, using tag: {tag}"
                )
            else:
                # Skip the operation if no monitoring group or tags are provided
                logger.warning(
                    f"No x-pagopa-monitoring-group or tags for {path} {method}, skipping operation"
                )
                continue
            if subgroup not in monitoring_groups:
                monitoring_groups[subgroup] = []
            endpoint_info = {
                "path": path,
                "method": method.upper(),
                "operationId": operation_id,
            }
            if endpoint_info not in monitoring_groups[subgroup]:
                monitoring_groups[subgroup].append(endpoint_info)
            if composite_group not in composite_mappings:
                composite_mappings[composite_group] = set()
            composite_mappings[composite_group].add(subgroup)
    logger.info(
        f"Extracted monitoring groups: {json.dumps(monitoring_groups, indent=2)}"
    )
    logger.info(
        f"Extracted composite mappings: {json.dumps({k: list(v) for k, v in composite_mappings.items()}, indent=2)}"
    )
    logger.info(
        f"Total monitoring groups: {len(monitoring_groups)}, Total composite groups: {len(composite_mappings)}"
    )
    return monitoring_groups, composite_mappings
