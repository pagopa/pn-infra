# Infra — AI-Enabled IaC Development Guidelines

## Context and objectives

This page collects the Infrastructure as Code development rules and best practices consolidated by the SEND Infra team. Formalizing them makes conventions shareable that would otherwise need to be reconstructed from source code or passed between team members. It provides a common basis for infrastructure development and review, and for building AI-assisted agentic development tools such as skills and agents.

The architectural context and infrastructure organization are described in the local reference [SEND architectural patterns](architecture.md).

## General design and development principles

These principles apply to infrastructure changes regardless of the IaC language or tool. They complement the technical rules in the following sections; they do not define the phases of a specific agent workflow.

### Understand the context before implementation

**When it applies:** introducing a feature or changing existing behavior.

* Reconstruct the objective, current behavior, expected outcome, and affected components by consulting available documentation, source code, and decisions. Distinguish verified facts from assumptions.
* Clarify with the user any uncertainty that changes scope, security, behavior, or operations. Do not ask for information that can be derived from available sources, and do not infer business decisions from code alone.
* Determine whether the change is a business capability or a technical capability for platform support, observability, or operations. This distinction informs ownership, error handling, and monitoring, but does not determine criticality by itself.
* Do not implement the part of a solution that depends on an unresolved material decision. Source inspection and analysis needed to resolve it may continue.

**Checks:** the objective and expected outcome are explicit; material decisions are resolved, and any remaining assumptions are clearly identifiable.

### Verify necessity and reuse

**When it applies:** proposing new resources, integrations, modules, or configuration mechanisms.

* Tie every introduced element to a concrete need. If part of the request appears redundant or does not contribute to the objective, discuss its value without removing it unilaterally.
* Before adding a new implementation, verify whether configuration or reuse of existing resources, fragments, and modules can satisfy the requirement.
* Assess the reused component against responsibilities, permissions, limits, and dependencies. A similar name or structure alone does not prove suitability.

**Checks:** new resources have an identifiable purpose; relevant reuse options were examined, and alternatives are justified.

### Simplicity and minimum change — KISS

**When it applies:** choosing among solutions or defining the scope of a change.

* Prefer the simplest solution that meets requirements for security, reliability, and operability, limiting unnecessary dependencies, abstraction layers, and configuration steps.
* Make the smallest coherent change: include updates required for callers, permissions, and contracts without extending the work to unrelated refactoring.
* Do not measure simplicity only by changed lines or files. Omitting necessary alarms, error handling, or compatibility reduces the diff, not operational complexity.

**Checks:** every part of the change supports the objective or its safe integration; reducing scope does not leave incomplete dependencies.

### Avoid duplication without forcing abstractions — DRY

**When it applies:** introducing configuration or definitions similar to existing ones.

* Reuse shared value sources and established components instead of creating separately maintained copies. For parameters already propagated by CI/CD, follow the existing channel.
* Extract a common component when cases share responsibility and behavior, not merely a block of syntax.
* Do not combine cases with different evolution, security, or lifecycle needs into one module full of exceptions. Before changing a shared component, consider every affected caller.

**Checks:** no competing source is introduced for the same value; reuse does not create unjustified coupling between independent capabilities.

### Evaluate components as building blocks

**When it applies:** designing a new infrastructure implementation with a meaningful, independent responsibility, such as a CodeBuild project, a support Lambda, or a reusable fragment.

* Before tying the component to one feature, separate the stable capability from caller-specific details: inputs, outputs, configuration, permissions, and activation.
* When multiple components have the same concrete need, consider a building block with a small, clear interface that does not depend on feature-specific names or flows.
* Compare reuse with a dedicated solution. A shared component must not unnecessarily broaden permissions or couple release cycles, error handling, or operational ownership.
* Do not introduce speculative parameters, modes, or abstractions for hypothetical users. If reuse is not yet justified, keep the component specific and its responsibility narrow enough to extract later when a real use case emerges.

**Checks:** the choice between a dedicated and shared component is justified; when reused, its interface, security boundaries, and ownership remain clear to all callers.

### Avoid speculative functionality — YAGNI

**When it applies:** proposing extensions beyond the requested behavior.

* Do not introduce modes, resources, parameters, or generalizations solely because they may be useful later. Tie them to a current requirement or an explicitly agreed future need.
* Distinguish speculative extensions from necessary operational requirements: security, failure handling, monitoring, and recovery are not optional merely because the first use is in development.
* Report possible evolutions without implementing them implicitly in the current task.

**Checks:** the scope contains no capability without an identified need; all requirements needed to use and operate the feature remain covered.

### Design for production use

**When it applies:** introducing or changing capabilities intended for SEND environments.

* From the initial development implementation, consider expected production behavior: volume, concurrency, availability, data, access, dependencies, and failure consequences.
* Consider recurring cost, service limits, and recovery after errors or interruptions. State material assumptions that cannot be verified in development.
* Separate solution characteristics from environment sizing. Designing for production does not mean reproducing production capacity and cost in development.
* Do not automatically extend a release to every environment. Intended behavior and authorized deployment scope remain separate decisions.

**Checks:** the solution does not rely on conditions that are true only in development; sizing differences and verification limits are explicit.

### Configurability of values

**When it applies:** introducing or changing values that may vary by environment or operational need.

