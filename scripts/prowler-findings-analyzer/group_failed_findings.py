#!/usr/bin/env python3
"""Group homogeneous Prowler FAIL findings for mute-list review.

Same CHECK_ID across many resources (e.g. ECS task definitions) is reported once,
with resource counts, regions, and sample names.

Supports Prowler CSV (semicolon-delimited) and OCSF JSON arrays.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

SEVERITY_RANK = {
    "critical": 0,
    "high": 1,
    "medium": 2,
    "low": 3,
    "informational": 4,
}

CSV_FIELD_MAP = {
    "check_id": "CHECK_ID",
    "check_title": "CHECK_TITLE",
    "status": "STATUS",
    "muted": "MUTED",
    "severity": "SEVERITY",
    "service": "SERVICE_NAME",
    "resource_type": "RESOURCE_TYPE",
    "resource_uid": "RESOURCE_UID",
    "resource_name": "RESOURCE_NAME",
    "region": "REGION",
    "account": "ACCOUNT_UID",
    "status_extended": "STATUS_EXTENDED",
    "description": "DESCRIPTION",
    "risk": "RISK",
    "remediation": "REMEDIATION_RECOMMENDATION_TEXT",
    "remediation_url": "REMEDIATION_RECOMMENDATION_URL",
}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Group failed Prowler findings by check so each issue appears once."
    )
    p.add_argument(
        "-i",
        "--input",
        type=Path,
        default=Path("prowler-core.csv"),
        help="Prowler CSV or OCSF JSON file (default: prowler-core.csv)",
    )
    p.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        default=Path("grouped_findings"),
        help="Directory for grouped reports (default: grouped_findings)",
    )
    p.add_argument(
        "--min-severity",
        choices=list(SEVERITY_RANK),
        default="low",
        help="Keep FAIL findings at this severity or worse (default: low = all FAILs)",
    )
    p.add_argument(
        "--include-muted",
        action="store_true",
        help="Include findings already marked MUTED=True (default: skip them)",
    )
    p.add_argument(
        "--sample-resources",
        type=int,
        default=8,
        help="How many example resource names to keep per check (default: 8)",
    )
    p.add_argument(
        "--emit-mutelist",
        action="store_true",
        help="Also write mutelist_candidates.yaml (all grouped checks commented out)",
    )
    return p.parse_args()


def severity_ok(sev: str, min_severity: str) -> bool:
    return SEVERITY_RANK.get((sev or "").lower(), 99) <= SEVERITY_RANK[min_severity]


def is_fail(status: str) -> bool:
    return (status or "").strip().upper() == "FAIL"


def is_muted(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "1", "yes"}


def load_csv(path: Path) -> list[dict[str, Any]]:
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh, delimiter=";")
        if not reader.fieldnames or "CHECK_ID" not in reader.fieldnames:
            raise SystemExit(f"{path} does not look like a Prowler CSV (missing CHECK_ID)")
        findings = []
        for row in reader:
            findings.append(
                {out: (row.get(src) or "").strip() for out, src in CSV_FIELD_MAP.items()}
            )
        return findings


def _ocsf_resources(item: dict[str, Any]) -> list[dict[str, Any]]:
    resources = item.get("resources") or []
    if isinstance(resources, dict):
        return [resources]
    return resources if isinstance(resources, list) else []


def load_ocsf(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as fh:
        data = json.load(fh)
    if isinstance(data, dict):
        data = data.get("findings") or data.get("data") or [data]
    findings = []
    for item in data:
        meta = item.get("metadata") or {}
        unmapped = item.get("unmapped") or {}
        cloud = item.get("cloud") or {}
        resources = _ocsf_resources(item)
        first = resources[0] if resources else {}
        findings.append(
            {
                "check_id": meta.get("event_code") or unmapped.get("check_id") or "",
                "check_title": item.get("finding_info", {}).get("title")
                or unmapped.get("check_title")
                or "",
                "status": item.get("status_code") or "",
                "muted": str(unmapped.get("muted", False)),
                "severity": (item.get("severity") or "").lower(),
                "service": (cloud.get("service") or {}).get("name")
                or unmapped.get("service_name")
                or "",
                "resource_type": first.get("type") or "",
                "resource_uid": first.get("uid") or first.get("name") or "",
                "resource_name": first.get("name") or first.get("uid") or "",
                "region": cloud.get("region") or first.get("region") or "",
                "account": (cloud.get("account") or {}).get("uid") or "",
                "status_extended": item.get("status_detail") or item.get("message") or "",
                "description": (item.get("finding_info") or {}).get("desc") or "",
                "risk": unmapped.get("risk") or "",
                "remediation": (
                    ((item.get("remediation") or {}).get("desc"))
                    or unmapped.get("remediation")
                    or ""
                ),
                "remediation_url": unmapped.get("related_url") or "",
            }
        )
    return findings


def load_findings(path: Path) -> list[dict[str, Any]]:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return load_csv(path)
    if suffix == ".json":
        return load_ocsf(path)
    raise SystemExit(f"Unsupported input type: {path.suffix} (use .csv or .json)")


def group_findings(
    findings: Iterable[dict[str, Any]],
    *,
    min_severity: str,
    include_muted: bool,
    sample_resources: int,
) -> list[dict[str, Any]]:
    buckets: dict[str, dict[str, Any]] = {}

    for f in findings:
        if not is_fail(f.get("status", "")):
            continue
        if not include_muted and is_muted(f.get("muted")):
            continue
        if not severity_ok(f.get("severity", ""), min_severity):
            continue

        check_id = f.get("check_id") or "(unknown)"
        bucket = buckets.get(check_id)
        if bucket is None:
            bucket = {
                "check_id": check_id,
                "check_title": f.get("check_title") or "",
                "severity": (f.get("severity") or "").lower(),
                "service": f.get("service") or "",
                "resource_type": f.get("resource_type") or "",
                "fail_count": 0,
                "accounts": set(),
                "regions": set(),
                "resource_uids": set(),
                "resource_names": [],
                "status_extended_samples": [],
                "description": f.get("description") or "",
                "risk": f.get("risk") or "",
                "remediation": f.get("remediation") or "",
                "remediation_url": f.get("remediation_url") or "",
            }
            buckets[check_id] = bucket

        bucket["fail_count"] += 1
        if f.get("account"):
            bucket["accounts"].add(f["account"])
        if f.get("region"):
            bucket["regions"].add(f["region"])
        uid = f.get("resource_uid") or f.get("resource_name") or ""
        if uid:
            bucket["resource_uids"].add(uid)
        name = f.get("resource_name") or uid
        if name and name not in bucket["resource_names"] and len(bucket["resource_names"]) < sample_resources:
            bucket["resource_names"].append(name)
        detail = f.get("status_extended") or ""
        if (
            detail
            and detail not in bucket["status_extended_samples"]
            and len(bucket["status_extended_samples"]) < 3
        ):
            bucket["status_extended_samples"].append(detail)

        if SEVERITY_RANK.get(bucket["severity"], 99) > SEVERITY_RANK.get(
            (f.get("severity") or "").lower(), 99
        ):
            bucket["severity"] = (f.get("severity") or "").lower()

    grouped = []
    for check_id, b in buckets.items():
        grouped.append(
            {
                "check_id": check_id,
                "check_title": b["check_title"],
                "severity": b["severity"],
                "service": b["service"],
                "resource_type": b["resource_type"],
                "fail_count": b["fail_count"],
                "unique_resources": len(b["resource_uids"]),
                "accounts": sorted(b["accounts"]),
                "regions": sorted(b["regions"]),
                "sample_resources": b["resource_names"],
                "status_extended_samples": b["status_extended_samples"],
                "description": b["description"],
                "risk": b["risk"],
                "remediation": b["remediation"],
                "remediation_url": b["remediation_url"],
            }
        )

    grouped.sort(
        key=lambda x: (
            SEVERITY_RANK.get(x["severity"], 99),
            -x["fail_count"],
            x["check_id"],
        )
    )
    return grouped


def write_csv(path: Path, grouped: list[dict[str, Any]]) -> None:
    fields = [
        "severity",
        "fail_count",
        "unique_resources",
        "service",
        "check_id",
        "check_title",
        "resource_type",
        "regions",
        "accounts",
        "sample_resources",
        "status_extended_samples",
        "remediation_url",
    ]
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in grouped:
            writer.writerow(
                {
                    **row,
                    "regions": "|".join(row["regions"]),
                    "accounts": "|".join(row["accounts"]),
                    "sample_resources": " | ".join(row["sample_resources"]),
                    "status_extended_samples": " | ".join(row["status_extended_samples"]),
                }
            )


def yaml_quote(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def write_mutelist(path: Path, grouped: list[dict[str, Any]]) -> None:
    """Write a Prowler mutelist skeleton. Every check is commented out."""
    accounts = sorted({acc for row in grouped for acc in row["accounts"]}) or ["*"]
    account_key = accounts[0] if len(accounts) == 1 else "*"

    lines = [
        "# Prowler mutelist candidates generated from grouped FAIL findings.",
        "# Review each check, then uncomment the block you actually want to mute.",
        "# Docs: https://docs.prowler.com/projects/prowler-open-source/en/latest/tutorials/mutelist/",
        "",
        "Mutelist:",
        "  Accounts:",
        f"    {yaml_quote(account_key)}:",
        "      Checks:",
    ]
    for row in grouped:
        title = row["check_title"].replace("\n", " ")
        lines.append(f"        # {row['severity'].upper()} | {row['fail_count']} FAIL(s) | {title}")
        lines.append(f"        # {yaml_quote(row['check_id'])}:")
        lines.append("        #   Regions:")
        lines.append('        #     - "*"')
        lines.append("        #   Resources:")
        lines.append('        #     - "*"')
        lines.append(
            f"        #   Description: \"Accepted / false positive: {row['check_id']}\""
        )
        lines.append("")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def print_summary(grouped: list[dict[str, Any]], raw_fail_count: int) -> None:
    by_sev: dict[str, int] = defaultdict(int)
    for row in grouped:
        by_sev[row["severity"]] += 1
    print(f"Failed finding rows: {raw_fail_count}")
    print(f"Grouped unique checks: {len(grouped)}")
    for sev in SEVERITY_RANK:
        if by_sev[sev]:
            print(f"  {sev:15s} {by_sev[sev]}")
    print()
    print(f"{'SEV':8s} {'FAILS':>6s} {'RES':>6s} {'SERVICE':16s} CHECK_ID")
    for row in grouped[:25]:
        print(
            f"{row['severity']:8s} {row['fail_count']:6d} {row['unique_resources']:6d} "
            f"{row['service'][:16]:16s} {row['check_id']}"
        )
    if len(grouped) > 25:
        print(f"... {len(grouped) - 25} more checks (see output files)")


def main() -> int:
    args = parse_args()
    if not args.input.exists():
        print(f"Input not found: {args.input}", file=sys.stderr)
        return 1

    findings = load_findings(args.input)
    grouped = group_findings(
        findings,
        min_severity=args.min_severity,
        include_muted=args.include_muted,
        sample_resources=args.sample_resources,
    )
    raw_fail_count = sum(r["fail_count"] for r in grouped)

    out = args.output_dir
    out.mkdir(parents=True, exist_ok=True)
    write_csv(out / "grouped_failed_checks.csv", grouped)
    (out / "grouped_failed_checks.json").write_text(
        json.dumps(grouped, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    if args.emit_mutelist:
        write_mutelist(out / "mutelist_candidates.yaml", grouped)

    print_summary(grouped, raw_fail_count)
    print()
    print(f"Wrote {out / 'grouped_failed_checks.csv'}")
    print(f"Wrote {out / 'grouped_failed_checks.json'}")
    if args.emit_mutelist:
        print(f"Wrote {out / 'mutelist_candidates.yaml'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
