# SEND Architectural Patterns and Infrastructure as Code

## Context and objectives

This document collects SEND architectural and infrastructure patterns and guidelines. It provides a foundation for the Infra team's development guidelines and a starting point for building AI tools that support agentic infrastructure development.

## 1. High-level SEND architectural patterns

### 1.1 Domains, environments, and AWS accounts

* SEND has five environments: **dev, test, uat, hotfix, and prod**.
* Each environment has two domains: **PN-CORE** and **PN-CONFINFO**. Each domain maps to a dedicated AWS account in each environment, for a total of **10 AWS accounts**.
* An additional AWS account dedicated to **CI/CD** centralizes build pipelines and Docker image management.
* **PN-CORE** hosts application services that manage the notification lifecycle, workflow orchestration, and SEND API exposure.
* **PN-CONFINFO** handles confidential data, documents, and related integrations through services such as Data Vault, Safe Storage, External Channel, and Conservazione a Norma.

### 1.2 Communication between SEND domains — CORE and CONFINFO

* The main synchronous pattern is **CORE → CONFINFO**: CORE services invoke Data Vault, Safe Storage, and External Channel through AWS PrivateLink.
* CORE provides Interface VPC Endpoints. CONFINFO exposes VPC Endpoint Services connected to internal Network Load Balancers, which forward traffic to the Application Load Balancers of CONFINFO services.
* Endpoint services allow connections from the CORE account.
* CORE services reach CONFINFO through Interface VPC Endpoints in their VPC. Endpoint security groups allow connections from the CORE network on the required ports. This network control is separate from application authorization.
* PrivateLink exposes specific services without providing general connectivity between VPCs. API Gateway VPC Link instead connects APIs to private backends.
* Asynchronous flows include **CONFINFO → CORE** communication through EventBridge.

#### SEND examples

* For Conservazione a Norma, PN-CN also uses direct invocation of CONFINFO Lambdas from API Gateway in CORE, authorized by cross-account permissions. The direction remains CORE → CONFINFO, with an integration other than PrivateLink.

### 1.3 Event Bus and event routing

* The PN Core Event Bus, based on Amazon EventBridge, centralizes routing for several SEND flows and accepts authorized publications from CONFINFO.
* EventBridge rules act as dispatchers: `EventPattern` selects events, for example through `detail-type` and fields under `detail`, and forwards them to targets.
* Targets include SQS queues and Lambda functions. The payload may be selected or transformed before forwarding. Dedicated targets record intercepted events.
* For configured targets, `DeadLetterConfig` sends delivery failures to `pn-CoreEventBus-DLQ`, which has an alarm. The same queue also receives errors from the Address Manager → Delivery Push forwarding Lambda.

#### SEND examples

* Action Manager publishes ready actions to the Core Event Bus through the `pn-action-router-manager` and `action-enqueuer-manager` Lambdas. Rules select the action type and route it to the Delivery Push Workflow and Delivery Push Validator queues.
* The Address Manager → Delivery Push flow passes through a Lambda that delays message enqueueing.

### 1.4 Event streams and CDC

* SEND uses DynamoDB Streams and Amazon Kinesis Data Streams for asynchronous processing. Change Data Capture (CDC) flows collect DynamoDB record inserts, updates, and deletions.
* DynamoDB Streams and Kinesis are separate mechanisms and may both be present on the same table. Records can feed application processing and analytics collection flows.
* CDC data is also archived to S3 through Amazon Data Firehose. Archived data can be queried with Amazon Athena for analysis and historical reconstruction through dedicated tables and views.

<!-- Confluence reference: Athena documentation link to be added. -->

#### SEND examples

* In Delivery, DynamoDB Streams triggers a Lambda that publishes new-notification events to the Core Event Bus.
* Kinesis CDC streams feed Lambdas in several components. In `pn-stream`, a Lambda reads timeline changes and forwards them to an SQS queue consumed by the microservice.

### 1.5 SQS queues and DLQs