* Identify values that should change without a code-version change, such as alarm thresholds and windows, execution frequency, timeouts, and processing limits. Expose them through the component's established configuration mechanisms.
* First verify whether the value is already available as a parameter, output, or propagated configuration. Do not create a second source for the same data or ask the user to enumerate parameters that technical analysis can identify.
* Carry configuration through to the consuming resource; do not hardcode values in intermediate fragment or module invocations. The CloudFormation and Terraform sections define the respective mechanisms.
* Keep values without a concrete configuration need invariant in code. For exposed values, make meaning, unit, and default behavior clear.
* Distinguish avoiding a new code version from avoiding deployment operations. A configuration change may still require a pipeline run, stack update, or component restart. Respect Terraform variable ownership and the authorization required to change `pn-configuration`.

**Checks:** operationally useful values can be changed through the intended channel, reach the resource, and have a known application mechanism; no parameter is introduced without a concrete purpose.

### Feature flags and operating modes

**When it applies:** introducing a capability or changing how an existing capability is activated or controlled; assess the need for configuration rather than assuming a flag has already been chosen.

* Assess whether the capability must be enabled, disabled, or switched between operating modes without changing the code version. Do not add a flag for every resource without a control requirement.
* Define default behavior, state meaning, and transition consequences. When independent behaviors require separate controls, make allowed combinations and dependencies explicit.
* Distinguish disabling processing from not creating or removing resources. Consider retained data, queued messages, in-flight operations, and reactivation behavior.
* Use established configuration mechanisms, including `pn-configuration` where applicable, without conflating them with Terraform variable management. Clarify whether the change requires an infrastructure update or is consumed at runtime.
* Do not treat a flag as an automatic substitute for rollback: disabling behavior does not necessarily reverse written data or completed effects.

**Checks:** states and transitions have defined behavior; disabling and re-enabling do not leave inconsistent dependencies or unexamined data effects.

### Compatibility and reversibility

**When it applies:** changing existing resources, shared contracts, or processing flows.

* Identify affected consumers and dependencies, including those in other repositories or domains. Consider compatibility during rollout, not only after completion.
* Derive deployment order from the actual pipelines and scripts across affected components and CORE/CONFINFO accounts; do not assume a fixed account order. Assess old/new version coexistence, interruption, degradation, unavailable integrations and queued or in-flight work at the start of Planning. If the sequence requires disruption, explain feasible alternatives and obtain confirmation of the proposed trade-off before finalizing the dependent plan or implementing it. Do not require an outage-duration estimate or treat design confirmation as deploy authorization.
* Determine whether the change updates, replaces, or removes resources and what it does to data. Do not assume restoring the previous template also restores application state.
* Define how to stop or restore behavior and flag non-reversible operations. Resolve decisions involving data loss, replay, or interruption before implementation.

**Checks:** dependencies and update order are compatible; rollback options and their limits are known.

### Monitoring and verifiability

**When it applies:** introducing a capability or changing its behavior or dependencies.

* Define signals that distinguish correct operation, degradation, and failure. Check existing coverage before adding duplicate logs, metrics, or alarms.
* Tie notifications to operational ownership and an expected action, applying SEND topic and routing rules. The distinction between business and technical support does not replace this assessment.
* Propose checks with a scenario, expected result, and observable evidence, including relevant errors, regressions, and flag transitions. Do not delegate technical test design to the user; ask only for unavailable business outcomes, constraints, or authorization.
* Distinguish what static checks, tests, and environment trials prove. Report checks not run and do not present syntax validity as proof of production behavior.

**Checks:** proposed checks map to expected results; actual results and limitations are distinct; monitoring can detect relevant failures.

### Respect scope and authorization

**When it applies:** every infrastructure change or activity performed with AI-assisted tools.

* Limit changes to the agreed objective and preserve unrelated pre-existing work. Report dependencies that require expanding scope before changing them.
* Do not treat an analysis or review request as authorization to edit code. Do not infer permission to commit, push, deploy, run AWS operations, or modify `pn-configuration` from authorization to edit local files.
* Clarify material decisions not determined by available sources and do not interpret silence as approval.

**Checks:** performed actions match the request and received authorization; any scope expansion or external operation was agreed explicitly.

## Cross-cutting architectural decisions

### Domain boundaries

**When it applies:** introducing a resource or changing an integration between SEND domains.

* Place resources in the account responsible for the service and processed data. For CORE–CONFINFO integrations, keep the channel, recipients, and permissions explicit; general connectivity between accounts requires a dedicated architectural decision.

**Checks:** account placement, communication channel, recipients, and permissions match service and data ownership; any general cross-account connectivity is an explicit architectural decision.

### Event routing

**When it applies:** adding or changing a flow routed through the Core Event Bus.

* In Core Event Bus flows, keep event publication separate from destination selection. For every change, verify the producer, event contract, filters, targets, delivered payload, and permissions.
* Distinguish target-delivery errors from consumer errors. An EventBridge DLQ does not replace the processing queue's DLQ and does not collect events that match no rule.

**Checks:** the producer contract matches target filters and expected payload; permissions allow delivery, and error handling separates routing from processing.

### Queues and consumer responsibility

**When it applies:** creating SQS queues or changing the producers, consumers, or failure handling of a flow.

* Organize SQS queues by consumer responsibility and processing characteristics; do not force a one-to-one mapping with microservices. When independent consumers must receive the same event, use separate queues and configure the corresponding fan-out.
* Size retries and timeouts for the consumer and keep delivery failures, processing failures, and their DLQs distinguishable.

**Checks:** each independent consumer receives its intended events; timeouts, retries, and DLQs match processing behavior.

## CloudFormation

### Targeted validation of changes

**When it applies:** changing a CloudFormation template or fragment.

