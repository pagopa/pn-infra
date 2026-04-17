import json
import logging

from builders.details import build_detail_dashboard_resources
from builders.outputs import build_detail_outputs, build_summary_outputs
from builders.summary import build_summary_dashboard_resources
from services.wafv2 import discover_regional_web_acls


logger = logging.getLogger()
logger.setLevel(logging.INFO)


def _success(event, fragment):
    return {
        "requestId": event.get("requestId", "unknown"),
        "status": "success",
        "fragment": fragment,
    }


def _failure(event, exc):
    logger.error("Error in WAF dashboard macro: %s", str(exc), exc_info=True)
    return {
        "requestId": event.get("requestId", "unknown"),
        "status": "failure",
        "errorMessage": str(exc),
    }


def handler(event, context):
    try:
        logger.info("Received macro event: %s", json.dumps(event))

        params = event.get("params", {})
        action = params.get("Action", "Resources").lower()
        component = params.get("Component", "All").lower()
        project_name = params.get("ProjectName")
        dashboard_prefix = params.get("DashboardPrefix", "WAF-Hub")
        dashboard_detail_prefix = params.get("DashboardDetailPrefix", "WAF-Detail")
        region = params.get("Region") or event.get("region")
        default_metric_period_seconds = int(params.get("DefaultMetricPeriodSeconds", 300))
        max_sparkline_wafs = int(params.get("MaxSparklineWafs", 12))

        if not project_name:
            raise ValueError("Missing required parameter: ProjectName")
        if not region:
            raise ValueError("Missing required parameter: Region")

        waf_configs = discover_regional_web_acls(region)
        logger.info("Discovered %s regional WAFs in %s", len(waf_configs), region)

        if action == "resources":
            resources = {}
            if component in ("summary", "all"):
                resources.update(
                    build_summary_dashboard_resources(
                        project_name=project_name,
                        dashboard_prefix=dashboard_prefix,
                        dashboard_detail_prefix=dashboard_detail_prefix,
                        waf_configs=waf_configs,
                        region=region,
                        default_metric_period_seconds=default_metric_period_seconds,
                        max_sparkline_wafs=max_sparkline_wafs,
                    )
                )
            if component in ("details", "all"):
                resources.update(
                    build_detail_dashboard_resources(
                        project_name=project_name,
                        dashboard_prefix=dashboard_prefix,
                        dashboard_detail_prefix=dashboard_detail_prefix,
                        waf_configs=waf_configs,
                        region=region,
                        default_metric_period_seconds=default_metric_period_seconds,
                    )
                )
            return _success(event, resources)

        if action == "outputs":
            outputs = {}
            if component in ("summary", "all", "outputs"):
                outputs.update(
                    build_summary_outputs(
                        project_name=project_name,
                        dashboard_prefix=dashboard_prefix,
                        waf_configs=waf_configs,
                    )
                )
            if component in ("details", "all", "outputs"):
                outputs.update(
                    build_detail_outputs(
                        project_name=project_name,
                        dashboard_detail_prefix=dashboard_detail_prefix,
                        waf_configs=waf_configs,
                    )
                )
            return _success(event, outputs)

        raise ValueError(f"Invalid Action parameter: {params.get('Action')}")
    except Exception as exc:
        return _failure(event, exc)