* SQS queues hold messages awaiting processing and decouple producer timing from consumer timing. In EventBridge flows, the bus selects destinations while queues feed consumers.
* A queue maps to a processing responsibility. A microservice may consume multiple queues for different workloads.
* Separate queues allow pending messages, retries, and DLQs to be managed independently. Queue separation does not imply isolated consumer compute resources.
* Consumers of the same queue compete for messages. To deliver the same event to independent processing responsibilities, use distinct queues.
* For queues with redrive, `maxReceiveCount` controls transfer to the DLQ after repeated receipt without deletion. This counter is separate from application-workflow attempts. Other DLQs receive explicit writes from components; distinguish those error paths from SQS redrive.

#### SEND examples

* IO Connector separates message submission from result polling, with one queue and one DLQ for each workload.

### 1.6 Networking: VPCs, subnets, and Availability Zones

* CORE and CONFINFO application VPCs span **three Availability Zones**, with subnets separated by purpose.
* The network distinguishes:

    * **internal subnets**, without Internet egress, for private components and connections;
    * **egress subnets**, private, with Internet access through NAT Gateways;
    * **public subnets**, connected to the Internet Gateway, hosting NAT Gateways and any intended public ingress.

* CORE and CONFINFO provide one NAT Gateway per Availability Zone for egress subnets.
* Application ECS services use private internal or egress subnets without public IP addresses. Application Load Balancers for CORE and CONFINFO services are internal. Lambdas that need VPC access use subnets appropriate to their destinations.
* S3 and DynamoDB are reached through Gateway VPC Endpoints. Other AWS services use Interface VPC Endpoints with private DNS and dedicated security groups.
* Multi-AZ network distribution supports resilience to zonal failures; service availability also depends on replicas and downstream dependencies.

#### SEND examples

* Specialized components may have dedicated VPCs: PDF Raster runs in a CONFINFO VPC without a NAT Gateway and is reached through PrivateLink.

### 1.7 Alarm and warning-notification routing

* Standard alarms use the notification path based on `pn-AllAlarmSnsTopic`, which feeds the standard flow to the configured Slack channel.
* Warning routing uses the central `pn-WarningSnsTopic` in CORE. An SNS subscription feeds an SQS queue with a DLQ; a dispatcher Lambda selects an environment-specific route and forwards the notification to the intended Slack channel.
* Routes may use `DROP` to suppress an event explicitly. Without a valid route, the dispatcher reports an error and the message follows the queue retry path.
* The producer selects one of the two topics but does not know the Slack channel or bot token. Publishing the same alarm to both topics produces duplicate notifications. The warning topic may also receive application reports, which the dispatcher handles under a contract distinct from CloudWatch alarms.

#### SEND examples

* Technical alarms for the Warning Notification Dispatcher publish to the warning topic; `pn-send-pdnd-automation` uses the same topic for its alarms.

## 2. Infrastructure as Code design patterns

### 2.1 IaC repository structure and organization

Base infrastructure is managed with Terraform in `pn-infra-core` and `pn-infra-confinfo`. Higher-level shared resources, including compute resources, are defined with CloudFormation in the central `pn-infra` repository. Resources owned by individual services remain in their component repositories.

Repositories dedicated to configuration control, artifact generation, and CI/CD complete this organization.

#### pn-configuration

A private configuration-control repository that defines SEND release composition for **test, UAT, hotfix, and prod**, associating repository versions, application images, and configuration.

* **Version manifest:** `repository-list.json` lists versions for microservices, infrastructure, other deployed components, and CI/CD scripts. Repository revisions use **commit IDs or Git tags**.
* **Repository–image pair:** each containerized component, such as an ECS microservice, has two references:

    * `<component>_commitId`: commit ID or Git tag selecting the revision that contains source code and deployment templates;
    * `<component>_imageUrl`: Docker image to run, identified by a **SHA-256 digest**.

    For example, `pn_delivery_commitId` and `pn_delivery_imageUrl` define the pair for Delivery. Components without a Docker image keep only the repository revision reference.

* **Environment configuration:** directories mirror component repository paths and contain CloudFormation parameters in `*-cfg.json`, application `.env` files, and frontend configuration. During deployment, CI/CD overlays them on the files from the selected revision.
* **System configuration:** `_conf` separates CORE and CONFINFO and contains Parameter Store, DynamoDB, and application configuration.

**This mechanism is not used for development releases.** Development uses cfg files from component repositories and `config/desired-commit-ids-env.sh` in the CD Artifact bucket for version selection. The file is managed manually and updated by build events that feed automatic deployment.

**Parameter Store**

