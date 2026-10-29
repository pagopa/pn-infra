---
name: pn-infra-agent-implement
description: Implement an explicitly approved SEND infrastructure plan and report verification evidence.
agent: pn-infra-agent
argument-hint: Identify the presented plan or the task memory to resume
---

Read the `pn-infra` skill's `SKILL.md` from `.github/skills/pn-infra/` or `.agents/skills/pn-infra/` in the workspace (`skills/pn-infra/` in the standalone toolkit checkout), then its `workflows/development.md`. Apply the operating contract before using tools.

Identify the current plan, covered tasks and approval evidence. This command approves implementation only of a specific current plan already presented to the user. If the plan is missing, unpresented or materially stale, prepare or revise it, present it and end the turn awaiting approval before source changes. Follow the workflow's single plan gate rather than inferring approval from the original development request.

With a valid approval, implement only the covered local changes and run the permitted, proportionate verification. Reuse approved task/branch decisions, preserve unrelated work and return for approval of material plan changes. Report changed files, actual checks and pending criteria. Follow the existing separate authorizations for AWS access, deployment, tools and Git operations.
