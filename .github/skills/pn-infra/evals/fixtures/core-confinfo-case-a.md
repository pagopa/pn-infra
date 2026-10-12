# core-confinfo-case-a

Synthetic repository snapshot for read-only evaluation. Paths below are relative to the fixture workspace. Each fenced block contains the complete file contents.

## shared.yaml

````yaml
AWSTemplateFormatVersion: '2010-09-09'
Parameters:
  Domain:
    Type: String
    AllowedValues: [CORE, CONFINFO]
  CoreTopicArn:
    Type: String
Conditions:
  IsCore: !Equals [!Ref Domain, CORE]
Resources:
  Subscription:
    Type: AWS::SNS::Subscription
    Condition: IsCore
    Properties:
      TopicArn: !Ref CoreTopicArn
      Protocol: email
      Endpoint: notifications@example.invalid
````

## core-parameters.json

````json
[
  {
    "ParameterKey": "Domain",
    "ParameterValue": "CORE"
  },
  {
    "ParameterKey": "CoreTopicArn",
    "ParameterValue": "arn:aws:sns:eu-south-1:111111111111:pn-example"
  }
]
````

## confinfo-parameters.json

````json
[
  {
    "ParameterKey": "Domain",
    "ParameterValue": "CONFINFO"
  }
]
````

## CONTEXT.md

````markdown
# Shared template
Both parameter files are complete inputs to fresh stack creation using shared.yaml.
Only CORE creates a subscription. CONFINFO must continue working without a topic parameter.
The account ID and email are synthetic. Review parameter requiredness and the Condition; do not deploy.
````
