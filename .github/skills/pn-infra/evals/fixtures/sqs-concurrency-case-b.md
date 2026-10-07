# sqs-concurrency-case-b

Synthetic repository snapshot for read-only evaluation. Paths below are relative to the fixture workspace. Each fenced block contains the complete file contents.

## consumer.yaml

````yaml
AWSTemplateFormatVersion: '2010-09-09'
Parameters:
  LambdaRoleArn:
    Type: String
  QueueOneArn:
    Type: String
  QueueTwoArn:
    Type: String
Resources:
  Consumer:
    Type: AWS::Lambda::Function
    Properties:
      Role: !Ref LambdaRoleArn
      Runtime: python3.12
      Handler: index.handler
      ReservedConcurrentExecutions: 10
      Code:
        ZipFile: |
          def handler(event, context):
              return {}
  FirstMapping:
    Type: AWS::Lambda::EventSourceMapping
    Properties:
      FunctionName: !Ref Consumer
      EventSourceArn: !Ref QueueOneArn
      ScalingConfig:
        MaximumConcurrency: 8
  SecondMapping:
    Type: AWS::Lambda::EventSourceMapping
    Properties:
      FunctionName: !Ref Consumer
      EventSourceArn: !Ref QueueTwoArn
      ScalingConfig:
        MaximumConcurrency: 8
````

## CONTEXT.md

````markdown
# Capacity contract
Two standard SQS queues can each demand eight concurrent invocations at the same time.
They are the function's only invocation sources. The downstream service supports twenty concurrent calls.
Review the mapping limits against the function reservation. IAM, queue visibility timeouts and business code are outside this focused fixture; do not infer defects from their omission.
````
