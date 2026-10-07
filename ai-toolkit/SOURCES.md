# Source provenance

## Approved memory design

The four-phase knowledge base and documentation folder with HANDOFF, WORKLOG, DECISIONS and phase artifacts is a local design agreed with the user. It draws on Spec Kit's artifact continuity and AI-DLC's separation of state, evidence and confirmed learning; its filenames and layout are not an upstream AWS or GitHub specification. Shared learning requires explicit approval. Historical task documentation is preserved. Behavioral validation remains pending.

Imported on 2026-09-19 from the existing local topic `agents-memories/send-expert-infra-atlas-skills-evolution`:

| Toolkit file | Existing source |
| --- | --- |
| `.github/skills/pn-infra/references/iac-guidelines.md` | `confluence-infra-ai-enabled-iac-development-guidelines.md` |
| `.github/skills/pn-infra/references/architecture.md` | `confluence-pattern-architetturali-e-infrastructure-as-code-di-send.md` |

Both files were initially copied verbatim. The guidelines were subsequently extended locally as recorded below. This records local provenance, not a fresh comparison with Confluence or validation against all SEND repositories.

Naming/comment guidance, fragment reuse and propagated log retention have been restored from explicit user decisions and local evidence. The local reconciliation was subsequently extended with lifecycle and S3 rules, IAM source constraints, ARN construction, CloudFormation dependencies, Lambda alarm usage, schedule configuration and CI/CD contracts. These rules combine explicit user decisions with recurring patterns verified in the local SEND repositories; they are not claims that every historical template already conforms. Development reconciliation notes are maintained outside this distributable repository. The guidelines' Confluence smartlink was replaced with a local architecture reference.

The new entry point and procedures are an initial implementation of the agreed development/review split and durable task memory. They have not yet undergone behavioral evaluation. No external skill implementation has been copied into this project.

The AI-DLC comparison used the team-knowledge convention examined in the local 2.9.0 laboratory. This historical experiment is separate from the toolkit's installation.

## Mechanisms adopted — 2026-09-19