* In Verification, inspect the diff, the required behavior, and any editor diagnostics for the changed file. If the editor already exposes `cfn-lint` results, do not repeat the same lint through the CLI. Attribute findings to the task only when they concern changed lines or directly affected dependencies; report unrelated historical findings without fixing or suppressing them.
* If those diagnostics are unavailable and lint is needed for the change, run `cfn-lint` only with an invocation already established by the repository. Make at most one CLI attempt per task, scoped to the changed files. If it cannot run, report linting as not performed; do not troubleshoot the invocation through retries, try alternative parsers, change lint configuration, or add exclusions to obtain a passing result. After correcting a relevant finding, do not rerun lint automatically; state that the correction has not been linted again.
* Do not install a missing tool or automatically substitute SAM, Ruby, or another parser. If a broader lint check is already part of CI, identify it as pending until its actual result is available; do not assume CI exists or report it as passed.
* Passing lint establishes static template checks, not deployment behavior. A lint result cannot replace verification of the requested behavior.

**Checks:** editor diagnostics are not duplicated with CLI lint; at most one established CLI invocation is attempted when needed. Results distinguish relevant findings from pre-existing ones, and missing or unusable validation is reported as a limitation without fallback attempts.

### Names, comments, and descriptions

**When it applies:** introducing or changing parameters, resources, comments, and descriptions in templates.

* Use descriptive names and concise English descriptions. Make meaning and unit explicit, for example `TimeoutSeconds`, `MaxSizeBytes`, and `RetentionDays`.
* Describe what the value represents and, where useful, behavior when empty or disabled. Example: `Maximum payload size in bytes`.
* Write technical, non-conversational comments. Avoid references to the user or chat and avoid justifying the agent's work. Keep only explanations useful for understanding non-obvious constraints or behavior.

**Checks:** names and descriptions are understandable, in English, and include explicit units; comments remain useful without knowledge of the conversation.

### Parameters and fragments

#### Reuse established fragments

**When it applies:** creating a resource covered by shared fragments under `pn-infra/runtime-infra/fragments/`.

* Use established fragments by default when they cover the use case. This is the preferred practice; justify alternatives against requirements not covered by the fragment.
* Treat `pn-infra/runtime-infra/fragments/` as the catalog of shared fragments already used in SEND. The table below highlights common cases and does not replace a targeted search of the directory when a use case is not listed.
* Inspect the relevant fragment and necessary callers without reading the entire directory. Verify parameters, conditions, and outputs before reuse.

| Resource or capability | Fragment | Content to verify |
| --- | --- | --- |
| Log group | `log-group.yaml` | Retention, encryption, and the optional Kinesis subscription filter |
| SQS queue | `sqs-queue.yaml` | DLQ, redrive, retention, and configurable alarms |
| Lambda alarms | `lambda-alarms.yaml` | Function alarms; distinct from `lambda.yaml` |

**Checks:** the selected fragment covers the required behavior; conditional capabilities are not assumed to be active.

#### Parameter provenance and propagation

**When it applies:** adding, changing, or diagnosing a CloudFormation parameter used by SEND stacks or nested fragments.

