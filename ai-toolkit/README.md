# pn-infra-ai-toolkit

Shared SEND infrastructure guidance for AI-assisted analysis, development and review. The toolkit combines a Copilot skill, a selectable custom agent and repository instructions. The skill contains the workflows and references for SEND architecture, CloudFormation, Terraform and CI/CD; the agent provides an explicit entry point for interactive work.

## Use in `pn-infra`

Open the repository in a supported Copilot client. Select **pn-infra-agent** from the custom-agent menu for an infrastructure task, or use the default agent and ask it to use the `pn-infra` skill. The skill routes the request to its development or review workflow and loads the relevant SEND references.

For a local review, provide the workspace change or diff. For a PR review, provide its GitHub URL; the skill can read the PR without a local checkout using an available read-only tool, including GitHub CLI. The two review procedures share SEND finding criteria. Copilot Code Review uses repository skills and instructions from the pull request's head branch; it does not select the interactive custom agent.

## Install the skill in another repository

Use a GitHub CLI version that provides `gh skill install`, or Node.js with npm for the `npx` alternative. From the root of the target repository, choose one installer:

```sh
gh skill install pagopa/pn-infra .github/skills/pn-infra --allow-hidden-dirs --agent github-copilot --scope project
```

```sh
npx skills add pagopa/pn-infra --skill pn-infra --agent github-copilot --copy
```

Both install the skill at project scope under `.agents/skills/pn-infra/`. The `npx` command uses the [`skills` CLI](https://github.com/vercel-labs/skills); this toolkit does not need a separate npm package. Choose one installer, not both.

The GH/npx commands above install the skill only. As an alternative, install the complete toolkit from the root of a local pn-infra checkout with one command (do not combine the two installation methods):

```sh
bash ai-toolkit/scripts/install-copilot-agent.sh /path/to/workspace
```

The script installs or updates `.github/skills/pn-infra/` (including evals and fixtures), `.github/agents/pn-infra.agent.md` and `.github/instructions/pn-infra-ai-toolkit.instructions.md`. It uses Bash and standard utilities on macOS/Linux, without Python, Node or network access. Unchanged components are skipped. Replaced components are preserved under `.pn-infra-toolkit-backups/install-XXXXXXXX/previous/` with their original relative paths; keep this recovery directory local, outside commits. Other skills and settings are untouched. Alternative installations under `.agents/skills/` and legacy toolkit names must be archived explicitly first to avoid duplicate discovery. After installation, start a new Copilot chat and select **pn-infra-agent**.

### Optional terminal approvals

To offer an explicit confirmation before configuring workspace terminal approvals:

```sh
bash ai-toolkit/scripts/install-copilot-agent.sh /path/to/workspace --configure-approvals
```

The default installation does not change permissions. This option asks before copying `ai-toolkit/copilot/terminal-approvals.settings.json` into a new `.vscode/settings.json`. It uses Bash and standard macOS/Linux utilities, with no Node or Python dependency. Existing settings are never overwritten: if present and different, the script leaves them intact and asks you to review and merge the preset manually in VS Code. No backup is needed because no existing settings file is replaced.

The preset allows common read commands (`pwd`, `ls`, `tree`, `grep`, `rg`, `cat`, `head`, `tail`) and requires confirmation for copy/move/delete commands and general shell, Node or Python execution. It adds conservative guards for redirection, substitutions, tree output files and ripgrep preprocessors. It retains VS Code's default rules and is not an exclusive allowlist or security sandbox; existing user/remote approvals, shell aliases and organization policies can affect behavior. Review effective settings, especially in multi-root workspaces, and keep normal/manual permissions rather than Allow All or Autopilot. This applies to the workspace, not only the pn-infra-agent persona, and does not change MCP, file-edit or GitHub permissions.

Reference: [VS Code terminal approvals](https://code.visualstudio.com/docs/agents/run/approvals#automatically-approve-terminal-commands).

The local script includes the path-specific instructions. GH/npx alone does not install the persona or those instructions.

## AWS documentation

The skill uses AWS Knowledge MCP Server when an AWS question needs documentation beyond the local sources. In VS Code, add the following server entry to your MCP configuration, preserving existing entries:

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

The server requires no AWS credentials and cannot access your AWS resources. Its name in the client is an alias; an existing configuration such as `awsknowledge` can be reused. Enable the server and its tools in Copilot. The persona uses the host's available tools without an alias-specific filter; the skill's rules govern their use. The installation script does not configure MCP servers. See [AWS Knowledge MCP Server](https://awslabs.github.io/mcp/servers/aws-knowledge-mcp-server) for the service documentation.

## Toolkit layout

Paths below are relative to the repository root.

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

The skill is maintained once under `.github/skills/pn-infra/`; the installer reads those repository files rather than maintaining a second copy. `ai-toolkit/` contains the user guide, provenance, version and installation support. No installation is needed to copy these files into this same checkout.

Evaluation fixtures are compact Markdown snapshots with explicit virtual file paths. See [evaluation guidance](../.github/skills/pn-infra/evals/README.md). Evaluation expectations are not ordinary runtime instructions and should be withheld from the agent during a benchmark.

Interactive external PR reviews require a user-approved folder under `agents-memories/` before acquiring metadata or a diff. Source code and GitHub remain unchanged. Development notes, task memories and installer backups are local artifacts, not toolkit content to commit.

Maintain SEND rules in the skill references and update installed copies from this source. See [SPEC.md](../.github/skills/pn-infra/SPEC.md) for the skill contract and [SOURCES.md](SOURCES.md) for provenance.

Installation and Copilot references: [GitHub CLI `gh skill install`](https://cli.github.com/manual/gh_skill_install), [Copilot customization locations](https://docs.github.com/en/copilot/reference/customization-cheat-sheet) and [Copilot Code Review](https://docs.github.com/en/copilot/concepts/agents/code-review).
