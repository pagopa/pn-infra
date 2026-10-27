---
name: pn-infra-agent-plan
description: Analyze a SEND infrastructure task and present an implementation plan for approval.
agent: pn-infra-agent
argument-hint: Describe the task or provide its Jira key or epic URL
---

Read the `pn-infra` skill's `SKILL.md` from `.github/skills/pn-infra/` or `.agents/skills/pn-infra/` in the workspace (`skills/pn-infra/` in the standalone toolkit checkout), then its `workflows/development.md`. Apply the operating contract before using tools.

Run Analysis and Planning only for the user's task. Reuse the matching task memory and confirmed requirements; apply full/light eligibility and the memory agreement rules. Present ordered tasks, files to create or modify and their purpose, dependencies, relevant impacts and acceptance-linked checks.

Follow the workflow's plan-approval gate: for a new or materially revised plan, request approval and end the turn. If the same presented plan remains approved and current, report that status and stop without requesting duplicate approval. Do not edit source files or execute implementation commands. An existing approval does not make this planning-only command an implementation request.