* Do not assume parameters are inherited automatically between stacks. The path is explicit and may combine Terraform outputs, Infra stack outputs, component storage outputs, `*-cfg.json` files, and values constructed by the pipeline.
* Before adding a value to a cfg file, verify whether it is already available through the deployment path. CORE stacks normally receive aggregated outputs from `pn-infra-storage`, `pn-cache`, `pn-infra`, and `pn-ipc`; CONFINFO stacks receive aggregated outputs from `infra-storage` and `infra`.
* In the recurring ECS path, deploy `storage.yml` first and use its outputs as inputs to `microservice.yml`; then deploy `data-quality.yml` when present and supported by that path. Templates explicitly pass only required parameters to nested fragments.
* Keep the output name identical to the consumer parameter when the pipeline associates them by key. Use a different name only when an explicit remapping exists in the stack or script. For the `deployNetworking.sh` prefix-removal path, follow the scoped example in [architecture.md, section 2.2](architecture.md#22-cloudformation-parameter-provenance-and-propagation); trace the transformed key and actual value type, not just the original output name.
* Identify the effective path with targeted searches in `pn-cicd/cd-cli/cnf-templates/complete-pipeline.yaml`, `pn-cicd/cd-cli/cnf-templates/confinfo-complete-pipeline.yaml`, and the invoked deployment script. Search for the component or repository first, then follow the parameter name through scripts and `merge-infra-outputs-*` helpers; do not read entire pipeline files unnecessarily.
* Do not assume universal precedence between cfg values and outputs: merge order differs between CORE and CONFINFO paths. Verify it in the script used by the component before introducing an existing key.

**Checks:** the exact value name is traced from source to the property that uses it; all affected deployment paths are covered, and no competing source was introduced.

#### Configurable parameters

**When it applies:** introducing or changing values used by a CloudFormation template or fragment.

* Expose values that must vary by environment or operational need as parameters; do not hardcode them in resource properties or fragment invocations.
* Apply the general “Configurability of values” principle to decide what to expose; this rule describes propagation through CloudFormation templates.
* When a fragment uses the value, declare the parameter in the fragment and its calling stack (`microservice.yml`, `storage.yml`, or another template) if not already present, then pass it with `!Ref` in the nested stack's `Parameters`.
* Keep invariant values constant in the template; use defaults for intentional behavior that remains compatible with existing callers.

**Checks:** every configurable value reaches the consuming resource through any nested stack without being replaced by a hardcoded value.

#### Parameter compatibility in shared fragments

**When it applies:** adding or changing a parameter in a fragment already in use.

* Identify all calling stacks and determine which ones must use the new capability.
* Preserve the values and combinations accepted by existing parameters in fragments already in use. Avoid adding or tightening `AllowedValues`, patterns, bounds or `Rules` that reject previously valid caller inputs. First consider validation in the affected caller or a separate optional capability. Only when no adequate compatible alternative exists and the user explicitly authorizes the exception may the shared constraint change; document affected callers, accepted-value changes and the coordinated migration before editing.
* For a new optional parameter, choose a default valid for its type that preserves the previous behavior when omitted. Use `Default: ''` only for string parameters whose empty value is supported and explicitly handled.
* Handle any sentinel value explicitly in consuming resources and references; do not assume that an empty string or zero is neutral.
* Pass the optional parameter from stacks that enable the capability. Other callers must continue using the fragment unchanged.
* When a change serves only one new or existing caller, modify that caller and the fragment, not every other caller. Fragment compatibility must preserve their deployment and previous behavior.
* Do not use an empty default for a required parameter; define how all affected callers will be updated.

**Checks:** test both omitted and populated values; existing callers retain their intended behavior.

#### CloudFormation Rules for parameter relationships

**When it applies:** parameter combinations can be invalid even though each supplied value satisfies its own constraints.

* First use required parameters, defaults, `AllowedValues`, and other parameter constraints for individual values. A parameter without `Default` is already required at stack creation; a resource `Condition` does not make it optional.
* Use a `Rules` assertion when a relationship must be checked before resource creation or update, such as two optional API path overrides that cannot both be set. Use `RuleCondition` when the assertion applies only in a particular parameter state, such as an enabled capability that requires a nonempty value.
* Do not add a Rule that only restates a missing required parameter or another failure already guaranteed by CloudFormation. Keep validation in the template that owns the parameter relationship, with a short English `AssertDescription`.
* In shared fragments already in use, apply “Parameter compatibility in shared fragments” to `Rules` as well: preserve previously accepted inputs and combinations. A stricter shared Rule is a last resort when no adequate compatible alternative exists and the user explicitly authorizes the exception and its caller migration.

**Checks:** valid and invalid parameter combinations produce the intended outcome; the Rule adds a real check rather than duplicating built-in validation.

#### Output compatibility across stacks and pipelines

**When it applies:** adding, changing, or removing a Terraform, CloudFormation, or nested-stack output consumed by other stacks or CI/CD.

* Identify scripts and templates that consume the output, tracing its name through conversions, merges, and parameter passing.
* Preserve name and format compatibility for existing consumers. If either must change, include every affected step and define a compatible release order.
* Before renaming a consumed output, consider retaining the current name, adding a parallel output, or coordinating migration of all consumers. Report the impact to the user and do not leave consumers connected to the old key.
* For new outputs, ensure the key does not unintentionally overwrite an existing pipeline-merge value.

**Checks:** every downstream parameter still receives the intended value in each affected deployment path.

### Lifecycle and persistent resources

#### `DeletionPolicy` and `UpdateReplacePolicy`

**When it applies:** creating or changing a resource that stores data, messages, logs, keys, or other state that must survive CloudFormation removal or replacement.

* Set both `DeletionPolicy: Retain` and `UpdateReplacePolicy: Retain` for persistent SEND resources. The first protects a resource when it is removed from the stack or the stack is deleted; the second preserves the old resource when an update requires replacement.
* Unless there is an explicit exception, apply this to DynamoDB tables, persistent S3 buckets, log groups, queues and DLQs whose contents must be retained, and KMS keys tied to persistent data. For resources created by a nested stack, verify that policies protect the level that actually controls the lifecycle.
* Omit the policies only for intentionally temporary, reconstructible resources with no state to preserve, such as short-lived technical logs or regenerable monitoring components. Do not explicitly set `Delete`, which is already the default. Make the exception's temporary nature recognizable in the template and verify deletion does not disrupt diagnostics or recovery.
* Consider `Snapshot` for supported resource types when a backup should be retained instead of keeping the previous resource operational.
* Remember that retained resources continue to incur cost and are no longer managed by the stack after removal. Fixed physical names may also prevent recreation while a retained resource exists.

**Checks:** both policies are present on persistent resources; every omission is consistent with data, recovery, and operations; replacement and stack removal have the intended outcome.

#### S3 buckets

**When it applies:** creating or changing an S3 bucket managed by SEND templates.

* Use a stable, descriptive name with the `pn-` prefix and derive region and account from CloudFormation pseudo parameters. When rapid recreation with a new globally unique name is required, expose `BucketSuffix` with initial value `001`. Example: `pn-example-name-bucket-${AWS::Region}-${AWS::AccountId}-${BucketSuffix}`.
* For new private buckets, block public access and configure encryption appropriate to the data, reusing the domain KMS key where applicable. Public exposure requires an explicit use case and must not result from merely omitting the block.
* Apply `DeletionPolicy: Retain` and `UpdateReplacePolicy: Retain` to persistent buckets. Use versioning, Object Lock, and lifecycle rules according to retention and recovery requirements; do not enable them indiscriminately.
* For temporary data, exports, or intermediate results, scope lifecycle rules to the relevant prefixes and parameterize expiration when it varies by environment. For versioned buckets, also consider expiration of non-current versions.

**Checks:** naming and suffix support the intended lifecycle; public access, encryption, retention, versioning, and lifecycle match the data; replacement does not cause unintended loss.

### IAM, ARNs, and dependencies

#### Least privilege and source constraints

**When it applies:** creating or changing IAM policies, resource policies, or permissions that allow an AWS service to invoke or write to a resource.

* Grant only the actions and resources required by the flow. Avoid `Resource: '*'` when an ARN, prefix, or finite resource set can be determined; split statements with different scopes instead of broadening them for convenience.
* When supported by the integration, constrain service principals with `aws:SourceAccount` and `aws:SourceArn`, or the equivalent `SourceAccount` and `SourceArn` properties. Apply these controls especially to Lambda permissions and queue, bucket, topic, and EventBridge policies, using the ARN of the resource that actually originates the call.
* For cross-account flows, state the source account, destination account, and permissions on both sides. Do not replace account checks with an overly broad ARN and do not assume a policy only in the consumer account completes the integration.
* Keep wildcards only in the necessary variable part of a name or ARN and verify they do not extend access to unrelated environments, components, or generations.

**Checks:** principal, actions, resources, source account, and source ARN match the real flow; cross-account permissions exist on both sides and include no unrelated scope.

#### ARN derivation and stable physical names

**When it applies:** referring to a resource by ARN or physical name, especially across stacks or accounts.

* Prefer `!Ref` and `!GetAtt` when the resource is available in the template. When an ARN must be constructed, use `AWS::Partition`, `AWS::Region`, and `AWS::AccountId` for the current account; do not hardcode numeric account IDs or `eu-south-1`.
* For cross-account references, use the propagated SEND parameters: `ConfidentialInfoAccountId` from CORE to CONFINFO and `PnCoreAwsAccountId` from CONFINFO to CORE. Derive the region from `AWS::Region`, even though SEND environments currently run in Milan.
* Construct ARNs that remain compatible across environments and intended generations, avoiding ephemeral name components when the contract can rely on a prefix or stable identifier. Before constructing an ARN, verify creation order, name availability, and whether it can be received as an output.
* When a normally generated resource, such as a target group, needs a stable reference and no output or attribute is available, assign an explicit name beginning with `pn-` and including components consistent with environment and purpose. Do not fix physical names without need; they can restrict replacement.

**Checks:** ARNs and names contain no hardcoded account or region; cross-account parameters match the SEND path; references remain valid across affected environments and do not block required replacements.

#### Implicit and explicit dependencies

**When it applies:** introducing or changing resources whose creation, update, or deletion order matters.

* Use dependencies implied by `!Ref`, `!GetAtt`, and resource references in `!Sub` when they already express the real relationship. Do not add redundant `DependsOn` entries.
* Add `DependsOn` when the required order is not represented by a property, for example when a Lambda target group must be created after its invocation permission or an Event Source Mapping after the policy required by its consumer.
* An ARN or name constructed only from strings, pseudo parameters, or external parameters does not necessarily create a dependency on the target resource. In these cases, determine whether an output, direct reference, or explicit dependency is needed.
* Apply compatible conditions to connected resources and ensure dependencies create neither cycles nor references to resources that are not created.

**Checks:** required ordering is expressed once and in the most direct form; creation, update, and deletion do not depend on pipeline timing coincidences.

### Monitoring and alarms

#### Log retention

**When it applies:** creating or changing a log group in SEND deployment paths that propagate `LogRetention`.

* Reuse `LogRetention`, provided through CI/CD from infrastructure outputs, after verifying the applicable propagation path.
* Pass it to `log-group.yaml` as `LogGroupRetention: !Ref LogRetention`.
* Do not duplicate the value in a cfg file when the deployment path already supplies it, and do not replace it with a fixed retention value in the fragment invocation.

**Checks:** the propagated parameter reaches the log group's `RetentionInDays` through `LogGroupRetention`.

#### Alarm configuration and tuning

**When it applies:** creating or changing an alarm whose values may need environment-specific tuning.

* Where possible, expose all useful tuning values as CloudFormation parameters, especially `Threshold`, `Period`, `EvaluationPeriods`, and `DatapointsToAlarm` when applicable.
* When an alarm is defined in a fragment, expose the parameters in the calling stack and pass them to the fragment rather than hardcoding values in its invocation.
* Include units in parameter names or descriptions.
* Before adding an alarm, inspect existing coverage and avoid duplicate alerts for the same condition unless they serve a different operational purpose.

**Checks:** configurable values reach the resource through fragments; units and operational purpose are explicit, and the alarm does not duplicate equivalent coverage.

#### Alarm destination and warning routing

**When it applies:** creating an alarm or changing its notification path.

* Before adding an alarm, select the notification path: `AlarmSNSTopicArn` for the standard flow on `pn-AllAlarmSnsTopic`, or `WarningSNSTopicArn` for dedicated routing on `pn-WarningSnsTopic`. Choose by required destination and operational handling, not perceived severity alone.
* Pass the selected ARN to the template or fragment. In fragments exposing only `AlarmSNSTopicArn`, populate that parameter with the selected ARN. Use the same path for `AlarmActions` and `OKActions` when both are present; do not publish the same alarm to both topics.
* For warning routing, verify that the target environment has an `alarm` route to a Slack channel or `DROP` for intentional suppression. A missing route causes dispatcher errors and message retries; the producer must not know the Slack channel or bot token.
* For CONFINFO producers, verify the CORE topic reference and cross-account publish permissions.

**Checks:** the ARN passed to the template matches the selected path; warning routing exists, and CONFINFO producers have the required cross-account permissions.

### Lambda

#### Lambda alarms

**When it applies:** creating a Lambda or changing its monitoring coverage.

* Unless the case is unsupported, use `pn-infra/runtime-infra/fragments/lambda-alarms.yaml` for function alarms. Pass at least `FunctionName` and the selected topic ARN through `AlarmSNSTopicArn`, exposing any required tuning parameters in the calling stack.
* Classify the function by operational use—business capability or monitoring/platform function—and choose the standard or warning topic according to “Alarm destination and warning routing.” If the purpose cannot be derived from source or requirements, clarify it before defining routing.
* Verify that the log group and `FilterPattern` match logs actually emitted. Do not treat the application-error alarm as equivalent to every other signal the function needs.
* For Kinesis or DynamoDB Streams consumers, enable the fragment's `IteratorAge` alarm only after configuring its threshold and evaluation periods for the tolerated lag.

**Checks:** the fragment receives the correct function, topic, and tuning values; the filter matches expected logs; any `IteratorAge` alarm matches the trigger type and tolerated lag.

#### Parameter and secret caching in Lambda

**When it applies:** repeatedly reading SSM parameters or secrets from a Lambda.

* Consider using the `AWS-Parameters-and-Secrets-Lambda-Extension` layer and integrate it with the read path in application code.
* The default cache duration is 300 seconds.
* Adjust it with `SSM_PARAMETER_STORE_TTL` and `SECRETS_MANAGER_TTL` according to update frequency and acceptable delay before new values are observed.
* Avoid caching when every invocation must read the current value.

**Checks:** when the extension is used, the code calls it and the TTL respects the acceptable refresh delay; when current values are required on every read, the read path bypasses the cache.

#### Lambda subnets

**When it applies:** creating a VPC-connected Lambda or changing destinations called by an existing Lambda.

* Use `SubnetsIds` when destinations are reachable through the internal network or private endpoints.
* Use `VpcEgressSubnetsIds` when NAT egress to external endpoints is required.
* Reuse infrastructure-provided parameters and respect their type: pass a list directly or use `!Split` when the value is a comma-separated string.
* Verify subnets, routing, and security groups together against the actual destinations.

**Checks:** subnets, routes, and security groups cover the required destinations; egress subnets are used only for a real NAT-egress requirement.

#### Retry for Lambda automations

**When it applies:** creating or changing a Lambda automation invoked asynchronously or triggered by Kinesis Data Streams or DynamoDB Streams.

Set retry limits on the mechanism that invokes the Lambda:

* **Asynchronous invocation:** configure `AWS::Lambda::EventInvokeConfig` with `MaximumRetryAttempts` and, where needed, an `OnFailure` destination.
* **Kinesis or DynamoDB Streams trigger:** configure attempts in the `EventSourceMapping`, and consider maximum record age and the error destination.
* Size limits according to criticality and the useful processing window. For non-critical monitoring jobs, avoid prolonged retries of events that are no longer useful.

**Checks:** limits are configured on the actual invocation mechanism and match the useful processing window; any error destination is connected.

#### Direct Lambda-to-Lambda invocation

**When it applies:** a new Lambda directly invokes another Lambda to relay or sequence work.

* Treat direct invocation as an architectural anti-pattern by default: it couples the functions' execution, permissions, timeouts, retry behavior, and operational ownership.
* First check whether a shared library, an existing event contract, a queue, or an explicit workflow fits the actual responsibility and response requirement. Do not add infrastructure merely to avoid a direct call.
* If a direct invocation remains necessary, explain the concrete reason and agree the exception with the user before implementation. Define failure propagation, retries, idempotency, and timeout boundaries; do not assume all existing SEND integrations follow one pattern.

**Checks:** the chosen interaction follows the required business contract and failure behavior; any direct-invocation exception is explicit and justified.

#### Concurrency limits for SQS-triggered Lambdas

**When it applies:** setting `ScalingConfig.MaximumConcurrency` on an SQS Event Source Mapping or `ReservedConcurrentExecutions` on its Lambda.

* Distinguish the per-mapping `MaximumConcurrency` from the function-wide reserved concurrency. For multiple SQS mappings on one function, compare the sum of their caps with the function's reserved concurrency; a lower function cap can throttle invocations.
* Size the caps against intended throughput, queue backlog, downstream capacity, and other invocation sources. Do not copy one limit mechanically to every mapping or infer that the same `ScalingConfig` applies to Kinesis or DynamoDB Streams.
* When limits must vary by environment, use the established parameter path. Check supported service bounds and whether the mapping uses a scaling mode compatible with `MaximumConcurrency`.

**Checks:** mapping caps and function capacity are mutually consistent; the intended back-pressure and recovery behavior remain observable.

#### Lambda versions and aliases with Provisioned Concurrency

**When it applies:** introducing or changing a Lambda that uses Provisioned Concurrency.

* Define an `AWS::Lambda::Version` resource and a `live` alias pointing to the published version. Configure provisioned capacity on the alias through a parameter.
* Add `UpdateDeploymentTransform` to the template's `Transform` section and include `PnPlaceholderEpochSeconds` in the version resource logical ID:

```yaml
Transform:
  - UpdateDeploymentTransform

Resources:
  ExampleLambdaVersionPnPlaceholderEpochSeconds:
    Type: AWS::Lambda::Version
    Properties:
      FunctionName: !Ref ExampleLambda
```

* The transform replaces the placeholder with a timestamp and updates references in the template. The new logical ID creates a new version resource; changing function code alone does not guarantee publication of a new version.
* Connect the alias to the version with `!GetAtt ExampleLambdaVersionPnPlaceholderEpochSeconds.Version`.
* Point integrations and invocation permissions to the alias. Calls to the unqualified function do not use the provisioned capacity on `live`.

**Checks:** the template contains the transform, version, and connected alias; provisioned capacity is configured on the alias, and integrations and invocation permissions reference that alias.

#### Lambda batch processing on Kinesis and DynamoDB Streams

**When it applies:** creating or changing an `AWS::Lambda::EventSourceMapping` between a Lambda and Kinesis Data Streams or DynamoDB Streams.

* Parameterize `BatchSize` according to expected processing time and the Lambda timeout.
* Enable `ReportBatchItemFailures` only when the consumer implements the required partial-batch response.
* Consider `BisectBatchOnFunctionError` to isolate problematic records together with application error handling and retry policy.
* Verify that the consumer can reprocess records without duplicating effects.

**Checks:** batch size matches expected processing time; partial-response and batch-bisection options are compatible with consumer code and replay handling.

#### Retry and monitoring for Lambda consumers of Kinesis and DynamoDB Streams

**When it applies:** creating or changing failure handling for a Lambda–Kinesis Data Streams or Lambda–DynamoDB Streams Event Source Mapping.

* Configure `MaximumRetryAttempts` and `MaximumRecordAgeInSeconds` according to flow criticality, tolerated delay, and stream retention.
* Configure `DestinationConfig.OnFailure` when unprocessed events must be recovered. Select a destination based on the retained payload and recovery process.
* Configure an `IteratorAge` alarm with a parameterized threshold based on acceptable lag.
* When an error destination exists, also monitor delivery failures through `DestinationDeliveryFailures`.

**Checks:** retry limits, record age, and retention support the required recovery; alarms cover processing lag and any failures delivering to the destination.

#### Starting position for Kinesis and DynamoDB Streams mappings

**When it applies:** creating or replacing an Event Source Mapping between Lambda and Kinesis Data Streams or DynamoDB Streams, or changing its intended starting position.

* Evaluate `StartingPosition` explicitly:

    * `TRIM_HORIZON`: process from the oldest record still available.
    * `LATEST`: read new records without consuming the backlog.
    * `AT_TIMESTAMP`, for Kinesis only: read from a specified time.

* Treat the choice as a material functional and operational decision, considering event recovery, possible omissions, replay, and consumer capacity.
* Agree the starting position with the user for new implementations. Require explicit authorization before changing an existing position or replacing a mapping in a way that affects the read position.
* Do not assume a default starting position when the required behavior is unspecified.

**Checks:** the starting position and its effect on backlog and continuity were agreed; changes to existing mappings have the required authorization.

These three stream rules apply to direct Lambda–Kinesis Data Streams and Lambda–DynamoDB Streams integrations. They do not automatically apply to Firehose transformation Lambdas or SQS consumers.

### API Gateway

#### API Gateway integration

**When it applies:** exposing a new component through API Gateway or changing its integration.

* Verify the component's expected OpenAPI artifacts and consistency among codegen configuration, authorizer, and the CloudFormation template that publishes them.
* If artifacts are missing or expected authentication is undefined, request the development references before completing the integration.
* Do not fix generated files alone.

**Checks:** required OpenAPI artifacts exist and are consistent with codegen, authorizer, and template; missing sources or unresolved authentication decisions are reported before completion.

#### Associate APIs with Usage Plans

**When it applies:** creating an API or recreating one with a new ID when it uses centralized Usage Plans.

* Set `IntendedUsage` in `api-gw-expose-service-openapi.yaml`; the fragment automatically assigns the `PN_APIGW_TYPE` tag.
* Verify that the `unique` stage is associated with the required plans through `pn-cicd/cd-cli/deployApiGwUsagePlan.sh`. The CORE pipeline `cd-cli/cnf-templates/complete-pipeline.yaml` invokes these associations:

    * `B2B` → `pn_usageplan_small`, `pn_usageplan_medium`, `pn_usageplan_large`.
    * `IO` → `APP_IO_BE`.
    * `PNPG` → `SELCPG`.

* For a component-only release, verify that Usage Plan updates include the new API; deploying the microservice alone does not guarantee this association.

Examples: `pn-external-registries` exposes APIs with `IntendedUsage: B2B` and `IO`; `pn-national-registries` uses `PNPG`.

**Checks:** the release path associates the new API and stage with the intended plan; `IntendedUsage` in the template is not considered sufficient by itself.

### EventBridge and schedules

#### Schedule expression and state

**When it applies:** creating or changing an EventBridge rule or EventBridge Scheduler schedule.

* Parameterize the `rate` or `cron` expression when frequency may vary by environment or operational need. Do not hardcode a frequency that must remain configurable.
* Parameterize state with allowed values `ENABLED` and `DISABLED`, define an intentional default, and propagate it from the cfg files used by the deployment path.
* For EventBridge Scheduler, configure a time zone when the schedule has local operational meaning; for execution independent of civil time, keep UTC semantics explicit.
* If an `AWS::Events::Rule` invokes a Lambda, restrict `AWS::Lambda::Permission` to the rule with `SourceArn` and to the account with `SourceAccount: !Ref AWS::AccountId`. For `AWS::Scheduler::Schedule`, use an execution role with only the permissions required by the target.
* Do not change unrelated existing schedules merely because they contain hardcoded values. For affected schedules, verify the effect of the new default in every relevant environment.

**Checks:** expression and state are configurable through the intended path; default, time zone, and target permission match required behavior in each affected environment.

### ECS

#### JVM configuration for ECS services

**When it applies:** introducing or changing JVM options for a Java ECS service.

* Expose JVM options through `JavaToolOptions` in `microservice.yml` and pass them to `ecs-service.yaml`.
* Configure environment-specific values in the corresponding configuration files rather than placing them directly in the template.
* Preserve the `JAVA_TOOL_OPTIONS` composition defined by the fragment, including the instrumentation agent.

**Checks:** the environment value passes through `JavaToolOptions` into the fragment and contributes to `JAVA_TOOL_OPTIONS` without removing required instrumentation.

## Terraform

### Environment configuration and generated files

**When it applies:** adding or changing Terraform configuration in `pn-infra-core` or `pn-infra-confinfo`.

* Identify affected environments and update the repository's `codegen/pn-infra-configurations.yaml` matrix.
* For a new variable, add its Terraform declaration and connect it to the resources or modules that consume it.
* Ask the user to run codegen to generate environment variable files. Do not edit generated `terraform.tfvars` files manually.
* Keep these configurations in the appropriate Terraform repository, not in `pn-configuration`.
* After generation, verify that produced values match the matrix and unrelated environments did not change.

**Checks:** distinguish completed changes from files still awaiting generation; verify generated values before considering them aligned with the matrix.

### Modules and versions

**When it applies:** developing a feature that uses Terraform modules, providers, or a Terraform version already defined by the repository.

* Preserve adopted module sources and versions. Do not upgrade Terraform or providers while implementing an unrelated feature.
* Registry modules use explicit versions; local modules follow the repository revision.

**Checks:** the functional change introduces no module-source or version update; registry modules retain explicit versions.

### Module reuse

**When it applies:** adding Terraform resources that may already be covered by an adopted module.

* Prefer adopted modules when they cover the use case, including VPC, VPC Endpoint, ACM, and local diagnostic modules.
* Create local modules for coherent, reusable groups of resources; do not force every single resource into its own module.

**Checks:** existing modules were evaluated for the use case; any new module groups resources with coherent responsibility and real reuse value.

### Terraform code organization

**When it applies:** adding resources, variables, outputs, shared computations, or local modules.

* Place resources in the thematic files under `src/main`.
* Keep variables in `98-variables.tf`, outputs in `99-outputs.tf`, and shared computations in `15-locals.tf`.
* Organize local modules with `main.tf`, `variables.tf`, and `outputs.tf`.

**Checks:** additions follow the repository's expected thematic files and module structure.

### Structured configuration and resource identity

**When it applies:** introducing or changing configurable collections and resources instantiated with `count` or `for_each`.

* For configurable collections, use typed variables and `for_each` with stable logical keys, as done for IAM roles and DNS records.
* Do not rename keys or incidentally change `count` to `for_each`; doing so changes resource identity in Terraform state.

**Checks:** existing keys preserve their mapping to resources; any Terraform address change is identified and handled explicitly rather than treated as code reordering.

## CI/CD

### Ownership of configuration and artifacts

**When it applies:** a change requires new values, artifacts, or steps in SEND build and deployment paths.

* Keep the authoritative source with the owning repository: `pn-infra-core` and `pn-infra-confinfo` for Terraform variables and outputs; `pn-infra` and component repositories for CloudFormation templates; `pn-cicd` for packaging, pipelines, scripts, and parameter injection; `pn-configuration` for versions and configuration promoted to higher environments.
* For initial implementation, start with the component repository's development cfg files when present. Do not modify `pn-configuration` automatically: updates for test, UAT, hotfix, and production require authorization and occur after initial validation.
* Do not duplicate in cfg files values already supplied by Terraform outputs, Infra stacks, component storage, or the pipeline.

**Checks:** each value has one authoritative source; the change affects only authorized repositories and environments; `pn-configuration` updates remain separate from initial implementation.

### Deployment-script contracts

**When it applies:** adding or changing parameters, outputs, templates, or scripts used by a SEND deployment.

* Identify the pipeline and script that deploy the component, then trace the value through cfg files, outputs, merges, and the CloudFormation command. Use targeted searches for repository, component, and parameter names instead of reading very long pipeline files in full.
* Preserve the conventions of the affected path for names, transformations, fallbacks, and optional cfg files. Do not automatically transfer behavior observed in CONFINFO to CORE, or vice versa.
* A new parameter without a `Default` must be populated in every path that invokes the template. When an existing consumed contract changes, update producers and consumers and define a compatible release order.
* Do not add component-specific checks to a generic script when the constraint belongs in the template, configuration, or a dedicated validation.

**Checks:** the parameter or output is traced end to end in every affected path; no caller lacks a required value, and the release order avoids temporary contract incompatibility.

### Build, promotion, and distributed state

**When it applies:** changing build, packaging, version selection, or promotion between environments.

* Produce artifacts identified by commit, version, or digest and promote the same artifact without rebuilding it for the next environment.
* Distinguish automatic development deployment from higher-environment paths initiated and configured through `pn-configuration`. Success in development alone does not prove the promotion path.
* Do not infer deployed state from a branch or local file. When the effective version in an environment matters, use an authorized operational source or state that it was not verified.
* If a change alters artifact structure or content, verify the pipeline producer, storage, metadata, and consumer together.

**Checks:** the promoted artifact is the one that was validated; version and digest are traceable; conclusions about environment state come from an operational source rather than Git content alone.
