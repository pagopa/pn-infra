# AWS Cost Analysis Script

Fetches **daily costs** from AWS Cost Explorer grouped by **Service** and the custom tag **Microservice** for the last 6 months, across multiple environments and AWS accounts.

| Output | Description |
|---|---|
| `aws_cost_analysis_<env>_YYYYMMDD.xlsx` | Per-environment Excel workbook (one file per env) |
| `aws_cost_analysis_YYYYMMDD.html` | Self-contained interactive HTML dashboard (all envs combined) |

## Environments & SSO profiles

| Environment | Profiles used |
|---|---|
| `dev` | `sso_pn-core-dev`, `sso_pn-confinfo-dev` |
| `uat` | `sso_pn-core-uat`, `sso_pn-confinfo-uat` |
| `test` | `sso_pn-core-test`, `sso_pn-confinfo-test` |
| `hotfix` | `sso_pn-core-hotfix`, `sso_pn-confinfo-hotfix` |
| `prod` | `sso_pn-core-prod`, `sso_pn-confinfo-prod` |

If a profile is not authenticated or doesn't exist, that account is skipped with a warning and processing continues.

## Requirements

```bash
pip install -r requirements.txt
```

## Usage

```bash
# Log in to the profiles you need first
aws sso login --profile sso_pn-core-dev
aws sso login --profile sso_pn-confinfo-dev
# ... repeat for each env/account combination

# Analyse specific environments
python aws_cost_analysis.py --env dev prod

# Analyse all environments
python aws_cost_analysis.py --all

# Custom output directory
python aws_cost_analysis.py --all --output-dir ./reports
```

## What it generates

### Excel workbook (one per environment) – sheets

| Sheet | Content |
|---|---|
| **By Service** | Monthly cost pivot (rows = services, cols = months) + embedded bar chart |
| **By Microservice Tag** | Monthly cost pivot by microservice tag + chart |
| **By Account** | Monthly cost pivot by account type (core / confinfo) + chart |
| **Trend by Service** | Month-over-month Δ USD + Δ % for the two most recent months, colour-coded |
| **Trend by Tag** | Same as above, by Microservice tag |
| **Daily Detail** | Full raw dataset with auto-filter (includes Env + Account columns) |

### HTML dashboard – filters & charts

**Filters** (all combinable, react on Apply):
- Environment (multi-select)
- Account (multi-select: core, confinfo)
- Service (multi-select)
- Microservice Tag (multi-select)
- Month (single)

**Charts** (all update on filter change):
- Monthly cost stacked by environment
- Cost by Service – Top 15 (horizontal bar)
- Cost by Microservice Tag – Top 15 (horizontal bar)
- Cost by Account stacked by environment
- Daily cost trend (line)

**Trend tables** – computed live from the filtered data; top 20 movers (service + tag) with ▲/▼ badges

**Detail table** – sortable by any column, paginated (100 rows/page), includes Env + Account columns

### Console output

After running, the script prints the top-10 cost movers across all selected environments.
