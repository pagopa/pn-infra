import json
from typing import Dict, List

from utils.naming import build_detail_dashboard_name, build_summary_dashboard_name


_COLORS = [
    "#1f77b4",
    "#ff7f0e",
    "#2ca02c",
    "#d62728",
    "#9467bd",
    "#8c564b",
    "#e377c2",
    "#7f7f7f",
    "#bcbd22",
    "#17becf",
]

_Y_HEADER = 0
_Y_KPI = 2
_Y_TREND = 6
_Y_BAR = 14
_Y_AGG_HEADER = 22
_Y_AGG_ROW1 = 23
_Y_AGG_ROW1B = 31
_Y_AGG_ROW2 = 39
_Y_THREAT_HEADER = 55
_Y_THREAT_ROW = 56
_Y_THREAT_ROW2 = 64
_Y_RAW_HEADER = 72
_Y_RAW = 73

_PARSE_WAF_NAME = "parse webaclId '*/webacl/*/*' as _pfx, WebACL, _id"
_PARSE_ATTACK_TYPE = r'parse @message /\"conditionType\":\"(?<AttackType>[A-Z_]+)\"/'


def _dashboard_link(region: str, dashboard_name: str) -> str:
    return f"https://{region}.console.aws.amazon.com/cloudwatch/home?region={region}#dashboards/dashboard/{dashboard_name}"


def _build_log_source_by_region(all_with_logging: List[dict]) -> Dict[str, str]:
    regions = []
    for waf in all_with_logging:
        log_region = waf.get("log_region") or waf.get("region")
        if log_region not in regions:
            regions.append(log_region)

    sources = {}
    for region in regions:
        wafs = [waf for waf in all_with_logging if (waf.get("log_region") or waf.get("region")) == region]
        sources[region] = " | ".join(
            [f"SOURCE '{waf['log_group_name']}'" for waf in wafs[:50] if waf.get("log_group_name")]
        )
    return sources


def _summary_drilldown_markdown(
    project_name: str,
    dashboard_detail_prefix: str,
    waf_configs: List[dict],
    region: str,
) -> str:
    if not waf_configs:
        return "## Regional Web ACLs\n\nNo Regional Web ACLs found."

    lines = [
        "## Regional Web ACLs — Click to Open Detail Dashboard",
        "",
        "| # | Web ACL | Region | Logging | Detail Dashboard |",
        "|---|---------|--------|---------|------------------|",
    ]

    for index, waf in enumerate(waf_configs):
        detail_dashboard_name = build_detail_dashboard_name(
            project_name,
            dashboard_detail_prefix,
            waf["web_acl_name"],
        )
        lines.append(
            f"| {index + 1} | {waf['name']} | {waf['region']} | {'Yes' if waf.get('has_logging') else 'No'} | [Open Dashboard]({_dashboard_link(region, detail_dashboard_name)}) |"
        )

    return "\n".join(lines)