* SSM parameters under configuration control are maintained per environment and domain under `_conf/<core|confinfo>/system_params`, using `.param` files and a manifest that maps files to parameter names.
* CI/CD compares tracked values with values in AWS and reports differences. This check does not update Parameter Store.
* Value synchronization is a separate operation; `pn-infra` contains dedicated system-parameter management tools.

**Secrets Manager**

Secret creation and population follow a path separate from SSM parameter control:

* **Self-generated secrets:** passwords or tokens generated internally should preferably be created through IaC, stored in Secrets Manager, and supplied to the consuming resource from the same generated value.
* **Secrets from external sources:** credentials, tokens, or keys retrieved from **Keeper** or supplied by other systems must preserve the received value. Current practice creates and populates these secrets manually through the AWS Secrets Manager console.

IaC generation examples include database credentials in the `pn-infra` Aurora/RDS fragment, the read-only database user password in `pn-simulatore-recapiti`, and the Redis token in `pn-hub-spid-login-aws`.

#### pn-infra-core

Defines CORE base infrastructure in Terraform: VPCs, subnets, private connectivity, load balancers, VPC Link, and DNS.

The `codegen/pn-infra-configurations.yaml` matrix describes the infrastructure model and environment variants. `pn-codegen` generates the corresponding `terraform.tfvars`, which deployment selects.

**Terraform variables are maintained in this repository, not in `pn-configuration`. In the version manifest, `pn-configuration` selects only the repository version to deploy.**

#### pn-infra-confinfo

Defines CONFINFO base infrastructure and specialized VPCs such as PDF Raster in Terraform: networking, subnets, endpoints, load balancers, and PrivateLink services.

It maintains its own `codegen/pn-infra-configurations.yaml` matrix, from which `pn-codegen` produces environment- and domain-specific `terraform.tfvars`.

**Terraform variables are maintained in this repository, not in `pn-configuration`. In the version manifest, `pn-configuration` selects only the repository version to deploy.**

#### pn-infra

Contains CloudFormation stacks for shared CORE and CONFINFO infrastructure: ECS clusters, Event Bus, IPC communication, storage, cache, logging, monitoring, data analytics, and automation.

* `runtime-infra/`: shared CORE-domain stacks and support components, including Lambdas, analytics configuration, and account-wide resources.
* `runtime-infra-confinfo/`: shared CONFINFO-domain stacks, including storage, runtime, and monitoring resources.
* `runtime-infra/fragments/`: parameterized, reusable templates for SQS queues, Lambdas, ECS services, API exposure, and other resources.

Fragments follow a **modular composition pattern**: each template defines a component that can be instantiated multiple times with different parameters, composing resources reproducibly. The principle resembles Terraform modules; CloudFormation reuse uses **nested stacks** with explicit parameters and outputs.

Templates are published to S3 at the `pn-infra` revision selected for a release and are invoked by shared stacks and business components.

#### Infrastructure as Code in business components

Microservice and Lambda repositories define their owned infrastructure resources, generally under `scripts/aws/cfn/`:

* `storage.yml`: persistent and support resources such as tables, buckets, queues, and log groups.
* `microservice.yml`: ECS/Lambda runtime, triggers, permissions, integrations, and API exposure.
* `data-quality.yml`, where present: Glue resources that catalog CDC data archived in S3 and make it available to Athena analysis.

Templates reuse shared fragments and receive resource references through stack parameters and outputs.

#### pn-cicd

The repository dedicated to **Continuous Integration in the centralized PN-CI/CD AWS account** and deployment pipelines in SEND environment accounts.

* `ci/bootstrap/`: initial CI pipeline configuration and resources needed to start it.
* `ci/infra/`: shared CI infrastructure, including CodeArtifact package repositories, artifact buckets, and Event Bus. `root.yaml` composes shared resources and builders and is deployed by the CI pipeline after initial bootstrap.
* `ci/builders/`: CodeBuild templates for building, checking, and packaging Java, Node.js, frontend, and infrastructure projects. Depending on the component, builders produce packages, Docker images published to ECR, and Lambda or static artifacts published to S3.
* `cd-cli/`: deployment scripts for Terraform and CloudFormation infrastructure, ECS services, Lambdas, and frontends. It includes:

    * `cnf-templates/`: CD pipeline definitions, including CORE and CONFINFO;
    * `commons/`: shared functions for collecting and composing parameters, preparing environment files, publishing artifacts, and tracking releases;
    * `checkSystem/`: system-configuration checks, including comparison of SSM parameters.

