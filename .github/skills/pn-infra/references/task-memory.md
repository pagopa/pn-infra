# Durable task memory

In full development mode, use a dedicated knowledge base and documentation folder even for a small implementation. Before proposing a new folder, list the existing task folders in Agent Memories (a shallow tree or file listing is enough). Search exact Jira keys or PR identity in folder names and relevant contents as well as the task's component and objective, allowing for different wording; read HANDOFF or BRIEF in plausible matches to confirm whether they cover the same work. Reuse a matching folder even if its name differs from the proposed topic. If several folders could match, ask which one to use. Only when none is relevant, ask one concise question in the user's language, equivalent to: “This task does not yet have a dedicated folder. Would you like me to create one in Agent Memories for its knowledge base and documentation? Proposed path: `agents-memories/<task-topic>/`.” Wait for the answer before creating it. Do not call the folder mandatory, restate that confirmation is required, or repeat the question in a second sentence. Prefer workspace file listings over a terminal command when available; do not recursively read unrelated memories. In light mode, a small task needs no new documentation folder. Analysis-only requests do not authorize creating memory files. Local review and PR review follow the documentation agreements below; neither authorizes source edits.

Keep objective, scope, relevant source paths and revisions, approved decisions, open questions, completed work, verification results and next steps. Record concise outcomes and rationale, not private reasoning or full transcripts. Exclude credentials and sensitive payloads.

Maintain these Markdown files through direct reads and edits. Updating a plan or memory does not require a link checker, directory scanner, parser or custom Python/Node script. Follow the entry point's command-necessity rule; do not add a documentation-validation step to each update.

A full-mode task documentation folder uses the layout below. Create the four phase artifacts as their gates are reached. Handoff is continuous, not a phase. Existing historical task memories remain readable without mandatory migration.

```text
agents-memories/<topic>/
├── HANDOFF.md
├── WORKLOG.md
├── DECISIONS.md
├── 01-analysis/BRIEF.md
├── 02-planning/PLAN.md
├── 03-implementation/TASKS.md
└── 04-verification/EVIDENCE.md
```

Use [artifact templates](../templates/task-documentation.md) when creating these files. BRIEF owns scope and acceptance criteria; PLAN owns the solution; TASKS owns task completion; EVIDENCE owns check results. Link their content rather than duplicating it.

WORKLOG is a chronological, append-only record of material changes, findings and decisions. Record coherent increments, not every command. DECISIONS owns material choices, alternatives, rationale, consequences and approval status. Link superseded decisions rather than deleting them. HANDOFF is the current snapshot: phase, next action, blockers, source revisions and links. Refresh it whenever those change and before pausing or handing off.

On resumption, read HANDOFF first and follow relevant artifact links. Compare recorded evidence with current files and repository information already exposed by the client. Preserve unrelated edits; do not restore files from memory. Do not run Git commands solely to populate revision or working-tree metadata: record that information as unavailable when it is not needed for the task. Before Implementation, run a check only when its result is necessary to resolve a material decision or safely make the change and cannot be obtained from existing evidence or file inspection; defer other checks to Verification. If the task requires the latest remote state and repository freshness is uncertain, ask the user to update the relevant repositories before proceeding; do not pull automatically.

Update it after an approved material decision, a meaningful verification result, or before handoff; not after every tool call. Record source revision and file paths where available, and distinguish proposed decisions from approved ones. A new session must recheck changed sources and permissions: a historical approval is not authority for a different action.

For a substantial task, keep the current status in this compact shape:

```markdown
## Objective and scope
## Acceptance criteria
## Evidence and source revisions
## Approved decisions and unresolved questions
## Completed work and actual verification
## Next step and blockers
```

Record reusable discoveries in DECISIONS as candidate learnings with evidence, applicability and a proposed destination. Check current sources and existing rules, then obtain explicit user approval of the proposed shared-rule change before modifying toolkit references. Completing a task does not authorize promotion. Update source provenance when incorporating an approved learning. Never use temporary directories for persistent task memory.

