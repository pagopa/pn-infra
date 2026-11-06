# output-contract-case-a

Synthetic repository snapshot for read-only evaluation. Paths below are relative to the fixture workspace. Each fenced block contains the complete file contents.

## pn-infra/stack.yaml

````yaml
AWSTemplateFormatVersion: '2010-09-09'
Parameters:
  QueueArn:
    Type: String
Resources:
  Marker:
    Type: AWS::CloudFormation::WaitConditionHandle
Outputs:
  ProcessingQueueArn:
    Value: !Ref QueueArn
  LegacyQueueArn:
    Value: !Ref QueueArn
````

## pn-cicd/prepare-parameters.sh

````bash
#!/usr/bin/env bash
set -euo pipefail
# Input is the JSON response of describe-stacks; no AWS calls are made here.
jq -e '[.Stacks[0].Outputs[] | select(.OutputKey == "LegacyQueueArn")][0].OutputValue // error("Required output LegacyQueueArn is missing")' "$1"
````

## CONTEXT.md

````markdown
# Output contract
The prior producer exposed LegacyQueueArn. ProcessingQueueArn is the proposed new name.
The included consumer is the only deployment consumer in this synthetic scenario and is unchanged.
Review compatibility using these files. Do not execute deployment commands.
````
