# pn-infra skill specification

Classification: process toolkit for SEND IaC, executed inside a coding assistant. Development has four mandatory, visible phases (analysis, planning, implementation, verification). Full mode is the default and records phase artifacts in a knowledge base and documentation folder for the task; explicitly requested light mode retains the four visible gates without requiring a new folder for an eligible isolated change. Local review and PR review are separate read-only procedures. HANDOFF and WORKLOG are continuous task/review records. Both review modes may write agreed documentation, never source or remote state. The canonical memory contract and artifact sections live in `references/task-memory.md` and `templates/task-documentation.md`. These prompt-based procedures are not a deterministic orchestration engine.

## Intent and scope

One SEND-specific skill supports analysis, local development, local review and review of a GitHub PR that is not checked out locally. It uses shared infrastructure knowledge without turning general AWS documentation into a mandatory checklist. Primary users are the SEND Infra team and their coding assistants.

Out of scope: autonomous deployment, production operations, automatic PR approval, application-only development and a company-wide software lifecycle. Changes to these boundaries require an explicit design decision.

## Shape and runtime contract

Class: workflow-process. Primary shape: reference-backed expert, with three intent-selected procedures. Inline-only guidance would force every task to load the entire SEND corpus. Multi-agent orchestration and provider-specific hooks are unnecessary for this toolkit.

The entry point selects analysis, development, local review or PR review. Development presents analysis and plan before editing, then implementation and verification; the two review procedures return evidence-backed findings without source edits; Both review modes persist evidence only in the agreed documentation folder. They use the same domain references. PR review retrieves the identified PR's metadata and diff, then reads only the additional source context needed for supported findings. Full development preserves approved decisions, source revisions, results and next steps in one existing memory system.

The Copilot package includes three distinct adapters: a path-specific instruction that points infrastructure files to the skill, the project skill itself, and a manually selectable custom agent that guarantees interactive routing through the skill. The custom agent contains no duplicate SEND rules. Copilot code review consumes the repository instruction and skill directly; it does not depend on selecting the interactive custom agent.

The organization-wide distribution model is outside this skill specification and remains to be defined.

Instructions express intended behavior; they are not a security boundary. Host permissions and deterministic validation remain necessary.

## Evidence and maintenance

The two imported SEND documents are a dated local snapshot, not proof of the current implementation. Relevant repository sources establish actual wiring. Conflicts remain explicit until reconciled. See the project SOURCES.md for provenance and migration gaps.

SKILL.md holds routing and universal constraints; workflows hold development, local review and PR review procedures; reasoning holds focused simplicity, interview and decision-gate guidance; references hold SEND domain content and task-memory guidance. SPEC.md is for maintainers, not a required runtime read. The persona delegates to the skill rather than copying its rules. Installed files come from the maintained source.

Update this specification when scope, permissions, routing, evidence policy or evaluation changes. Update provenance when adding or changing a domain rule. Do not promote a task-specific workaround into a shared rule without review. Never retain secret values or sensitive payloads in examples or memory.

## Validation and acceptance

Structural checks cover frontmatter, linked files and portable paths. These do not establish model behavior.

Behavioral evaluation must cover development, review, ambiguous intent, missing cross-repository evidence and resumed work. Compare the same task and source revision with the same model/tool, with and without SEND context, in isolated sessions. Record correctness, regressions, unsupported findings, user interventions, elapsed active time and tokens only when measurable. Report waiting time separately if measuring through approved review.

The pilot is not accepted until development preserves existing callers, review avoids unsupported findings, permissions are respected and another session can resume from the recorded evidence. Real Copilot skill discovery and review invocation must be checked separately from local structural validation.

## Current limitations

The rule corpus has completed its initial reconciliation but is not an exhaustive representation of every historical SEND convention. Repository evidence still takes precedence when implementation details have changed. No end-to-end behavioral benchmark or Copilot pilot has passed yet.

## Ticket, branch and review-memory contract

Atlassian reads follow references/atlassian-context.md: single-ticket scope or actual epic descendants, explicit subsets, complete pagination and no remote writes. Missing access offers consensual setup or supplied content, not automatic installation/authentication.

Multi-task epics use full mode and one memory with PLAN and per-ticket plans in 02-planning. Distinguish implementation, manual integration and deploy order. Approved per-repository strategies permit local feature/PN-<number> branch creation/selection after protecting existing changes. Commit and integrations remain manual; remote Git synchronization is excluded.

Interactive PR review requires a user-approved folder under agents-memories before any acquisition or gh invocation, including diagnostics. It searches/reuses memory by the supplied PR identity, agrees both parent location and folder name before creating folders or querying GitHub, and permits task, PR-related or custom names. It prepares the agreed folder before acquisition, disables the pager per command and saves raw metadata and the complete patch directly as METADATA.json and DIFF.patch under pr-review, without terminal or shell-variable staging. CONTEXT, DIFF and REVIEW retain metadata, acquisition provenance and findings; DIFF can link the raw patch, and existing inline patches need no migration. The review reuses the full diff, preserves prior successful evidence if a refresh fails, checks base/head revision on resume and completion, and reports incomplete/redacted/stale evidence. If documentation is declined, clarify the limited local-write requirement and stop before acquisition unless approved. Automatic reviews retain their non-interactive exception. Behavioral evaluations cover these gates separately from structural checks.

Local review offers an agreed `local-review/REVIEW.md` in the task memory, preserving source and Git state and supporting chat-only review. PR review requests consent before installing a missing GitHub CLI and uses it only for remote reads; the review request authorizes relevant reads subject to client permissions.
