---
applyTo: "**/*.yml,**/*.yaml,**/*.tf,**/*.tfvars,**/*.sh,**/*-cfg.json,**/Dockerfile,**/Dockerfile.*"
---

For SEND infrastructure analysis, development and review, use the project skill `pn-infra` from `.agents/skills/pn-infra/` or `.github/skills/pn-infra/`, whichever is present in the workspace.

Select its development, local review or PR review procedure from the user's intent. Review preserves source code, Git state and remote systems; both review modes may persist evidence only in an agreed local documentation folder. For a PR unavailable locally, use the PR URL and `workflows/pr-review.md` to acquire, persist and reuse metadata and the complete diff with minimal reads, checking revision freshness before completion. Load only the relevant SEND references, inspect the actual templates and deployment scripts needed to verify the change, and report missing cross-repository evidence instead of inventing it.

For development, read `workflows/development.md` from the skill and use its four visible phase gates; full mode is the default. Do not edit before presenting the plan.