* `docs/` and `tool/`: system documentation and support utilities, including dependency-report tools.

CD pipeline definitions are deployed and updated manually in the relevant accounts. Scripts instead follow the revision selected for the release: the pipeline downloads and uses them in its stages without updating the pipeline definition itself.

CD script parameter collection and propagation are described in **section 2.2**. Automatic deployment after build events is used operationally only in **dev**.

#### pn-codegen

Produces configuration artifacts used by Terraform and API Gateway:

* **Terraform:** transforms CORE and CONFINFO YAML matrices into environment-specific `terraform.tfvars` files.
* **OpenAPI:** generates external specifications, optional bundles, and AWS OpenAPI files from internal contracts and `codegen/config.json`. Rules select APIs and exposure channels.
* **API Gateway:** generated OpenAPI files include backend integrations, mappings, and authorizer settings, including identity sources and cache. Lambda authorizer code remains separate in `pn-auth-fleet`.

Component CloudFormation templates import generated OpenAPI files. Codegen changes reach APIs through regeneration of component artifacts and their subsequent deployment.

### 2.2 CloudFormation parameter provenance and propagation

The main path is **Terraform outputs → Infra stacks → component stacks**, combined with configuration files and values produced by the pipeline.

#### Value sources

* **Terraform outputs:** the pipeline exports `pn-infra-core` or `pn-infra-confinfo` outputs to `terraform-<environment>-cfg.json`, adapting names and formats to CloudFormation inputs.
* **Stack outputs:** identify already-created resources and shared values required by downstream stacks.
* **`*-cfg.json` files:** provide stack- and environment-specific values. Development uses files from component repositories; test, UAT, hotfix, and prod use corresponding configuration in `pn-configuration`.
* **Pipeline values:** include version, artifact references, container image, and other parameters built during deployment.

#### Terraform output normalization in deployNetworking.sh

For outputs processed by `pn-cicd/cd-cli/deployNetworking.sh`, the script removes the selected `Core_` or `ConfInfo_` prefix when writing `terraform-<environment>-cfg.json` under `Parameters`. For example, `Core_NetworkLoadBalancerLink` becomes `NetworkLoadBalancerLink`. In `pn-infra-core/src/main/99-outputs.tf`, this output contains the API Gateway VPC Link ID, not the NLB ARN; the VPC Link targets the NLB defined in `60-load-balancers.tf`.

Trace **Terraform resource → Terraform output → CI/CD transformation → CloudFormation parameter → nested stack, if present → consuming property**. Verify the deployment script actually used: do not assume this normalization for direct Terraform-output consumers or CloudFormation output-merge helpers.

#### Pass-through and composition

* Infra stacks receive base parameters and expose selected values as outputs. **Pass-through** parameters are re-exposed without changing their value, such as a VPC reference.
* CORE aggregates outputs from `pn-infra-storage`, `pn-cache`, `pn-infra`, and `pn-ipc`; CONFINFO aggregates outputs from `infra-storage` and `infra`.
* Deployment scripts combine these outputs with cfg files and component-stack outputs. Runtime stacks receive, for example, references to resources created by the storage stack.
* Passing values between stacks is explicit and implemented by CI/CD scripts. Templates then pass parameters to the nested fragments that consume them.
* Merge order determines which value wins when names collide and depends on the script: CORE and CONFINFO paths do not necessarily use the same precedence.
* Some deployments consume Terraform outputs directly rather than requiring all values to be re-exposed by Infra stacks.

### 2.3 Runtime configuration for ECS components

`.env` files provide application configuration to ECS containers through a path distinct from CloudFormation parameters.

