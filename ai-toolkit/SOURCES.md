# Sources

## SEND domain references

| Reference | Scope |
| --- | --- |
| Infra — AI-Enabled IaC Development Guidelines | Engineering principles and CloudFormation, Terraform and CI/CD conventions. |
| Pattern architetturali e Infrastructure as Code di SEND | Architecture, repository responsibilities and deployment contracts. |
| SEND repository sources | Resource wiring, fragment callers, parameter transformations and deployment behavior. |

The toolkit combines these references with project-specific operating policies. Repository evidence establishes the current implementation; historical examples are not proof that every component follows a convention.

## Skill and workflow design

| Source | Contribution |
| --- | --- |
| Anthropic Skill Creator | Progressive disclosure and comparative evaluation with feedback. |
| [Sentry Skill Writer](https://github.com/getsentry/skills/tree/main/skills/skill-writer) | Separation of procedures, domain references and evaluation resources. |
| Angie Jones, Block, “3 Design Principles for Creating Agent Skills” | Separation of deterministic checks from contextual reasoning. |
| [GitHub Spec Kit](https://github.com/github/spec-kit) | Explicit acceptance criteria and continuity between task artifacts. |
| [AWS AI-DLC](https://github.com/awslabs/aidlc-workflows) | Separation of domain knowledge, workflow state and confirmed learning. |

The workflow and task-memory layout are toolkit-specific adaptations, not an AWS or GitHub specification. These sources are design references, not runtime dependencies.

## Platform documentation

- [GitHub Copilot agent skills](https://docs.github.com/en/copilot/how-tos/copilot-on-github/customize-copilot/customize-cloud-agent/add-skills)
- [GitHub Copilot custom agent configuration](https://docs.github.com/en/copilot/reference/custom-agents-configuration)
- [GitHub Copilot code review](https://docs.github.com/en/copilot/concepts/agents/code-review)
- [GitHub CLI PR metadata](https://cli.github.com/manual/gh_pr_view) and [PR diff](https://cli.github.com/manual/gh_pr_diff)
- [AWS Knowledge MCP Server](https://awslabs.github.io/mcp/servers/aws-knowledge-mcp-server)

## AWS technical references

- [CloudFormation Rules](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/rules-section-structure.html) and [parameters](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/parameters-section-structure.html)
- [DeletionPolicy](https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-attribute-deletionpolicy.html) and [UpdateReplacePolicy](https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-attribute-updatereplacepolicy.html)
- [Lambda SQS scaling](https://docs.aws.amazon.com/lambda/latest/dg/services-sqs-scaling.html)

Evaluation scenarios are synthetic test inputs, not claims about defects in the referenced repositories.