| Source | Contribution and boundary |
| --- | --- |
| Local Anthropic `skill-creator` | Progressive disclosure and comparative evaluation with feedback. Pilot cases are prepared; behavioral results are not yet available. |
| [Sentry Skill Writer](https://github.com/getsentry/skills/tree/main/skills/skill-writer) | Separation of runtime procedure, domain knowledge, source provenance and maintenance/evaluation. Read upstream instructions and selected references; no upstream code was copied. The user's workflow/reasoning folders take precedence over Sentry's flat-reference preference. |
| Angie Jones, Block, “3 Design Principles for Creating Agent Skills”, user-provided article | Preserve deterministic check results; reserve contextual interpretation and design for the agent. This is not a claim that prompt rules enforce permissions. |
| [GitHub Spec Kit](https://github.com/github/spec-kit), local checkout d4229c071c7ea3885b43e8a7739847300f618f13 | Expected behavior and acceptance before implementation, shared task artifacts proportional to scope. No lifecycle or adapter is installed by this change. |
| [AWS AI-DLC](https://github.com/awslabs/aidlc-workflows), local checkout 63b65ded10111a7e672a70305471135d888ba986 | Separate domain knowledge from workflow state; reuse the controlling framework's plan and decision record. Full lifecycle intentionally omitted. |
| [GitHub Copilot agent skills](https://docs.github.com/en/copilot/how-tos/copilot-on-github/customize-copilot/customize-cloud-agent/add-skills) and [custom agent configuration](https://docs.github.com/en/copilot/reference/custom-agents-configuration) | Repository packaging under `.github/skills`, a thin custom-agent profile, and manual agent selection for reproducible interactive runs. |
| [GitHub Copilot code review customization](https://docs.github.com/en/copilot/concepts/agents/code-review) | A short path-specific instruction points IaC work to the skill; code review consumes repository instructions and relevant skills from the PR head branch. |
| [GitHub CLI PR view](https://cli.github.com/manual/gh_pr_view) and [PR diff](https://cli.github.com/manual/gh_pr_diff) | The PR review workflow retrieves intent and file metadata with `gh pr view --json`, then a complete patch with `gh pr diff --patch`. Additional reads are scoped to material gaps. |
| User-approved Ponytail and Grill Me mechanisms | Minimum adequate solution and a targeted interview, one question at a time with recommendation and consequences. Implemented from the user's specification; upstream provenance and fidelity remain unverified. |

Selected shape: reference-backed expert with development/review routing, not a multi-agent orchestrator. Retrieval stopped after these mechanisms were sufficiently specified; further framework breadth would not improve this local implementation step.

Coverage: routing, permissions, interview, task resumption and result reporting are implemented; source corpus reconciliation, independent behavior evaluation and Copilot invocation remain open. Procedures are original local adaptations. The new folders separate operational needs without duplicating the SEND rules or persona.

## Guidelines extension — 2026-09-20

On 2026-09-23, added three user-requested design/validation rules and eval cases: direct Lambda-to-Lambda invocation is challenged by default rather than treated as an AWS prohibition; SQS mapping `ScalingConfig.MaximumConcurrency` is compared with function reserved concurrency; and CloudFormation `Rules` are used for meaningful parameter relationships, not for missing required parameters already rejected by CloudFormation. The local positive Rule example is `pn-infra/runtime-infra/fragments/api-gw-expose-service-openapi.yaml` (`ServiceApiPathOverrideMutualExclusion`), used by `pn-delivery/scripts/aws/cfn/microservice.yml` for informal APIs. The parent informal path parameter has no default, but values were found in the checked `pn-configuration` environments; the eval does not assert a current deployment failure. SQS concurrency examples were checked in `pn-infra/runtime-infra/pn-warning-notifications.yaml` and `pn-infra/runtime-infra/pn-infra-sec-monitoring.yaml`. AWS semantics were verified against [CloudFormation Rules](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/rules-section-structure.html), [CloudFormation parameters](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/parameters-section-structure.html), and [Lambda SQS scaling](https://docs.aws.amazon.com/lambda/latest/dg/services-sqs-scaling.html). The synthetic eval scenarios are not claims about current defects in these repositories.

Added the user-approved general design and development principles before the technology-specific rules. Source: decisions in this conversation, not newly verified upstream Ponytail or Grill Me instructions. The section covers context, necessity/reuse, KISS, DRY, YAGNI, production behavior, configurable values, feature flags, compatibility, observability/testing and authorization boundaries. It deliberately contains no tool phases, planning artifacts or interview sequencing. Existing CloudFormation parameter guidance remains the implementation-specific rule. No Confluence or historical snapshot was updated.

On 2026-09-22, a further user-proposed building-block principle was added to the local skill guidelines. It asks for a deliberate comparison between a feature-specific component and a reusable one when a substantial new capability has a concrete shared use. The rule is a design decision aid, not a claim that every SEND CodeBuild project or Lambda is already reusable. The Confluence source and historical snapshots were not changed.

Added repository-backed operational rules for persistent CloudFormation resources, S3 buckets, IAM source constraints, ARN and account derivation, dependency ordering, Lambda alarms, EventBridge schedules and CI/CD ownership and contracts. The retention rule reflects the dominant SEND pattern while allowing the policies to be omitted for disposable resources observed in monitoring and cost-saving templates; it does not prescribe an explicit `Delete`. Semantics were checked against the AWS CloudFormation references for [`DeletionPolicy`](https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-attribute-deletionpolicy.html) and [`UpdateReplacePolicy`](https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-attribute-updatereplacepolicy.html). No SEND repository or Confluence page was modified.

## Distribution decision — 2026-09-20

GitHub Copilot plugins are retained as the future centralized, versioned distribution mechanism for interactive CLI, cloud-agent and app use. The current GitHub documentation does not list plugins as a Copilot Code Review input: repository `enabledPlugins` is documented for CLI and cloud agent, whereas Code Review consumes repository instructions, skills and configured MCP servers from the PR head branch. The toolkit therefore preserves a single canonical source but plans versioned synchronization pull requests for Code Review repositories. Sources: [About GitHub Copilot plugins](https://docs.github.com/en/copilot/concepts/agents/about-plugins), [Copilot CLI configuration](https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-config-dir-reference), and [About Copilot Code Review](https://docs.github.com/en/copilot/concepts/agents/code-review).

## AWS external knowledge routing — 2026-09-23

The initial policy preferred AWS MCP Server. This preference was superseded by the explicit user decision on 2026-09-24 to use AWS Knowledge MCP Server for unresolved documentation questions.

## Consistency corrections — 2026-09-24

User decisions: one CloudFormation CLI lint attempt per task without automatic retries; before implementation, run only checks necessary to decide or safely make the change; preserve shared-fragment parameter compatibility, allowing stricter constraints only as an explicitly authorized last resort with a caller migration.

AWS Knowledge is identified by service provenance and capabilities rather than a local alias. Its public endpoint and lack of authentication are documented by [AWS](https://awslabs.github.io/mcp/servers/aws-knowledge-mcp-server). The Copilot persona omits an alias-specific tool allowlist, using the host's available tools as documented in [custom agent configuration](https://docs.github.com/en/copilot/reference/custom-agents-configuration). This changes tool visibility, not the skill's authorization contract. MCP installation and configuration remain explicit user choices.
