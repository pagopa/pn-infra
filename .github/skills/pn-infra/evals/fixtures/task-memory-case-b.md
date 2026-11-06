# task-memory-case-b

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

## agents-memories/queue-long-polling/HANDOFF.md

````markdown
# Current task
Objective: Tune queue visibility timeout for pn-other, preserving its retry policy.
Source: pn-other/storage.yaml
State: analysis only; no implementation approved.
See 01-analysis/BRIEF.md.
````

## agents-memories/queue-long-polling/01-analysis/BRIEF.md

````markdown
# Objective
Change VisibilityTimeout on pn-other ProcessingQueue; long polling is unrelated.
# Scope
Only the named component and queue.
# Acceptance
The pn-other visibility timeout is consistent with its existing consumer.
````