def build_summary_dashboard_resources(
    project_name: str,
    dashboard_prefix: str,
    dashboard_detail_prefix: str,
    waf_configs: List[dict],
    region: str,
    default_metric_period_seconds: int,
    max_sparkline_wafs: int,
) -> Dict[str, dict]:
    dashboard_name = build_summary_dashboard_name(project_name, dashboard_prefix)
    widgets = []

    all_waf_configs = waf_configs
    all_with_logging = [waf for waf in all_waf_configs if waf.get("has_logging") and waf.get("log_group_name")]
    log_source_by_region = _build_log_source_by_region(all_with_logging)
    log_regions = list(log_source_by_region.keys())
    has_any_logs = len(all_with_logging) > 0

    if not all_waf_configs:
        widgets.append(
            {
                "type": "text",
                "x": 0,
                "y": 0,
                "width": 24,
                "height": 4,
                "properties": {
                    "markdown": "# WAF Security Operations Hub\n\nNo REGIONAL WAF Web ACLs discovered in this account and region during deploy-time macro execution."
                },
            }
        )
    else:
        widgets.append(
            {
                "type": "text",
                "x": 0,
                "y": _Y_HEADER,
                "width": 24,
                "height": 2,
                "properties": {
                    "markdown": "\n".join(
                        [
                            f"# WAF Security Operations Hub — {project_name}",
                            f"Regional WAFs: **{len(all_waf_configs)}** | CloudFront WAFs: **0** | WAFs with logging: **{len(all_with_logging)}** | _Click any WAF name in the tables below to open its detail dashboard_",
                        ]
                    )
                },
            }
        )

        widgets.extend(
            [
                {
                    "type": "metric",
                    "x": 0,
                    "y": _Y_KPI,
                    "width": 12,
                    "height": 4,
                    "properties": {
                        "title": "Blocks — Last 1h",
                        "region": region,
                        "stat": "Sum",
                        "period": 3600,
                        "view": "singleValue",
                        "sparkline": True,
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
                                {"label": waf["web_acl_name"]},
                            ]
                            for waf in all_waf_configs
                        ],
                    },
                },
                {
                    "type": "metric",
                    "x": 12,
                    "y": _Y_KPI,
                    "width": 12,
                    "height": 4,
                    "properties": {
                        "title": "Allowed — Last 24h",
                        "region": region,
                        "stat": "Sum",
                        "period": 86400,
                        "view": "singleValue",
                        "sparkline": True,
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
                                {"label": waf["web_acl_name"]},
                            ]
                            for waf in all_waf_configs
                        ],
                    },
                },
                {
                    "type": "metric",
                    "x": 0,
                    "y": _Y_TREND,
                    "width": 12,
                    "height": 8,
                    "properties": {
                        "title": "Total Blocked Requests — All WAFs (5 min intervals)",
                        "region": region,
                        "stat": "Sum",
                        "period": 300,
                        "view": "timeSeries",
                        "stacked": True,
                        "yAxis": {"left": {"showUnits": False}},
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
                                {
                                    "label": waf["name"],
                                    "color": _COLORS[index % len(_COLORS)],
                                    "region": waf["region"],
                                },
                            ]
                            for index, waf in enumerate(all_waf_configs)
                        ],
                    },
                },
                {
                    "type": "metric",
                    "x": 12,
                    "y": _Y_TREND,
                    "width": 12,
                    "height": 8,
                    "properties": {
                        "title": "Allowed vs Blocked — All WAFs (5 min intervals)",
                        "region": region,
                        "stat": "Sum",
                        "period": 300,
                        "view": "timeSeries",
                        "stacked": False,
                        "yAxis": {"left": {"showUnits": False}},
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
                                {
                                    "label": waf["name"],
                                    "color": _COLORS[index % len(_COLORS)],
                                    "region": waf["region"],
                                },
                            ]
                            for index, waf in enumerate(all_waf_configs)
                        ],
                    },
                },
                {
                    "type": "metric",
                    "x": 0,
                    "y": _Y_BAR,
                    "width": 12,
                    "height": 8,
                    "properties": {
                        "title": "Blocked Requests by WAF — 24h (fixed)",
                        "region": region,
                        "stat": "Sum",
                        "period": 86400,
                        "view": "bar",
                        "yAxis": {"left": {"showUnits": False}},
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
                                {
                                    "label": waf["name"],
                                    "color": _COLORS[index % len(_COLORS)],
                                    "region": waf["region"],
                                },
                            ]
                            for index, waf in enumerate(all_waf_configs)
                        ],
                    },
                },
                {
                    "type": "metric",
                    "x": 12,
                    "y": _Y_BAR,
                    "width": 12,
                    "height": 8,
                    "properties": {
                        "title": "Blocked Requests by WAF — Selected Time Range",
                        "region": region,
                        "stat": "Sum",
                        "setPeriodToTimeRange": True,
                        "view": "bar",
                        "yAxis": {"left": {"showUnits": False}},
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
                                {
                                    "label": waf["name"],
                                    "color": _COLORS[index % len(_COLORS)],
                                    "region": waf["region"],
                                },
                            ]
                            for index, waf in enumerate(all_waf_configs)
                        ],
                    },
                },
            ]
        )

        if has_any_logs:
            widgets.append(
                {
                    "type": "text",
                    "x": 0,
                    "y": _Y_AGG_HEADER,
                    "width": 24,
                    "height": 1,
                    "properties": {"markdown": "## Aggregated Log Analytics — All WAFs"},
                }
            )

            for region_index, log_region in enumerate(log_regions):
                offset = 1 if len(log_regions) > 1 else 0
                row_offset = region_index * 34
                log_source = log_source_by_region[log_region]

                if len(log_regions) > 1:
                    widgets.append(
                        {
                            "type": "text",
                            "x": 0,
                            "y": _Y_AGG_ROW1 + row_offset,
                            "width": 24,
                            "height": 1,
                            "properties": {"markdown": f"### Log Analytics — {log_region}"},
                        }
                    )

                widgets.extend(
                    [
                        {
                            "type": "log",
                            "x": 0,
                            "y": _Y_AGG_ROW1 + row_offset + offset,
                            "width": 12,
                            "height": 8,
                            "properties": {
                                "title": f"Top Blocking Rules{' (' + log_region + ')' if len(log_regions) > 1 else ' — All WAFs'}",
                                "region": log_region,
                                "view": "pie",
                                "query": f"{log_source} | stats count(*) as Blocks by terminatingRuleId | sort Blocks desc | limit 10",
                            },
                        },
                        {
                            "type": "log",
                            "x": 12,
                            "y": _Y_AGG_ROW1 + row_offset + offset,
                            "width": 12,
                            "height": 8,
                            "properties": {
                                "title": f"Top Blocked IPs{' (' + log_region + ')' if len(log_regions) > 1 else ' — with WAF'}",
                                "region": log_region,
                                "view": "table",
                                "query": f"{log_source} | {_PARSE_WAF_NAME} | stats count(*) as Blocks by httpRequest.clientIp, WebACL | sort Blocks desc | limit 15",
                            },
                        },
                        {
                            "type": "log",
                            "x": 0,
                            "y": _Y_AGG_ROW1B + row_offset + offset,
                            "width": 12,
                            "height": 8,
                            "properties": {
                                "title": f"Attack Origin by Country{' (' + log_region + ')' if len(log_regions) > 1 else ''}",
                                "region": log_region,
                                "view": "pie",
                                "query": f"{log_source} | stats count(*) as Blocks by httpRequest.country | sort Blocks desc | limit 10",
                            },
                        },
                        {
                            "type": "log",
                            "x": 12,
                            "y": _Y_AGG_ROW1B + row_offset + offset,
                            "width": 12,
                            "height": 8,
                            "properties": {
                                "title": f"Top Targeted URIs{' (' + log_region + ')' if len(log_regions) > 1 else ' — with WAF'}",
                                "region": log_region,
                                "view": "table",
                                "query": f"{log_source} | {_PARSE_WAF_NAME} | stats count(*) as Blocks by httpRequest.uri, WebACL | sort Blocks desc | limit 15",
                            },
                        },
                        {
                            "type": "log",
                            "x": 0,
                            "y": _Y_AGG_ROW2 + row_offset + offset,
                            "width": 12,
                            "height": 8,
                            "properties": {
                                "title": f"Attack Classification (XSS / SQLi / etc.){' (' + log_region + ')' if len(log_regions) > 1 else ''}",
                                "region": log_region,
                                "view": "table",
                                "query": f"{log_source} | {_PARSE_ATTACK_TYPE} | filter ispresent(AttackType) | {_PARSE_WAF_NAME} | stats count(*) as Hits by AttackType, WebACL | sort Hits desc | limit 20",
                            },
                        },
                        {
                            "type": "log",
                            "x": 12,
                            "y": _Y_AGG_ROW2 + row_offset + offset,
                            "width": 12,
                            "height": 8,
                            "properties": {
                                "title": f"Block Rate per WAF — every 5 min{' (' + log_region + ')' if len(log_regions) > 1 else ''}",
                                "region": log_region,
                                "view": "timeSeries",
                                "query": f"{log_source} | {_PARSE_WAF_NAME} | stats count(*) as Blocks by bin(5m), WebACL | sort @timestamp asc",
                            },
                        },
                    ]
                )

            widgets.append(
                {
                    "type": "text",
                    "x": 0,
                    "y": _Y_THREAT_HEADER,
                    "width": 24,
                    "height": 1,
                    "properties": {"markdown": "## Threat Intelligence"},
                }
            )

            for region_index, log_region in enumerate(log_regions):
                offset = 1 if len(log_regions) > 1 else 0
                row_offset = region_index * 25
                log_source = log_source_by_region[log_region]

                if len(log_regions) > 1:
                    widgets.append(
                        {
                            "type": "text",
                            "x": 0,
                            "y": _Y_THREAT_ROW + row_offset,
                            "width": 24,
                            "height": 1,
                            "properties": {"markdown": f"### Threat Intelligence — {log_region}"},
                        }
                    )

                widgets.extend(
                    [
                        {
                            "type": "log",
                            "x": 0,
                            "y": _Y_THREAT_ROW + row_offset + offset,
                            "width": 12,
                            "height": 8,
                            "properties": {
                                "title": f"Attack Type × WAF Matrix{' (' + log_region + ')' if len(log_regions) > 1 else ''}",
                                "region": log_region,
                                "view": "table",
                                "query": f"{log_source} | filter action = 'BLOCK' | {_PARSE_WAF_NAME} | stats count(*) as Blocks by terminatingRuleId, WebACL | sort Blocks desc | limit 20",
                            },
                        },
                        {
                            "type": "log",
                            "x": 12,
                            "y": _Y_THREAT_ROW + row_offset + offset,
                            "width": 12,
                            "height": 8,
                            "properties": {
                                "title": f"Block Trend — Last 24h per WAF (30 min){' (' + log_region + ')' if len(log_regions) > 1 else ''}",
                                "region": log_region,
                                "view": "timeSeries",
                                "query": f"{log_source} | filter action = 'BLOCK' | {_PARSE_WAF_NAME} | stats count(*) as Blocks by bin(30m), WebACL | sort @timestamp asc",
                            },
                        },
                        {
                            "type": "log",
                            "x": 0,
                            "y": _Y_THREAT_ROW2 + row_offset + offset,
                            "width": 24,
                            "height": 8,
                            "properties": {
                                "title": f"Persistent Attackers — IP × WAF{' (' + log_region + ')' if len(log_regions) > 1 else ''}",
                                "region": log_region,
                                "view": "table",
                                "query": f"{log_source} | filter action = 'BLOCK' | {_PARSE_WAF_NAME} | stats count(*) as TotalBlocks, earliest(@timestamp) as FirstSeen, latest(@timestamp) as LastSeen by httpRequest.clientIp, WebACL | sort TotalBlocks desc | limit 20",
                            },
                        },
                    ]
                )

            widgets.append(
                {
                    "type": "text",
                    "x": 0,
                    "y": _Y_RAW_HEADER,
                    "width": 24,
                    "height": 1,
                    "properties": {"markdown": "## Live Blocked Requests Feed"},
                }
            )

            for region_index, log_region in enumerate(log_regions):
                log_source = log_source_by_region[log_region]
                widgets.append(
                    {
                        "type": "log",
                        "x": 0,
                        "y": _Y_RAW + (region_index * 9),
                        "width": 24,
                        "height": 8,
                        "properties": {
                            "title": f"Recent Blocked Requests{' (' + log_region + ')' if len(log_regions) > 1 else ' — All WAFs'}",
                            "region": log_region,
                            "view": "table",
                            "query": f"{log_source} | {_PARSE_WAF_NAME} | sort @timestamp desc | display @timestamp, WebACL, httpRequest.clientIp, httpRequest.country, httpRequest.httpMethod, httpRequest.uri, terminatingRuleId | limit 100",
                        },
                    }
                )

        sparkline_wafs = all_waf_configs[:max_sparkline_wafs]
        sparkline_truncated = len(all_waf_configs) > max_sparkline_wafs
        sparkline_y_start = _Y_RAW + 9

        widgets.append(
            {
                "type": "text",
                "x": 0,
                "y": sparkline_y_start - 1,
                "width": 24,
                "height": 1,
                "properties": {
                    "markdown": (
                        f"## Per-WAF Sparklines (top {max_sparkline_wafs} of {len(all_waf_configs)})"
                        if sparkline_truncated
                        else "## Per-WAF Sparklines"
                    )
                },
            }
        )

        for index, waf in enumerate(sparkline_wafs):
            widgets.append(
                {
                    "type": "metric",
                    "x": (index % 2) * 12,
                    "y": sparkline_y_start + (index // 2) * 8,
                    "width": 12,
                    "height": 8,
                    "properties": {
                        "title": waf["name"],
                        "region": waf["region"],
                        "stat": "Sum",
                        "period": 300,
                        "view": "timeSeries",
                        "stacked": True,
                        "yAxis": {"left": {"showUnits": False}},
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
                }
            )

        sparkline_rows = (min(len(all_waf_configs), max_sparkline_wafs) + 1) // 2
        after_sparklines_y = sparkline_y_start + (sparkline_rows * 8)
        regional_table_height = min(max(len(all_waf_configs) + 5, 5), 30)

        widgets.append(
            {
                "type": "text",
                "x": 0,
                "y": after_sparklines_y,
                "width": 24,
                "height": regional_table_height,
                "properties": {
                    "markdown": _summary_drilldown_markdown(
                        project_name=project_name,
                        dashboard_detail_prefix=dashboard_detail_prefix,
                        waf_configs=all_waf_configs,
                        region=region,
                    )
                },
            }
        )

    dashboard_body = json.dumps({"start": "-PT24H", "widgets": widgets})

    return {
        "WafHubSummaryDashboard": {
            "Type": "AWS::CloudWatch::Dashboard",
            "Properties": {
                "DashboardName": dashboard_name,
                "DashboardBody": dashboard_body,
            },
        }
    }
