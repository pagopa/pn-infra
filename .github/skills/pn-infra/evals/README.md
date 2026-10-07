# Evaluation notes

Status: designed, not executed. SEND design, development, and review cases are in [evals.json](evals.json); workflow and permission checks are in [regression-evals.json](regression-evals.json). Preliminary activation checks are in [trigger-evals.json](trigger-evals.json). The comparative run protocol is in [benchmark-plan.md](benchmark-plan.md).

Use sanitized fixtures or approved local repository snapshots. Keep model, tools, source revision and task identical across variants; use independent sessions and record exact inputs and outputs. Do not treat remembered answers as execution evidence.

The packaged skill includes evaluation files. These are public development tests, not a held-out benchmark. For an unbiased comparison, select unseen tasks and keep their expected results outside the runtime workspace. Cases with `files: []` require an approved local repository snapshot or sanitized fixture. Do not score an unavailable file or deployment path as if it had been inspected.

## Paired synthetic fixtures

[fixture-evals.json](fixture-evals.json) defines ten cases with explicit input files, arranged in five pairs:

| Scenario | What the pair checks |
| --- | --- |
| Shared fragment | Preserve existing callers when adding a parameter; recognize a compatible default. |
| Output contract | Trace an actual script consumer; distinguish a breaking rename from a retained alias. |
| CORE/CONFINFO | Distinguish parameter requiredness from resource conditions. |
| Task memory | Match existing documentation by task content, not just directory name. |
| SQS concurrency | Compare two simultaneous mapping limits with Lambda reserved concurrency. |

Follow the [snapshot and staging instructions](fixtures/README.md). Supply only the selected case inputs to the evaluated agent, not its expected output or the paired case. These fixtures are synthetic review inputs, not deployment templates. No AWS access is needed. Structural checks do not establish that an agent passes the cases.

Additional task-memory checks to develop into concrete test cases: keep a proposed decision unapproved; link a superseded decision; decline promoting a task workaround without user approval; perform read-only review without memory writes. A successful result must preserve the next actionable step and actual verification limitations.

The trigger checks are preliminary and have not been run against Copilot discovery.
