# Task knowledge base and documentation sections

Create only the artifacts needed for the active work. Replace placeholders with verified facts or explicitly unresolved questions. Each artifact has one responsibility.

| Artifact | Required sections or fields |
| --- | --- |
| HANDOFF.md | Updated timestamp; current phase and state; next action; blockers and pending decisions; repository locations and revision anchors; relevant artifact links |
| WORKLOG.md | Timestamp; material outcome; affected files; links to decision and verification records |
| DECISIONS.md | Decision ID; proposed/approved/superseded status; scope; evidence; alternatives; choice and rationale; actual confirmation or pending approval; consequences; superseded decision link |
| 01-analysis/BRIEF.md | Objective; expected production behavior; scope and exclusions; repositories/domains/environments; acceptance criteria; existing patterns; unresolved material questions |
| 02-planning/PLAN.md | Brief link; initial decisions and unresolved approvals; new/existing resource scope; CORE/CONFINFO and environment differences; production behavior; solution and reuse; affected files/contracts/dependencies; configurable values and feature flags; pipeline-derived deployment order and transitional compatibility; expected disruption and actual user confirmation when required; rollback/data continuity; monitoring and test strategy |
| 03-implementation/TASKS.md | Plan link; task IDs and checkboxes; affected paths; dependencies; acceptance criterion links; implemented work awaiting verification |
| 04-verification/EVIDENCE.md | Check ID; timestamp; acceptance criterion; repository revision and dirty-tree state; actual command or inspection; passed/failed/not-run result; concise evidence; limitations and remaining checks |

Mark inapplicable design sections with a short reason. Do not invent parameter names or results. Keep HANDOFF compact by linking details. Proposed decisions must never appear as approved. Routine agent choices must be identified as such, without inventing user confirmation.

Record revision and working-tree metadata only when already available or needed to work correctly. Otherwise mark it as unavailable; these fields do not require additional Git commands.

Candidate learnings use a decision record with type `candidate learning`, applicability and a proposed shared destination. They remain proposed until the user approves promotion.

## Epic planning additions

BRIEF includes Jira keys, URLs, issue types and agreed scope. PLAN includes an ordered ticket table with prerequisites, repositories, branches/local bases and links to per-ticket plans. Keep implementation order, manual integration order and deploy order separate. Put order in PLAN, not filename prefixes.

For each included implementation task, `02-planning/PN-<number>.md` contains objective, acceptance criteria, affected files/components, prerequisites, design and steps, verification, unresolved decisions and a link to TASKS for status. TASKS remains the single local progress record; HANDOFF identifies the active ticket and any manual integration blocker.

## PR review artifacts

| Artifact | Required sections or fields |
| --- | --- |
| pr-review/METADATA.json | Complete metadata response saved directly into the agreed folder before reading it; acquisition must succeed and refer to the identified PR |
| pr-review/DIFF.patch | Complete raw patch saved directly into the agreed folder with pager disabled, without terminal or shell-variable staging; disclose incomplete coverage or redactions in DIFF.md |
| pr-review/CONTEXT.md | Full PR URL, owner/repository/number; title/body; base/head branches and SHAs; acquisition time and source; changed files; relevant ticket links; evidence limitations; link to METADATA.json when present |
| pr-review/DIFF.md | Base/head SHAs and acquisition source/time; link to the complete local DIFF.patch; explicit missing/binary/truncated coverage or secret redactions. Existing complete inline patches remain valid, using a fenced diff block with a delimiter longer than any conflicting fence in the patch |
| pr-review/REVIEW.md | Reviewed revision; findings with file/line, triggering condition, impact and evidence; material questions; coverage and unexecuted checks |
| HANDOFF.md | Current review revision/state, next investigation, blockers and links to the three review files |
| WORKLOG.md | Significant acquisitions, revision changes and progress, without duplicating patch or findings |
| DECISIONS.md | Actual material decisions and unresolved choices, approval status and evidence links |

Agree the memory parent path and folder name before any interactive review `gh` command, then prepare the folder before acquisition. Do not create PLAN or TASKS for PR review. Link raw captures instead of duplicating long patches. Do not rewrite the acquired patch from memory or silently replace a full diff with excerpts. Never store secret values; disclose redaction and its effect on fidelity. Permission to write review documentation is not permission to edit sources or publish remotely. Interactive external PR review requires these files in a user-approved folder under agents-memories; if permission is refused, stop before acquisition. Automatic review services follow their non-interactive exception.

## Local review report

`local-review/REVIEW.md` contains the review date, objective, repository and scope, comparison base/revision when available, findings with file/line, triggering condition, impact and evidence, material questions, coverage and unexecuted checks. State explicitly when there are no supported findings. It belongs in the agreed task memory and does not require development PLAN/TASKS or a stored complete diff. Reuse available revision metadata without commands solely to fill fields.
