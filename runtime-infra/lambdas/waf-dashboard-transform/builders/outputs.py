from typing import Dict, List

from utils.naming import build_detail_logical_id, sanitize_logical_id


def build_summary_outputs(
    project_name: str,
    dashboard_prefix: str,
    waf_configs: List[dict],
) -> Dict[str, dict]:
    return {
        "SummaryDashboardName": {
            "Description": "Name of the WAF hub summary dashboard",
            "Value": {"Ref": "WafHubSummaryDashboard"},
        },
        "DiscoveredRegionalWafCount": {
            "Description": "Number of REGIONAL WAF Web ACLs discovered during deploy-time macro execution",
            "Value": str(len(waf_configs)),
        },
        "DiscoveredRegionalWafNames": {
            "Description": "Comma separated list of REGIONAL WAF Web ACL names discovered during deploy-time macro execution",
            "Value": ",".join([waf["name"] for waf in waf_configs]),
        },
    }


def build_detail_outputs(
    project_name: str,
    dashboard_detail_prefix: str,
    waf_configs: List[dict],
) -> Dict[str, dict]:
    outputs = {}
    for waf in waf_configs:
        logical_id = build_detail_logical_id(waf["web_acl_name"])
        output_key = f"DetailDashboard{sanitize_logical_id(waf['web_acl_name'])}Name"
        outputs[output_key] = {
            "Description": f"Detail dashboard name for WAF {waf['name']}",
            "Value": {"Ref": logical_id},
        }
    return outputs
