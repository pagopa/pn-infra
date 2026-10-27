# Development procedure

## Select full or light

Use **full** unless the user explicitly requests light mode. Full mode can be requested explicitly but is already the default. Light is eligible only for an isolated, reversible local change with no shared fragment or contract, cross-repository propagation, persistent-resource lifecycle, data-continuity, or deployment implications. If light is requested for a change outside that boundary, explain why full is needed before proceeding. The user does not need to choose a mode for an ordinary request.

Both modes must make **Analysis → Planning → Plan approval → Implementation → Verification** visible, in order. Approval is a gate between the four work phases, not another artifact or development mode. Keep the agreed requirements as the reference: Analysis establishes them, Planning links changes and checks to them, Verification records the observed result. Present the plan, end the turn and wait for explicit user approval before source implementation, even when the original request says to develop or fix the feature. Other phase transitions need no repeated approval unless a material decision or separate execution authorization requires it. Analysis-only and review requests do not start this sequence.

In **full**, keep BRIEF, PLAN, TASKS and EVIDENCE in a [knowledge base and documentation folder for the task](../references/task-memory.md), updating HANDOFF and WORKLOG at meaningful changes. Reuse an existing folder when it belongs to the same task. If none exists, ask the single concise question defined in the memory contract, propose the path, and wait for the answer before creating it. Do not silently fall back to light because documentation is inconvenient. In **light**, present the same four phase outcomes briefly in chat; no new documentation folder is required, but update an existing relevant task memory when needed for handoff. Neither mode authorizes changes outside the user's scope.

## Plan approval and chat commands

The same gate applies with or without a command. `/pn-infra-agent-plan` selects Analysis and Planning only; `/pn-infra-agent-implement` requests implementation of an identified plan. These Copilot prompts route to this workflow and do not define another set of rules.

Before asking for approval, present a concise plan in chat with:

- requested outcome, scope, acceptance criteria and implementation strategy, including reuse of existing components where relevant;
- ordered implementation tasks, prerequisites and the files to create or modify for each task, with the purpose of each change;
- compatibility, configuration, data and operational impacts where relevant, distinguishing implementation, integration and deployment order;
- proposed checks, expected results and verification limits, including checks requiring separate permission.

Scale detail to the change. A light plan can be a few lines; full mode records the same plan in PLAN/TASKS and links it from chat. Reads and agreed planning-documentation updates may precede approval; source edits, code generation and implementation commands may not.

Ask whether the user approves this plan for the listed local changes, then end the turn. Accept an explicit reply such as approval or an instruction to implement the just-presented plan; no exact phrase is required. Invoking `/pn-infra-agent-implement` counts as that instruction only when the specific current plan has already been presented to the user. If it is missing, has not been presented, or no longer matches the task, prepare or revise it, present it and wait. Silence, an initial development request, agreement to a memory folder or a branch, and tool-execution consent do not approve an unseen implementation plan.

One approval covers the listed tasks, including multiple epic tasks if explicitly planned together. Do not ask again for each file or phase. Record the actual confirmation and covered scope in the existing PLAN or decision record and the handoff; in light mode the conversation is sufficient. On resumption, reuse that approval only if current sources and requirements still support the same plan. Material changes to scope, affected files or dependencies, behavior, environment or operational risk require a revised plan and new approval before the affected implementation. Routine technical choices within the approved plan do not.

Plan approval does not authorize deployment, live AWS queries, Git integration or other separately restricted operations. When an enclosing framework already owns the plan and explicit human approval, reuse that record instead of duplicating it; the initial request alone is insufficient.

## Ticket context and epic planning

When a Jira ticket or relevant Confluence page is supplied, follow [Atlassian context](../references/atlassian-context.md). Reading context does not authorize implementation. Respect the user's chosen task subset; report conflicting or inaccessible acceptance criteria.

Use full mode for implementing multiple tasks of an epic, with one shared memory and per-ticket plans as defined in [task memory](../references/task-memory.md). At Planning, separate:
- implementation order and prerequisites;
- manual integration order between branches;
- deployment order derived from actual pipelines, contracts and transitional compatibility.

