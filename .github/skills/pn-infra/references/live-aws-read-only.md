# Live AWS read-only access

This procedure applies only when the task requires information from actual AWS resources. It does not apply to AWS Knowledge MCP or public documentation, which use no AWS account credentials and cannot inspect the user's infrastructure.

## Authorization gate

Before each logically related group of live queries:

1. State the target SEND environment or expected AWS account, service, region and exact information to retrieve.
2. Show the exact command or tool invocation and state that it is read-only. Explain whether it returns identifiers, configuration, status, metrics or logs.
3. Ask the user to identify or confirm the read-only AWS profile or role and authorize that query. A profile name that appears read-only is not sufficient evidence without user confirmation.
4. If the expected account identity has not been established, include a read-only `sts get-caller-identity` check using the same explicit profile and region, and compare the returned account with the intended environment before issuing the service query.

Authorization is limited to the stated account or environment, region, service, data and commands. A later query with different scope requires a new explanation and authorization.

## Transparent AWS CLI commands

Every AWS CLI command must contain literal `--profile <confirmed-profile>` and `--region <target-region>` arguments. In the actual approval request, replace placeholders with the concrete values; do not execute a command containing shell variables or unresolved placeholders. For regional SEND services, use the confirmed target region; when a service is global, state that explicitly rather than hiding the context.

Do not rely on the shell's default profile or region. Do not use `AWS_PROFILE`, `AWS_REGION`, `AWS_DEFAULT_REGION`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN`, `export`, shell variables, aliases, functions or wrapper scripts that make the selected identity or region invisible in the approval prompt.

Group compatible read-only calls in one approval only when every literal command and its scope remain visible. Do not mix account reads with local writes, authentication, role assumption or any state-changing action.

## Missing access

If no read-only profile is available, its permissions are uncertain, credentials are expired, SSO authentication is missing or the expected account cannot be confirmed:

- report the exact blocker;
- ask the user to select or prepare the appropriate read-only profile and perform any required authentication themselves;
- do not run `aws configure`, `aws sso login`, `sts assume-role`, credential exports or profile changes;
- do not fall back to a more privileged profile.

Never request secret access keys, session tokens or credential-file contents. Never copy credentials into commands, task memory, logs or chat.
