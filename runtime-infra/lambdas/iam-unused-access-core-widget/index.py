import collections
import csv
import html
import io
import math
import os
import sys

import boto3

s3 = boto3.client("s3")

# Allow parsing CSV rows with very large details_json fields.
csv.field_size_limit(sys.maxsize)

def _describe():
  return {
    "markdown": "Widget IAM unused access: full table or pie charts (summary/microservice) from the latest CSV report."
  }

def _render_message(message):
  return f'<div class="cwdb-no-default-styles"></div><p>{html.escape(message)}</p>'

def _format_unused_actions(raw_actions):
  if not raw_actions:
    return "-"
  actions = [a.strip() for a in str(raw_actions).split(";") if a.strip()]
  if not actions:
    return "-"
  return ", ".join(actions)

def _to_int(value, default_value):
  try:
    return int(value)
  except Exception:
    return default_value

def _find_latest_csv(bucket, prefix):
  token = None
  latest = None
  while True:
    kwargs = {"Bucket": bucket, "Prefix": prefix, "MaxKeys": 1000}
    if token:
      kwargs["ContinuationToken"] = token
    response = s3.list_objects_v2(**kwargs)
    for obj in response.get("Contents", []):
      if not obj["Key"].endswith(".csv"):
        continue
      if latest is None or obj["LastModified"] > latest["LastModified"]:
        latest = obj
    if not response.get("IsTruncated"):
      return latest
    token = response.get("NextContinuationToken")

def _render_pie_card(title, counts):
  filtered = [(k, v) for k, v in counts.items() if v > 0]
  if not filtered:
    return _render_message(f"Nessun dato disponibile per {title}")

  total = sum(v for _, v in filtered)
  colors = ["#0ea5e9", "#f59e0b", "#22c55e", "#ef4444", "#8b5cf6", "#14b8a6", "#f97316", "#64748b"]
  radius = 70
  stroke = 38
  cx = 90
  cy = 90
  circumference = 2 * math.pi * radius

  circles = []
  legend = []
  offset = 0.0
  for idx, (label, value) in enumerate(filtered):
    color = colors[idx % len(colors)]
    fraction = value / total
    segment = circumference * fraction
    circles.append(
      f'<circle cx="{cx}" cy="{cy}" r="{radius}" fill="none" stroke="{color}" stroke-width="{stroke}" '
      f'stroke-dasharray="{segment:.2f} {circumference - segment:.2f}" stroke-dashoffset="{-offset:.2f}" '
      f'transform="rotate(-90 {cx} {cy})" />'
    )
    percent = (fraction * 100.0)
    legend.append(
      f'<div style="display:flex;align-items:center;gap:8px;margin:4px 0">'
      f'<span style="display:inline-block;width:10px;height:10px;background:{color};border-radius:999px"></span>'
      f'<span>{html.escape(str(label))}: <b>{value}</b> ({percent:.1f}%)</span>'
      f'</div>'
    )
    offset += segment

  return (
    '<div class="cwdb-no-default-styles"></div>'
    '<div style="font-family:Arial,sans-serif;font-size:12px;color:#1e293b">'
    '<style>@media(prefers-color-scheme:dark){.cw-dark{color:#e2e8f0!important}.cw-dark b{color:#f1f5f9!important}.cw-dark .cw-bg{stroke:#374151!important}}</style>'
    f'<p class="cw-dark" style="margin:0 0 8px 0"><b>{html.escape(title)}</b> (totale: {total})</p>'
    '<div style="display:flex;gap:16px;align-items:flex-start;flex-wrap:wrap">'
    '<svg width="190" height="190" viewBox="0 0 190 190" role="img" aria-label="pie-chart">'
    f'<circle class="cw-bg" cx="{cx}" cy="{cy}" r="{radius}" fill="none" stroke="#e5e7eb" stroke-width="{stroke}" />'
    f'{"" .join(circles)}'
    '</svg>'
    f'<div class="cw-dark">{"" .join(legend)}</div>'
    '</div>'
    '</div>'
  )