Do not derive these orders from ticket numbers. Distinguish confirmed dependencies from hypotheses; block dependent work when prerequisites or cycles remain unresolved. Present the overall plan and obtain approval for its included task plans before implementing.

If separate branches are requested, propose each repository's local base, epic branch and task branches. Feature names are `feature/PN-<number>`, without a descriptive suffix. Children may branch from the epic, but do not automatically inherit its later changes or sibling work. Identify manual integration checkpoints. Approval covers only the listed local branch creations/selections; inspect branch and working-tree state first and stop rather than moving or discarding unrelated changes. Local commits follow the procedure below; merge, rebase and cherry-pick remain manual. Do not push, pull or fetch. Wait for the user's integration before dependent implementation.

## Phase gates

1. **Analysis:** Locate the owning source artifact before deciding which repositories are affected. Use names and paths in the request to narrow the search; do not infer ownership from the open repository or a deployment script. Inspect the current behavior, affected callers and applicable SEND rules. Use branch and working-tree information already exposed by the environment or prior evidence; do not request a terminal command solely to collect them. Report the branch when known. If it is a default or protected branch, is clearly unrelated to the task, or its suitability is uncertain, ask the user to confirm it before the first source edit; do not ask when the intended branch has already been confirmed. If branch or working-tree state is unavailable and materially necessary for safe editing, explain why one read-only check is needed before requesting it. Only create or select branches under the approved strategy below; never synchronize Git remotely, and do not query a commit hash solely to complete task-memory metadata. Summarize the requested outcome, scope, exclusions, CORE/CONFINFO domains and environments, expected behavior and observable acceptance criteria as applicable. Distinguish confirmed requirements from source facts and material unknowns. Resolve facts from code; use the discovery interview for choices evidence cannot settle. Identify repository-provided validation from focused configuration, documentation or workflow lookups; search scripts only when those sources do not establish the check. Select relevant verification checks without executing or inventorying them here. In full, record these findings in BRIEF. State the analysis outcome before planning.
2. **Planning:** First check requirement clarity, then the other [initial planning decisions](#initial-planning-decisions-and-system-impact). Resolve material gaps before finalizing the dependent plan; proceed without an interview when the requirements are sufficient. Apply [simplicity-check](../reasoning/simplicity-check.md). Link each change and proposed check to an agreed requirement or acceptance criterion; state affected files/contracts, compatibility and relevant configuration or flags. Trace deployment wiring only where it matters. In full, write PLAN and initial TASKS using the BRIEF criteria. Present the ordered plan and request approval following [the plan gate](#plan-approval-and-chat-commands); end the turn before source edits. Use [discovery-interview](../reasoning/discovery-interview.md) for open choices and [decision-gates](../reasoning/decision-gates.md) for authorization; reuse existing answers and approvals for the same presented plan.
3. **Implementation:** Confirm that the current plan was presented and explicitly approved, then make the smallest coherent change it describes. Follow real inputs and outputs when relevant, check existing callers before changing shared fragments, and preserve unrelated working-tree changes. In full, update TASKS and WORKLOG with coherent increments. If evidence materially changes the plan or scope, return to Planning, present the revision and obtain approval before the affected implementation.
4. **Verification:** Select the minimum local checks needed for the acceptance criteria, then run them and compare the result with expected behavior, not merely syntax. Inspect the diff and available editor diagnostics first; do not duplicate a lint result with a terminal invocation. Defer approval-requiring check commands to this phase unless an earlier result was necessary to implement safely. When possible, combine related read-only checks into one clearly explained approval request; do not include unrelated or state-changing operations. Do not run deployments or Terraform operations requiring remote access without authorization. If codegen is required, follow the applicable guideline and report pending generated artifacts. Show the evidence for calling a diagnostic pre-existing or unrelated. In full, record actual results and gaps in EVIDENCE, then refresh HANDOFF. Report what passed, what failed or remains unverified, and the next step. Do not claim completion for an untested acceptance criterion.

Handoff and worklog are continuous records, not a fifth phase. Before Implementation, run a check only when its result is necessary to resolve a material decision or safely make the change and cannot be obtained from existing evidence or file inspection. Defer other checks to Verification. CloudFormation lint has a single CLI-attempt budget for the task; do not duplicate editor lint or automatically retry it. Do not silently expand scope or turn a read-only request into edits.

## Local commit

After an approved development implementation passes every required verification, automatically create a local commit for that task if the user has not declined it and client permissions permit. Include this step in the plan. The subject begins with the identified Jira task key, `PN-<number>`, followed by a concise description, for example `PN-21072: Enable load balancer deletion protection`. Use the user's configured Git identity; do not add a `Co-authored-by` trailer unless a higher-priority client rule requires it.

Before committing, inspect the changes and staging state. Include only changes covered by the approved plan, preserve unrelated staged and unstaged work, and do not amend an existing commit. If the task key is unknown or ambiguous, required verification failed or remains incomplete, the approved changes cannot be separated safely from unrelated work, or no changes remain, stop without committing and explain the reason; ask the user to identify the task when needed. Surface Git or hook failures and never bypass them silently. Report the resulting commit identifier and verification limits. A local commit does not authorize merge, remote synchronization, deployment or any live AWS operation.

## Initial planning decisions and system impact

Analysis gathers evidence. At the start of Planning, before defining implementation steps, assess every decision below. Record the supported conclusion or a brief reason why it does not apply. This assessment is mandatory in both modes, not a mandatory interview questionnaire: resolve facts from sources and confirmed decisions first. Bring unresolved material choices into the discovery interview, one question at a time, before finalizing the dependent plan or implementing it. Do not defer this assessment to the final report.

| Unresolved decision | Establish before implementing |
| --- | --- |
| Requirement clarity | Requested outcome, scope/exclusions, expected behavior and observable acceptance criteria; recipients or monitored signals when applicable. Resolve facts from evidence and ask about material choices before finalizing dependent steps. |
| Scope and existing state | New resources versus changes to existing ones; owning repository, stack, callers and consumers. A definition in Git does not establish deployed state; disclose unavailable state when it matters. |
| Domains and environments | CORE, CONFINFO or both; affected environments; configuration, activation and sizing differences. Do not automatically extend rollout to every environment. |
| Production behavior | Business capability, monitoring or platform support; dependencies, load, failures and recovery. Design for production from the outset without copying production capacity into dev. |
| Configurability and flags | For each new capability, assess whether enabling, disabling or changing modes without a code release is needed. Define defaults and effects on data, queued and in-flight work and reactivation. Reuse configuration mechanisms; avoid purposeless flags and distinguish disabling behavior from deleting resources or avoiding deployment. |
| Deployment order | Trace the actual SEND pipelines and scripts to derive component update order and temporary compatibility between old and new versions. Never assume CONFINFO must precede CORE. Identify a procedure or pipeline change requiring agreement if the current path cannot support the sequence. |
| Service continuity | Assess interruption, degradation, unavailable integrations and backlog during the transition. Distinguish necessary planned disruption from unintended risk and consider feasible alternatives. Obtain explicit user confirmation of a disruption-requiring solution before finalizing the dependent plan or implementing it. No outage-duration estimate is required. Approval of the design does not authorize deployment. |
| Data continuity | Acceptable replay, data retention and replacement impact; obtain explicit approval for stream starting-position changes |
| Shared contract | Callers affected by a parameter/output change and compatibility expected during rollout |
| Success and recovery | Observable checks for final behavior and critical transitions, including flag changes where relevant; stop/recovery conditions and rollback limits. Propose technical checks rather than asking the user to design them. |

Do not ask for account IDs or parameter names that can be read from the relevant sources. Do not infer approval for a destructive or wider change from an unanswered question.

## Completion report

Return changed behavior and files, checks run with actual results, pending checks or generated files, and material decisions still needed. Do not mark a task verified while an acceptance criterion remains untested.
