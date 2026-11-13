# pn-infra-ai-toolkit

SEND infrastructure guidance for AI-assisted development, local review and PR review, with rules for CloudFormation, Terraform and CI/CD.

## Use with Copilot

Open the workspace and select **pn-infra-agent**, or ask the default agent to use the `pn-infra` skill.

- **Development:** provide the task, scope and available context.
- **Local review:** provide the local files or diff to review.
- **PR review:** provide the GitHub pull request URL.

Development starts with discovery and a proposed plan. Implementation waits for explicit approval of that specific plan. Two optional prompt commands expose the same workflow:

- `/pn-infra-agent-plan`: prepare and present the plan, then stop for approval.
- `/pn-infra-agent-implement`: implement a specific current plan already presented to you. If the plan is missing, unpresented or materially stale, present or revise it and wait for approval.

Natural-language development requests follow the same approval gate in both full and light mode. Approval is reused while the scope remains valid; material plan changes require renewed approval. These commands do not introduce a new workspace or parallel execution.

After approved development and successful required verification, the agent creates a local commit for the approved changes, with a subject starting with the Jira task key (for example `PN-21072: ...`). It stops if the key is missing, checks fail or unrelated changes cannot be safely excluded. The preferred message has no `Co-authored-by` trailer unless a higher-priority client rule requires it. Local commits do not authorize integration, remote synchronization or deployment.

Interactive PR reviews require an agreed folder under `agents-memories/` for metadata, the complete diff and review findings. The review does not change source code or publish actions on GitHub.

Copilot Code Review on GitHub uses repository skills and instructions independently of the interactive custom agent.

## Install the complete toolkit

No installation is required in this checkout. To install the toolkit in another workspace, run from the `pn-infra` repository root:

```sh
bash ai-toolkit/scripts/install-copilot-agent.sh /path/to/workspace
```

Requires Bash and standard macOS/Linux utilities. The script installs or updates:

- `.github/skills/pn-infra/`, including evals and fixtures;
- `.github/agents/pn-infra.agent.md`;
- `.github/instructions/pn-infra-ai-toolkit.instructions.md`;
- `.github/prompts/pn-infra-agent-plan.prompt.md`;
- `.github/prompts/pn-infra-agent-implement.prompt.md`.

Unchanged components are skipped. Replaced components are backed up under `.pn-infra-toolkit-backups/install-XXXXXXXX/previous/`. The two prompt files are copied individually, preserving unrelated prompts. Other skills and settings are left unchanged. Keep backups outside commits.

Archive alternative installations under `.agents/skills/` and legacy toolkit names before installing to avoid duplicate discovery. Start a new Copilot chat and select **pn-infra-agent** after installation.

## Install only the skill

From the target repository root, choose one command. Do not combine it with the complete-toolkit installation.

With a GitHub CLI version that supports `gh skill install`:

```sh
gh skill install pagopa/pn-infra .github/skills/pn-infra --allow-hidden-dirs --agent github-copilot --scope project
```

With Node.js and npm:

```sh
npx skills add pagopa/pn-infra --skill pn-infra --agent github-copilot --copy
```

Both install the skill under `.agents/skills/pn-infra/`. They do not install the custom agent, repository instructions or prompt commands. The `npx` command uses the [`skills` CLI](https://github.com/vercel-labs/skills).

## Optional terminal approvals

```sh
bash ai-toolkit/scripts/install-copilot-agent.sh /path/to/workspace --configure-approvals
```

This option asks for consent before copying `ai-toolkit/copilot/terminal-approvals.settings.json` into a new `.vscode/settings.json`. Existing settings are not overwritten; merge the preset manually in VS Code when required.

The preset allows common read commands (`pwd`, `ls`, `tree`, `grep`, `rg`, `cat`, `head`, `tail`) and requests approval for copy, move, delete and general shell, Node or Python execution. Guards cover redirection, substitutions, tree output files and ripgrep preprocessors.

VS Code defaults and organization policies still apply. The preset is not a security sandbox and does not change MCP, file-edit or GitHub permissions. Review effective workspace settings and keep manual permissions rather than Allow All or Autopilot. See [VS Code terminal approvals](https://code.visualstudio.com/docs/agents/run/approvals#automatically-approve-terminal-commands).

## AWS documentation

Use AWS Knowledge MCP Server when a material AWS question remains unresolved by the repository and SEND references. Add this entry to the VS Code MCP configuration, preserving existing servers:

```json
{
  "servers": {
    "aws-knowledge-mcp-server": {
      "type": "http",
      "url": "https://knowledge-mcp.global.api.aws"
    }
  }
}
```

Enable the server and its tools in Copilot. An existing AWS Knowledge configuration can be reused regardless of its alias. The service requires no AWS credentials and cannot access your AWS resources. The installer does not configure MCP servers. See [AWS Knowledge MCP Server](https://awslabs.github.io/mcp/servers/aws-knowledge-mcp-server).

## Toolkit layout

```text
pn-infra/
├── .github/
│   ├── agents/pn-infra.agent.md
│   ├── instructions/pn-infra-ai-toolkit.instructions.md
│   ├── prompts/pn-infra-agent-plan.prompt.md
│   ├── prompts/pn-infra-agent-implement.prompt.md
│   └── skills/pn-infra/
│       ├── SKILL.md
│       ├── SPEC.md
│       ├── workflows/
│       ├── reasoning/
│       ├── references/
│       ├── templates/
│       └── evals/
│           └── fixtures/
└── ai-toolkit/
    ├── README.md
    ├── SOURCES.md
    ├── VERSION
    ├── scripts/install-copilot-agent.sh
    ├── tests/test_install_copilot_agent.py
    └── copilot/terminal-approvals.settings.json
```

See the [evaluation guide](../.github/skills/pn-infra/evals/README.md) for running the cases. Eval expectations are assessment material, not ordinary runtime instructions.

## Installer tests

From the repository root, run the standard-library Python tests:

```sh
python3 -B ai-toolkit/tests/test_install_copilot_agent.py
```

They run the installer against disposable fixture directories, not your workspace. They verify the installed files, unrelated prompts, idempotency, backups and invalid-input refusal. Copilot discovery and approval behavior must still be checked in a new client session; installer tests do not establish model behavior.

## Documentation

- [GitHub CLI skill installation](https://cli.github.com/manual/gh_skill_install)
- [Copilot customization locations](https://docs.github.com/en/copilot/reference/customization-cheat-sheet)
- [Copilot Code Review](https://docs.github.com/en/copilot/concepts/agents/code-review)