## Jira identity and epic memory

For a new Jira task/epic memory, propose `agents-memories/PN-<number>/`. Do not rename an existing matching folder merely to enforce this convention. Check whether the task already belongs to an epic memory before creating a separate folder. Record Jira keys, URLs, issue type and agreed included/excluded scope in BRIEF; preserve active ticket and next step in HANDOFF.

Use one folder for a multi-task epic, not one folder per child:
```text
agents-memories/PN-<epic>/
├── HANDOFF.md
├── WORKLOG.md
├── DECISIONS.md
├── 01-analysis/BRIEF.md
├── 02-planning/
│   ├── PLAN.md
│   ├── PN-<task-a>.md
│   └── PN-<task-b>.md
├── 03-implementation/TASKS.md
└── 04-verification/EVIDENCE.md
```

PLAN owns the overall order table: ticket/link, prerequisites, repository, branch/base and state links; distinguish implementation, manual integration and deploy sequences. Ticket filenames retain identity, not ordering prefixes. Each per-ticket plan owns objective, acceptance criteria, affected components/files, prerequisites, design/steps, verification and open decisions. Create plans only for tasks included in implementation. TASKS is the single operational status record; link it rather than copying status into each plan. Local status is not Jira status. Record manual integration blockers explicitly. A single task uses PLAN without redundant per-ticket plans.


## Local review memory

Offer to save the local review report unless the user has already requested or declined it. Search and reuse the task's existing memory by ticket, component and objective. Save under `local-review/REVIEW.md` in that memory; if none matches, propose `agents-memories/<task-or-review-topic>/local-review/REVIEW.md`. An explicit request to save the report authorizes that documentation; otherwise agree the location before writing. A chat-only review remains available.

The report records repository and reviewed scope (files, working-tree changes or comparison base), known revision context, findings, evidence, material questions and verification gaps. Reuse available metadata; do not run Git merely to fill report fields. At resumption, recheck the affected sources before reusing findings. Update existing HANDOFF/WORKLOG only for meaningful review outcomes; a new review memory needs no development phase folders or mandatory PLAN/TASKS. Documentation never authorizes source changes or remote publication.

## PR review memory

Interactive external PR review requires an agreed folder under `agents-memories/` before any PR acquisition or `gh` command. Search for matching memory, propose its reuse or a new folder name, and let the user confirm or choose the folder. Create or reuse the approved folder before capturing evidence. If the user says 'read-only', 'only here' or 'do not modify anything', explain that sources and GitHub stay unchanged but local evidence files are required, and ask for that limited permission. If local writes are refused, stop before acquisition; never override the refusal. Automatic code-review services retain their non-interactive exception.

```text
<agreed-memory>/
├── HANDOFF.md
├── WORKLOG.md
├── DECISIONS.md
└── pr-review/
    ├── METADATA.json
    ├── DIFF.patch
    ├── CONTEXT.md
    ├── DIFF.md
    └── REVIEW.md
```

Include the owner in the folder name if needed to disambiguate repositories. METADATA.json and DIFF.patch receive the complete raw captures directly, with the pager disabled; do not use terminal scrollback or shell variables as an intermediate evidence store. CONTEXT identifies the PR and base/head revisions and links the metadata; DIFF records acquisition and links the complete patch; REVIEW owns findings and coverage. Existing memories with the full patch embedded in DIFF remain valid without migration. See [templates](../templates/task-documentation.md) and [PR review](../workflows/pr-review.md) for acquisition and freshness rules. These documentation writes do not authorize source, Git or remote changes.

HANDOFF records current review revision, state and next investigation; WORKLOG records meaningful acquisitions/progress; DECISIONS records only material decisions and unresolved choices. Keep them brief and link the evidence. No implementation PLAN or TASKS is required for PR review. Do not duplicate secrets in the patch: redact values, clearly mark the redaction and disclose that the stored evidence is no longer byte-exact. Do not present truncated or redacted material as a complete unmodified patch.