* **Dev:** values are maintained in `scripts/aws/cfn/application-dev.env` in the component repository.
* **Test, UAT, hotfix, and prod:** `scripts/aws/cfn/application-<environment>.env` files are maintained in `pn-configuration` under paths corresponding to component repositories. CI/CD overlays them on files from the selected revision.
* **S3 publication:** `deployEcsService.sh` computes the SHA-256 checksum of the resulting file and invokes `commons/upload-files-runtime.sh`. The file is published as `application-<checksum>.env` under the component prefix in `pn-runtime-environment-variables-<region>-<account>`.
* **Task configuration:** the checksum is passed to the runtime stack through `ApplicativeEnvFileChecksum` and then to `pn-infra`'s `ecs-service.yaml` fragment. The Task Definition loads the application file and `runtime-variable.env` from S3 through `EnvironmentFiles`. Without a checksum, it uses `application.env`.
* **Configuration updates:** changing the application file changes the checksum and S3 reference in the Task Definition, producing a new revision even when the Docker image is unchanged.

### 2.4 Resource organization across stacks

#### Shared stacks

In `pn-infra`, shared resources are deployed in distinct stacks:

* **Infrastructure storage:** `pn-infra-storage.yaml` for CORE and `infra-storage.yaml` for CONFINFO define buckets for logs and runtime configuration, shared Kinesis streams, and related encryption keys.
* **Runtime infrastructure:** `pn-infra.yaml` for CORE and `infra.yml` for CONFINFO define ECS clusters, roles, and supporting runtime components.
* **Cross-cutting integrations and services:** in CORE, `pn-ipc.yaml` defines several inter-component communication queues; `pn-event-bridge.yaml` defines the Core Event Bus and routing rules. Cache, monitoring, and data analytics have additional dedicated stacks.

#### Component stacks

Resources owned by one component are generally split into:

* `storage.yml`: DynamoDB tables, S3 buckets, queues and DLQs, Kinesis streams, and component log groups. Delivery, for example, defines notification tables here; Safe Storage defines document buckets and processing queues.
* `microservice.yml`: ECS services, Lambdas, execution roles and policies, triggers, and API integrations. The ECS service uses the shared cluster received as a parameter, while data resources belong to storage.
* `data-quality.yml`, where present: Glue tables and crawlers for component CDC data, connected to the shared analytics Glue database and bucket.

For ECS deployment, storage and runtime are separate stacks: `<component>-storage-<environment>` and `<component>-microsvc-<environment>`. The pipeline deploys storage first and passes its outputs to runtime, then deploys the data-quality stack when present. This separation keeps data and support resources distinct from runtime definitions even when they are updated in the same release.

#### Links between stacks

Resource placement and consuming component do not necessarily coincide. Safe Storage → Delivery Push and Paper Channel → Service Desk queues are defined in `pn-ipc.yaml`, while consumers belong to the corresponding microservices. Other queues, including some fed by external components, are defined in service `storage.yml` files.

Resource names, ARNs, and URLs reach consuming stacks through outputs and parameters. CI/CD scripts compose these links according to **section 2.2**.

Stack organization may be adapted to component needs after considering dependencies, release lifecycle, and migration of existing resources.

### 2.5 CI/CD in SEND

#### CI automation through GitHub Actions

| Repository | Trigger and operations |
| --- | --- |
| `pn-infra`, `pn-infra-core`, `pn-infra-confinfo` | Push, pull request, and schedules: Trivy scanning of IaC templates and publication of findings to GitHub Security. |
| `pn-frontend` | Push, pull request, and weekly schedule: CodeQL JavaScript/TypeScript analysis on configured branches. Manual workflow to update the BFF dependency. |
| `pn-bff` | Manual workflow to update microservice dependencies. |
| `pn-cicd` | Manual Java release workflow: repository, version, and branch selection; POM and SNAPSHOT dependency checks; release branch, RC tag, and GitHub release management. Merge to `main` and SNAPSHOT increment according to selected options. |
| `pn-codegen` | Push to `develop`, `main`, `releases/**`, tags, and PRs to `develop`/`main`: build and publish the OpenAPI generator image to GHCR. Components select its version through `generate-code.sh`. |
| `pn-load-test` | Push to `main`: publish a GHCR image containing k6, load scenarios, and metric-collection tools. The workflow does not execute tests against environments. |
| `pn-local-emulator` | PR and tag: generation, compilation, linting, testing, and Trivy image scanning. Publication to GHCR only for tags. |
| `pn-b2b-client` | Manual Maven/Cucumber workflows: `InteropTracingTest` QA suite and selectable PARI suite. The PARI workflow retains the HTML report for ten days. |
| `pn-lab-docs` | Changes to `specs/**/*.yml` or manual start: HTML generation with Redoc CLI, then commit and push under `docs/`. |

