# Evaluation guide

- [evals.json](evals.json): SEND design, development and review cases.
- [regression-evals.json](regression-evals.json): workflow and permission checks.
- [trigger-evals.json](trigger-evals.json): skill activation checks.
- [fixture-evals.json](fixture-evals.json): cases with supplied input files.
- [benchmark-plan.md](benchmark-plan.md): comparison protocol.

## Run a comparison

Use sanitized fixtures or approved repository snapshots. Keep the task, model, tools and source revision identical across variants, and start an independent session for each run.

Provide the task prompt and its inputs to the evaluated agent. Keep expected answers and paired variants outside its accessible context. Cases with `files: []` require a repository snapshot or a separate fixture.

Record the actual inputs, outputs and assessment results. Treat unavailable files or deployment paths as verification limits. Evaluation definitions and structural checks do not establish that an agent passes a case.

For an unbiased benchmark, use unseen tasks with separate expected results. The included cases are accessible evaluation material and are not automatically executed or loaded as task instructions.

## Paired fixtures

Ten cases cover five scenarios:

| Scenario | What the pair checks |
| --- | --- |
| Shared fragment | Preserve existing callers when adding a parameter; recognize a compatible default. |
| Output contract | Trace an actual script consumer; distinguish a breaking rename from a retained alias. |
| CORE/CONFINFO | Distinguish parameter requiredness from resource conditions. |
| Task memory | Match existing documentation by task content, not just directory name. |
| SQS concurrency | Compare simultaneous mapping limits with Lambda reserved concurrency. |

Follow the [snapshot and staging instructions](fixtures/README.md) and supply only the selected case inputs. Fixtures are synthetic review inputs, not deployment packages; no AWS access is required.
