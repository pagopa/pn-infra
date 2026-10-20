# shared-fragment-case-a

Synthetic repository snapshot for read-only evaluation. Paths below are relative to the fixture workspace. Each fenced block contains the complete file contents.

## pn-infra/runtime-infra/fragments/queue.yaml

````yaml
AWSTemplateFormatVersion: '2010-09-09'
Parameters:
  QueueDelaySeconds:
    Type: Number
Resources:
  Queue:
    Type: AWS::SQS::Queue
    Properties:
      DelaySeconds: !Ref QueueDelaySeconds
Outputs:
  QueueArn:
    Value: !GetAtt Queue.Arn
````

## pn-alpha/storage.yaml

````yaml
AWSTemplateFormatVersion: '2010-09-09'
Parameters:
  FragmentUrl:
    Type: String
Resources:
  QueueStack:
    Type: AWS::CloudFormation::Stack
    Properties:
      TemplateURL: !Ref FragmentUrl
      Parameters:
        QueueDelaySeconds: 5
````

## pn-beta/storage.yaml

````yaml
AWSTemplateFormatVersion: '2010-09-09'
Parameters:
  FragmentUrl:
    Type: String
Resources:
  QueueStack:
    Type: AWS::CloudFormation::Stack
    Properties:
      TemplateURL: !Ref FragmentUrl
````

## pn-gamma/storage.yaml

````yaml
AWSTemplateFormatVersion: '2010-09-09'
Parameters:
  FragmentUrl:
    Type: String
Resources:
  QueueStack:
    Type: AWS::CloudFormation::Stack
    Properties:
      TemplateURL: !Ref FragmentUrl
````

## CONTEXT.md

````markdown
# Requested change
The three storage templates use the included queue fragment through FragmentUrl.
Previously the fragment had no parameters and set DelaySeconds to 0.
Only alpha requests a five-second delay. Beta and gamma must retain their existing behavior and remain unchanged.
All resources here are synthetic, disposable test resources. Review only the new parameter contract.
````
