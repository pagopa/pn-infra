"""Self-contained HTML report generation for IAM unused-access findings."""

import html
import secrets


HTML_REPORT_SCRIPT = r"""
(() => {
  const tbody = document.getElementById("report-body");
  const allRows = Array.from(tbody.querySelectorAll("tr[data-record]"));
  const search = document.getElementById("search");
  const typeFilter = document.getElementById("type-filter");
  const statusFilter = document.getElementById("status-filter");
  const microserviceFilter = document.getElementById("microservice-filter");
  const suppressionFilter = document.getElementById("suppression-filter");
  const pageSize = document.getElementById("page-size");
  const previousPage = document.getElementById("previous-page");
  const nextPage = document.getElementById("next-page");
  const pageStatus = document.getElementById("page-status");
  const noResults = document.getElementById("no-results");
  const download = document.getElementById("download-csv");
  const reset = document.getElementById("reset-filters");
  let currentPage = 1;
  let sortColumn = -1;
  let sortAscending = true;
  let filteredRows = allRows.slice();

  const cellText = (row, column) => row.cells[column].innerText.trim();

  const populateFilter = (select, column) => {
    const values = [...new Set(allRows.map(row => cellText(row, column)).filter(Boolean))]
      .sort((left, right) => left.localeCompare(right, "it", { sensitivity: "base" }));
    values.forEach(value => {
      const option = document.createElement("option");
      option.value = value;
      option.textContent = value;
      select.appendChild(option);
    });
  };

  const matchesFilters = row => {
    const term = search.value.trim().toLocaleLowerCase("it");
    const rowText = Array.from(row.cells).map(cell => cell.innerText).join(" ").toLocaleLowerCase("it");
    return (!term || rowText.includes(term))
      && (!typeFilter.value || cellText(row, 1) === typeFilter.value)
      && (!statusFilter.value || cellText(row, 4) === statusFilter.value)
      && (!microserviceFilter.value || cellText(row, 5) === microserviceFilter.value)
      && (
        !suppressionFilter.value
        || (suppressionFilter.value === "with" && cellText(row, 7) !== "-")
        || (suppressionFilter.value === "without" && cellText(row, 7) === "-")
      );
  };

  const render = () => {
    filteredRows = allRows.filter(matchesFilters);
    if (sortColumn >= 0) {
      filteredRows.sort((left, right) => {
        const comparison = cellText(left, sortColumn).localeCompare(
          cellText(right, sortColumn),
          "it",
          { numeric: true, sensitivity: "base" }
        );
        return sortAscending ? comparison : -comparison;
      });
    }

    const size = Number(pageSize.value);
    const totalPages = Math.max(1, Math.ceil(filteredRows.length / size));
    currentPage = Math.min(currentPage, totalPages);
    const start = (currentPage - 1) * size;
    const visibleRows = filteredRows.slice(start, start + size);

    tbody.replaceChildren(...visibleRows, noResults);
    noResults.hidden = visibleRows.length > 0;
    previousPage.disabled = currentPage <= 1;
    nextPage.disabled = currentPage >= totalPages;
    download.disabled = filteredRows.length === 0;
    pageStatus.textContent = `Pagina ${currentPage} di ${totalPages} · ${filteredRows.length} risultati`;
  };

  const escapeCsv = value => `"${String(value).replace(/"/g, '""')}"`;
  download.addEventListener("click", () => {
    const headers = Array.from(document.querySelectorAll("thead th")).map(header => header.innerText.trim());
    const lines = [headers, ...filteredRows.map(row => Array.from(row.cells).map(cell => cell.innerText.trim()))]
      .map(values => values.map(escapeCsv).join(","));
    const blob = new Blob(["\ufeff", lines.join("\r\n")], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = download.dataset.filename;
    anchor.click();
    URL.revokeObjectURL(url);
  });

  document.querySelectorAll("button[data-sort-column]").forEach(button => {
    button.addEventListener("click", () => {
      const column = Number(button.dataset.sortColumn);
      sortAscending = sortColumn === column ? !sortAscending : true;
      sortColumn = column;
      document.querySelectorAll("button[data-sort-column]").forEach(item => {
        item.removeAttribute("data-direction");
        item.setAttribute("aria-sort", "none");
      });
      button.dataset.direction = sortAscending ? "asc" : "desc";
      button.setAttribute("aria-sort", sortAscending ? "ascending" : "descending");
      currentPage = 1;
      render();
    });
  });

  [search, typeFilter, statusFilter, microserviceFilter, suppressionFilter, pageSize].forEach(control => {
    control.addEventListener(control === search ? "input" : "change", () => {
      currentPage = 1;
      render();
    });
  });
  previousPage.addEventListener("click", () => { currentPage -= 1; render(); });
  nextPage.addEventListener("click", () => { currentPage += 1; render(); });
  reset.addEventListener("click", () => {
    search.value = "";
    typeFilter.value = "";
    statusFilter.value = "";
    microserviceFilter.value = "";
    suppressionFilter.value = "";
    pageSize.value = "25";
    currentPage = 1;
    render();
  });
  populateFilter(typeFilter, 1);
  populateFilter(statusFilter, 4);
  populateFilter(microserviceFilter, 5);
  render();
})();
"""