Git operations in the release workflow may trigger CodeBuild webhooks. AWS component builds do not depend on a GitHub Action run.

#### Continuous Integration on AWS

AWS CI runs in the centralized CI/CD account in **Frankfurt (`eu-central-1`)**. `pn-cicd` defines CodeBuild projects and builder templates.

**Triggering**

Projects receive GitHub events through webhooks and filter by event and branch. The containerized Java builder handles `PUSH` and `PULL_REQUEST_MERGED`; the standard frontend builder uses `PUSH`.

One repository may trigger multiple projects: `pn-frontend`, for example, has separate builders for its portals.

**Builders**

Templates under `ci/builders/` cover these paths:

| Builder | Operations |
| --- | --- |
| `mvn-docker` | Maven build and test, image through Spring Boot Build Image, ECR publication. |
| `docker-generic` | Build from the repository Dockerfile and publish to ECR. |
| `mvn-jar` | Build and test; publish Maven artifacts to CodeArtifact for configured branches. |
| `nodejs-lambda`, `nodejs-multilambda`, `multilambda` | Prepare functions, execute required build scripts, and publish ZIP packages. |
| `nodejs-generic` | Run the configured npm script and publish the resulting package to S3. |
| `infra-codebuild` | Install production Node dependencies and package infrastructure functions as ZIP files. |
| `webapp-standard` | Generate clients, test, build the frontend, and publish portal archives. |
| `webapp-sonar`, `webapp-cypress` | Dedicated SonarCloud analysis and Cypress test projects. |
| `not-compiled-repo` | No compilation; emit an event containing repository and commit for configured branches. |

SonarCloud runs where required by the builder or component scripts, including Lambdas in `pn-auth-fleet` _(being phased out)_.

**Docker images**

For Java microservices, `spring-boot:build-image` uses Paketo buildpacks. The builder adds `VCS_COMMIT_ID` and publishes these tags to ECR:

* version and commit tags for `main`, `develop`, `release/*`, and `hotfix/*`;
* also `latest` for `main`;
* `latest_feature_bug` for other branches.

After the push, it retrieves the image URI with its SHA-256 digest, which identifies the image to deploy.

**S3 artifacts**

The CI Artifact bucket stores results under `<repository>/commits/<commit>/`:

* ZIP files for individual Lambdas;
* `functions.zip` containing functions and layers;
* `<portal>.tar.gz` for frontends;
* `static/` for additional assets.

Packages include the commit reference. A Java repository may produce both a Docker image and packages for supporting Lambdas.

**Build event**

On enabled paths, the builder publishes `BUILD_DONE` to `CiEventBus` with repository, branch, component type, commit, and image URI with digest for containers.

The event communicates build references; artifacts remain in S3, ECR, or CodeArtifact.

#### Continuous Delivery and Continuous Deployment

Pipelines run in **CORE and CONFINFO** accounts in **Milan (`eu-south-1`)**.

**Automatic deployment to dev**

1. EventBridge forwards events from `CiEventBus` to the CORE and CONFINFO `CdEventBus` instances in dev.
2. Rules select events: the `develop` branch for components and `main` for `pn-cicd`.
3. The `ChooseCdPipeline` CodeBuild project updates the commit and image in `config/desired-commit-ids-env.sh` in the CD Artifact bucket.
4. The selector identifies and starts the CodePipeline when applicable. For frontends, it first verifies that required packages exist.

`pn-cicd` events update the CD script version without directly starting a pipeline.

**Deployment to other environments**

In **test, UAT, hotfix, and prod**, startup is manual; versions and configurations come from `pn-configuration`. Pipeline operations are automated. Manual startup controls environment use and release order.

**Pipeline execution**

* Retrieve CD scripts and source code at selected revisions.
* Transfer packages from the CI Artifact bucket in Frankfurt to target buckets in Milan.
* Publish templates, fragments, and Lambda ZIP files to the CD Artifact bucket.
* Deploy ECS using the image identified by digest, without rebuilding it.
* Prepare application files and publish them to the runtime configuration bucket.
* Compose CloudFormation parameters according to **section 2.2, CloudFormation parameter provenance and propagation**.
