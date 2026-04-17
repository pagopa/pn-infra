import json
from typing import Dict, List

from utils.naming import build_detail_dashboard_name, build_detail_logical_id, build_summary_dashboard_name


def _dashboard_link(region: str, dashboard_name: str) -> str:
    return f"https://{region}.console.aws.amazon.com/cloudwatch/home?region={region}#dashboards/dashboard/{dashboard_name}"


def build_detail_dashboard_resources(
    project_name: str,
    dashboard_prefix: str,
    dashboard_detail_prefix: str,
    waf_configs: List[dict],
    region: str,
    default_metric_period_seconds: int,
) -> Dict[str, dict]:
    summary_dashboard_name = build_summary_dashboard_name(project_name, dashboard_prefix)
    resources = {}

    for waf in waf_configs:
        logical_id = build_detail_logical_id(waf["web_acl_name"])
        dashboard_name = build_detail_dashboard_name(
            project_name,
            dashboard_detail_prefix,
            waf["web_acl_name"],
        )

        widgets = [
            {
                "type": "text",
                "x": 0,
                "y": 0,
                "width": 24,
                "height": 2,
                "properties": {
                    "markdown": (
                        f"[Back to WAF Hub]({_dashboard_link(region, summary_dashboard_name)}) | "
                        f"**{waf['name']}** — Regional WAF Detail"
                        f"{'' if waf.get('has_logging') else ' (Logging not enabled)'}"
                    )
                },
            },
            {
                "type": "metric",
                "x": 0,
                "y": 2,
                "width": 8,
                "height": 6,
                "properties": {
                    "title": "Allowed vs Blocked",
                    "region": waf["region"],
                    "stat": "Sum",
                    "period": default_metric_period_seconds,
                    "view": "timeSeries",
                    "stacked": True,
                    "metrics": [
                        [
                            "AWS/WAFV2",
                            "AllowedRequests",
                            "WebACL",
                            waf["web_acl_name"],
                            "Region",
                            waf["region"],
                            "Rule",
                            "ALL",
                            {"label": "Allowed", "color": "#2ca02c"},
                        ],
                        [
                            "AWS/WAFV2",
                            "BlockedRequests",
                            "WebACL",
                            waf["web_acl_name"],
                            "Region",
                            waf["region"],
                            "Rule",
                            "ALL",
                            {"label": "Blocked", "color": "#d62728"},
                        ],
                    ],
                },
            },
            {
                "type": "metric",
                "x": 8,
                "y": 2,
                "width": 8,
                "height": 6,
                "properties": {
                    "title": "Blocked Requests Over Time",
                    "region": waf["region"],
                    "stat": "Sum",
                    "period": default_metric_period_seconds,
                    "view": "timeSeries",
                    "metrics": [
                        [
                            "AWS/WAFV2",
                            "BlockedRequests",
                            "WebACL",
                            waf["web_acl_name"],
                            "Region",
                            waf["region"],
                            "Rule",
                            "ALL",
                            {"label": "Blocked", "color": "#d62728"},
                        ]
                    ],
                },
            },
            {
                "type": "metric",
                "x": 16,
                "y": 2,
                "width": 8,
                "height": 6,
                "properties": {
                    "title": "Counted Requests",
                    "region": waf["region"],
                    "stat": "Sum",
                    "period": default_metric_period_seconds,
                    "view": "timeSeries",
                    "metrics": [
                        [
                            "AWS/WAFV2",
                            "CountedRequests",
                            "WebACL",
                            waf["web_acl_name"],
                            "Region",
                            waf["region"],
                            "Rule",
                            "ALL",
                            {"label": "Counted", "color": "#ff7f0e"},
                        ]
                    ],
                },
            },
        ]

        if waf.get("has_logging") and waf.get("log_group_name"):
            log_group_name = waf["log_group_name"]
            log_region = waf.get("log_region", waf["region"])
            widgets.extend(
                [
                    {
                        "type": "log",
                        "x": 0,
                        "y": 8,
                        "width": 8,
                        "height": 6,
                        "properties": {
                            "title": "Blocked by Rule",
                            "region": log_region,
                            "view": "pie",
                            "query": f"SOURCE '{log_group_name}' | stats count(*) as Blocks by terminatingRuleId | sort Blocks desc | limit 10",
                        },
                    },
                    {
                        "type": "log",
                        "x": 8,
                        "y": 8,
                        "width": 8,
                        "height": 6,
                        "properties": {
                            "title": "Top Countries",
                            "region": log_region,
                            "view": "pie",
                            "query": f"SOURCE '{log_group_name}' | stats count(*) as Requests by httpRequest.country | sort Requests desc | limit 10",
                        },
                    },
                    {
                        "type": "log",
                        "x": 16,
                        "y": 8,
                        "width": 8,
                        "height": 6,
                        "properties": {
                            "title": "Top Client IPs",
                            "region": log_region,
                            "view": "table",
                            "query": f"SOURCE '{log_group_name}' | stats count(*) as Requests by httpRequest.clientIp | sort Requests desc | limit 15",
                        },
                    },
                    {
                        "type": "log",
                        "x": 0,
                        "y": 14,
                        "width": 12,
                        "height": 6,
                        "properties": {
                            "title": "Top Blocked URIs",
                            "region": log_region,
                            "view": "table",
                            "query": f"SOURCE '{log_group_name}' | stats count(*) as Requests by httpRequest.uri | sort Requests desc | limit 15",
                        },
                    },
                    {
                        "type": "log",
                        "x": 12,
                        "y": 14,
                        "width": 12,
                        "height": 6,
                        "properties": {
                            "title": "Recent Blocked Requests",
                            "region": log_region,
                            "view": "table",
                            "query": f"SOURCE '{log_group_name}' | sort @timestamp desc | display @timestamp, terminatingRuleId, httpRequest.clientIp, httpRequest.uri, httpRequest.country | limit 100",
                        },
                    },
                ]
            )
        else:
            widgets.append(
                {
                    "type": "text",
                    "x": 0,
                    "y": 8,
                    "width": 24,
                    "height": 4,
                    "properties": {
                        "markdown": "## WAF Logging Not Enabled\n\nLog-based analytics widgets are unavailable because this Web ACL does not expose a CloudWatch Logs destination discoverable at deploy time."
                    },
                }
            )

        resources[logical_id] = {
            "Type": "AWS::CloudWatch::Dashboard",
            "Properties": {
                "DashboardName": dashboard_name,
                "DashboardBody": json.dumps({"start": "-PT24H", "widgets": widgets}),
            },
        }

    return resources