def handler(event, context):
  if event.get("describe"):
    return _describe()

  params = event.get("params") or {}
  bucket = params.get("bucket") or event.get("bucket") or os.environ.get("DEFAULT_BUCKET", "")
  prefix = params.get("prefix") or event.get("prefix") or os.environ.get("DEFAULT_PREFIX", "")
  label = params.get("label") or event.get("label") or prefix or "n/a"
  view = (params.get("view") or event.get("view") or "table").strip().lower()
  microservice_limit = _to_int(params.get("microserviceLimit") or event.get("microserviceLimit"), 8)
  if not bucket:
    return _render_message("Bucket non configurato")

  try:
    latest = _find_latest_csv(bucket, prefix)
  except Exception as e:
    return _render_message(f"Impossibile accedere al bucket {bucket}: {e}")

  if not latest:
    return _render_message(f"Nessun report CSV trovato in s3://{bucket}/{prefix}")

  try:
    obj = s3.get_object(Bucket=bucket, Key=latest["Key"])
    body = obj["Body"].read().decode("utf-8")
  except Exception as e:
    return _render_message(f"Impossibile leggere il report da s3://{bucket}/{latest['Key']}: {e}")
  data_rows = list(csv.DictReader(io.StringIO(body)))

  if view == "summary":
    counts = collections.OrderedDict()
    counts["Ruoli completamente inutilizzati (UnusedIAMRole)"] = sum(1 for r in data_rows if r.get("finding_type") == "UnusedIAMRole")
    counts["Ruoli usati con permessi inutilizzati (UnusedPermission)"] = sum(1 for r in data_rows if r.get("finding_type") == "UnusedPermission")
    return _render_pie_card(f"Distribuzione finding - {label}", counts)

  if view == "microservice":
    ms_counter = collections.Counter()
    for row in data_rows:
      microservice = str(row.get("microservice_tag") or "").strip() or "no-tag"
      ms_counter[microservice] += 1

    if not ms_counter:
      return _render_message(f"Nessun ruolo IAM associabile a microservizi per {label}")

    top = ms_counter.most_common(max(microservice_limit, 1))
    others = sum(v for _, v in ms_counter.items()) - sum(v for _, v in top)
    pie_counts = collections.OrderedDict(top)
    if others > 0:
      pie_counts["Altri"] = others

    return _render_pie_card(f"Finding per microservizio (tag Microservice) - {label}", pie_counts)

  rows = []
  for row in data_rows:
    rows.append(
      "<tr>"
      f"<td>{html.escape(row.get('finding_id', ''))}</td>"
      f"<td>{html.escape(row.get('resource', ''))}</td>"
      f"<td>{html.escape(row.get('status', ''))}</td>"
      f"<td>{html.escape(str(row.get('unused_action_count', '')))}</td>"
      f"<td>{html.escape(_format_unused_actions(row.get('unused_actions', '')))}</td>"
      "</tr>"
    )

  header = (
    '<div class="cwdb-no-default-styles"></div>'
    '<style>'
    'table{width:100%;border-collapse:collapse;font-family:Arial,sans-serif;font-size:12px;color:#1e293b}'
    'th,td{padding:6px;border-bottom:1px solid #ddd;text-align:left;vertical-align:top}'
    'td{word-break:break-word}'
    'th{background:#eef3f7;color:#1e293b}'
    '@media(prefers-color-scheme:dark){table{color:#e2e8f0}th{background:#1e293b;color:#e2e8f0}td{border-color:#374151}}'
    '</style>'
    f'<p><b>Scope:</b> {html.escape(str(label))}<br/>'
    f'<b>Bucket:</b> {html.escape(bucket)}<br/>'
    f'<b>Ultimo report:</b> {html.escape(latest["Key"])}<br/>'
    f'<b>Ultima modifica:</b> {latest["LastModified"].isoformat()}<br/>'
    f'<b>Righe:</b> {len(rows)}</p>'
  )

  if not rows:
    return header + '<p>Nessun finding nel report piu\' recente.</p>'

  table = (
    '<table><thead><tr><th>Finding</th><th>Resource</th><th>Status</th><th>Unused Count</th><th>Unused Actions</th></tr></thead>'
    f'<tbody>{"".join(rows)}</tbody></table>'
  )
  return header + table
