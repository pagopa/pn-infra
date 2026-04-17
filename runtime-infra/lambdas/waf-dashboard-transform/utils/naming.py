import hashlib
import re


def sanitize_logical_id(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9]", "", value or "")
    if not cleaned:
        cleaned = "Waf"
    if cleaned[0].isdigit():
        cleaned = f"Waf{cleaned}"
    digest = hashlib.sha1((value or "").encode("utf-8")).hexdigest()[:8]
    return f"{cleaned[:40]}{digest}"


def sanitize_dashboard_name(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "-", value or "")
    cleaned = re.sub(r"-{2,}", "-", cleaned)
    cleaned = cleaned.strip("-_")
    return cleaned or "waf-dashboard"


def build_summary_dashboard_name(project_name: str, dashboard_prefix: str) -> str:
    return sanitize_dashboard_name(f"{project_name}-{dashboard_prefix}")


def build_detail_dashboard_name(project_name: str, dashboard_detail_prefix: str, waf_name: str) -> str:
    return sanitize_dashboard_name(f"{project_name}-{dashboard_detail_prefix}-{waf_name}")


def build_detail_logical_id(waf_name: str) -> str:
    return f"WafDetailDashboard{sanitize_logical_id(waf_name)}"
