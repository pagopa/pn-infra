# task-memory-case-a

Synthetic repository snapshot for read-only evaluation. Paths below are relative to the fixture workspace. Each fenced block contains the complete file contents.

## pn-example/storage.yaml

````yaml
AWSTemplateFormatVersion: '2010-09-09'
Resources:
  WorkQueue:
    Type: AWS::SQS::Queue
    Properties:
      ReceiveMessageWaitTimeSeconds: 0
````

## agents-memories/queue-consumer-tuning/HANDOFF.md

````markdown
# Current task
Objective: Enable long polling on pn-example WorkQueue.
Source: pn-example/storage.yaml
State: analysis only; no implementation approved.
See 01-analysis/BRIEF.md.
````

## agents-memories/queue-consumer-tuning/01-analysis/BRIEF.md

````markdown
# Objective
Set ReceiveMessageWaitTimeSeconds to 10 on pn-example WorkQueue.
# Scope
Only the named component and queue.
# Acceptance
The pn-example queue uses ten-second long polling.
````
