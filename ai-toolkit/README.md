# pn-infra-ai-toolkit

SEND infrastructure guidance for AI-assisted development, local review and PR review, with rules for CloudFormation, Terraform and CI/CD.

## Use with Copilot

Open the workspace and select **pn-infra-agent**, or ask the default agent to use the `pn-infra` skill.

- **Development:** provide the task, scope and available context.
- **Local review:** provide the local files or diff to review.
- **PR review:** provide the GitHub pull request URL.

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
- `.github/instructions/pn-infra-ai-toolkit.instructions.md`.

Unchanged components are skipped. Replaced components are backed up under `.pn-infra-toolkit-backups/install-XXXXXXXX/previous/`. Other skills and settings are left unchanged. Keep backups outside commits.

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

Both install the skill under `.agents/skills/pn-infra/`. They do not install the custom agent or repository instructions. The `npx` command uses the [`skills` CLI](https://github.com/vercel-labs/skills).

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
    └── copilot/terminal-approvals.settings.json
```

See the [evaluation guide](../.github/skills/pn-infra/evals/README.md) for running the cases. Eval expectations are assessment material, not ordinary runtime instructions.

## Documentation

- [GitHub CLI skill installation](https://cli.github.com/manual/gh_skill_install)
- [Copilot customization locations](https://docs.github.com/en/copilot/reference/customization-cheat-sheet)
- [Copilot Code Review](https://docs.github.com/en/copilot/concepts/agents/code-review)
