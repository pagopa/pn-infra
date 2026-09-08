# Group Prowler failed findings

Python helper that collapses Prowler scan results so the **same failed check** is reported once, even when it hits many resources (for example many ECS task definitions).

Use it to review high/critical noise and decide what belongs on a [Prowler mutelist](https://docs.prowler.com/projects/prowler-open-source/en/latest/tutorials/mutelist/).

## Requirements

- Python 3.9+
- No extra packages
- Input: Prowler CSV (`;` delimited) or OCSF JSON array

## Usage

```bash
# High + critical FAILs, plus a commented mutelist skeleton
python3 group_failed_findings.py -i prowler-core.csv --min-severity high --emit-mutelist

# All FAIL checks
python3 group_failed_findings.py -i prowler-core.csv

# OCSF JSON
python3 group_failed_findings.py -i prowler-core.ocsf.json --min-severity high
```

### Options

| Flag | Default | Meaning |
|---|---|---|
| `-i`, `--input` | `prowler-core.csv` | Prowler CSV or `.json` |
| `-o`, `--output-dir` | `grouped_findings` | Output directory |
| `--min-severity` | `low` | Keep this severity and worse (`critical`, `high`, `medium`, `low`, `informational`) |
| `--include-muted` | off | Also keep findings already `MUTED=True` |
| `--sample-resources` | `8` | Example resource names per check |
| `--emit-mutelist` | off | Write `mutelist_candidates.yaml` |

Only `STATUS=FAIL` rows are grouped. `PASS` / `MANUAL` are ignored.

## Output

Written under `grouped_findings/` (or `--output-dir`):

- `grouped_failed_checks.csv` — one row per `CHECK_ID`
- `grouped_failed_checks.json` — same data, including description / risk / remediation
- `mutelist_candidates.yaml` — Prowler mutelist template (only with `--emit-mutelist`)

Each grouped row includes severity, fail count, unique resources, service, regions, accounts, sample resource names, and status-extended samples.

## Mute list workflow

1. Run with `--min-severity high --emit-mutelist`.
2. Review `grouped_failed_checks.csv` (or JSON).
3. In `mutelist_candidates.yaml`, uncomment only the checks you accept as false positives / accepted risk.
4. Pass that file to Prowler (`--mutelist`).

Every generated mute entry is **commented out** on purpose so nothing is silenced until you review it.

## Example

On `prowler-core.csv`, high+critical collapsed **1154 FAIL rows → 44 unique checks** (5 critical, 39 high). ECS readonly-root findings (`ecs_task_definitions_containers_readonly_access`) appear once instead of 147 times.