def render_html_report(
    *, generated_at, account_id, environment, account_role, report_rows, metrics
):
    """Render a self-contained HTML report without external assets or scripts."""
    def escape(value):
        return html.escape(str("" if value is None else value), quote=True)

    table_rows = []
    for row in report_rows:
        visible_actions = "<br>".join(escape(action) for action in row["unused_actions"]) or "-"
        suppressed_actions = "<br>".join(escape(action) for action in row["suppressed_actions"]) or "-"
        rule_ids = "<br>".join(escape(rule_id) for rule_id in row["suppression_rule_ids"]) or "-"
        table_rows.append(
            "<tr data-record>"
            f"<td>{escape(row['finding_id'])}</td>"
            f"<td>{escape(row['finding_type'])}</td>"
            f"<td>{escape(row['resource'])}</td>"
            f"<td>{escape(row['resource_type'])}</td>"
            f"<td>{escape(row['status'])}</td>"
            f"<td>{escape(row['microservice_tag'])}</td>"
            f"<td>{visible_actions}</td>"
            f"<td>{suppressed_actions}</td>"
            f"<td>{rule_ids}</td>"
            "</tr>"
        )

    table_body = "".join(table_rows)
    metric_cards = "".join(
        f'<div class="metric"><span>{escape(label)}</span><strong>{escape(value)}</strong></div>'
        for label, value in metrics.items()
    )
    script_nonce = secrets.token_urlsafe(18)
    download_filename = f"iam-unused-access-{environment}-{account_role}-filtered.csv"

    return f"""<!doctype html>
<html lang="it">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'nonce-{escape(script_nonce)}'; object-src 'none'; base-uri 'none'; form-action 'none'">
  <title>IAM unused access report - {escape(environment)}</title>
  <style>
    :root {{ color-scheme: light dark; font-family: Arial, sans-serif; }}
    body {{ margin: 0; padding: 24px; background: #f8fafc; color: #172033; }}
    h1 {{ margin-bottom: 4px; }}
    .metadata {{ color: #526077; margin-bottom: 20px; }}
    .metrics {{ display: flex; flex-wrap: wrap; gap: 12px; margin: 20px 0; }}
    .metric {{ min-width: 170px; padding: 14px; border: 1px solid #d8dee9; border-radius: 8px; background: white; }}
    .metric span {{ display: block; color: #526077; font-size: 12px; }}
    .metric strong {{ display: block; margin-top: 6px; font-size: 22px; }}
    .controls {{ display: grid; grid-template-columns: minmax(220px,2fr) repeat(4,minmax(150px,1fr)); gap: 10px; margin: 20px 0 12px; }}
    .controls label {{ display: grid; gap: 4px; color: #526077; font-size: 12px; }}
    input, select, button {{ font: inherit; padding: 8px 10px; border: 1px solid #aeb8c8; border-radius: 6px; background: white; color: #172033; }}
    button {{ cursor: pointer; }} button:disabled {{ cursor: not-allowed; opacity: .5; }}
    .actions, .pagination {{ display: flex; align-items: center; flex-wrap: wrap; gap: 8px; margin: 10px 0; }}
    .pagination {{ justify-content: flex-end; }} .pagination label {{ display: flex; align-items: center; gap: 6px; }}
    .table-wrap {{ overflow-x: auto; }}
    table {{ width: 100%; border-collapse: collapse; background: white; font-size: 13px; }}
    th, td {{ padding: 9px; border: 1px solid #d8dee9; text-align: left; vertical-align: top; }}
    th {{ background: #eaf0f6; position: sticky; top: 0; }}
    .sort {{ padding: 0; border: 0; border-radius: 0; background: transparent; font-weight: bold; white-space: nowrap; }}
    .sort::after {{ content: " ↕"; color: #64748b; }}
    .sort[data-direction="asc"]::after {{ content: " ↑"; }} .sort[data-direction="desc"]::after {{ content: " ↓"; }}
    td {{ word-break: break-word; }}
    .empty {{ text-align: center; padding: 28px; color: #526077; }}
    @media (prefers-color-scheme: dark) {{
      body {{ background: #111827; color: #e5e7eb; }}
      .metadata, .metric span, .empty {{ color: #aeb8c8; }}
      .metric, table, input, select, button {{ background: #1f2937; color: #e5e7eb; }}
      .metric, th, td {{ border-color: #445066; }}
      th {{ background: #273449; }}
    }}
    @media (max-width: 900px) {{ .controls {{ grid-template-columns: 1fr 1fr; }} }}
    @media (max-width: 560px) {{ .controls {{ grid-template-columns: 1fr; }} body {{ padding: 12px; }} }}
  </style>
</head>
<body>
  <h1>IAM unused access report</h1>
  <div class="metadata">
    Ambiente: {escape(environment)} · Account role: {escape(account_role)} ·
    Account ID: {escape(account_id)} · Generato: {escape(generated_at.isoformat())}
  </div>
  <div class="metrics">{metric_cards}</div>
  <div class="controls">
    <label>Cerca<input id="search" type="search" placeholder="Finding, ARN, azione…"></label>
    <label>Tipo<select id="type-filter"><option value="">Tutti</option></select></label>
    <label>Stato<select id="status-filter"><option value="">Tutti</option></select></label>
    <label>Microservizio<select id="microservice-filter"><option value="">Tutti</option></select></label>
    <label>Esclusioni granulari<select id="suppression-filter"><option value="">Tutti</option><option value="with">Con azioni ignorate</option><option value="without">Senza azioni ignorate</option></select></label>
  </div>
  <div class="actions">
    <button id="reset-filters" type="button">Azzera filtri</button>
    <button id="download-csv" type="button" data-filename="{escape(download_filename)}">Scarica vista filtrata CSV</button>
  </div>
  <div class="table-wrap">
    <table>
      <thead><tr>
        <th><button class="sort" type="button" data-sort-column="0" aria-sort="none">Finding</button></th>
        <th><button class="sort" type="button" data-sort-column="1" aria-sort="none">Tipo</button></th>
        <th><button class="sort" type="button" data-sort-column="2" aria-sort="none">Risorsa</button></th>
        <th><button class="sort" type="button" data-sort-column="3" aria-sort="none">Tipo risorsa</button></th>
        <th><button class="sort" type="button" data-sort-column="4" aria-sort="none">Stato</button></th>
        <th><button class="sort" type="button" data-sort-column="5" aria-sort="none">Microservizio</button></th>
        <th><button class="sort" type="button" data-sort-column="6" aria-sort="none">Azioni inutilizzate</button></th>
        <th><button class="sort" type="button" data-sort-column="7" aria-sort="none">Azioni ignorate</button></th>
        <th><button class="sort" type="button" data-sort-column="8" aria-sort="none">Regole</button></th>
      </tr></thead>
      <tbody id="report-body">{table_body}<tr id="no-results" hidden><td colspan="9" class="empty">Nessun finding corrisponde ai filtri</td></tr></tbody>
    </table>
  </div>
  <div class="pagination">
    <label>Righe per pagina<select id="page-size"><option>25</option><option>50</option><option>100</option></select></label>
    <button id="previous-page" type="button">Precedente</button>
    <span id="page-status" aria-live="polite"></span>
    <button id="next-page" type="button">Successiva</button>
  </div>
  <script nonce="{escape(script_nonce)}">{HTML_REPORT_SCRIPT}</script>
</body>
</html>
"""


def export_html_report(
    *, s3_client, bucket, csv_key, generated_at, account_id, environment,
    account_role, report_rows, metrics
):
    """Render and store the HTML report next to its CSV source report."""
    html_key = csv_key.rsplit(".", 1)[0] + ".html"
    html_bytes = render_html_report(
        generated_at=generated_at,
        account_id=account_id,
        environment=environment,
        account_role=account_role,
        report_rows=report_rows,
        metrics=metrics,
    ).encode("utf-8")
    s3_client.put_object(
        Bucket=bucket,
        Key=html_key,
        Body=html_bytes,
        ContentType="text/html; charset=utf-8",
        ContentDisposition="inline",
    )
    return html_key, len(html_bytes)
