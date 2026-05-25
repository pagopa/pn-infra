# AWS Resource Inventory

Scans all AWS resources in **eu-south-1** and **eu-central-1**, categorizes them, and generates a CSV report.

## Prerequisites

- Python 3.9+
- AWS CLI v2 with SSO configured (`~/.aws/config`)

## Installation

It is recommended to use a virtual environment:

```bash
cd scripts/aws-resource-inventory

# Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate          # macOS / Linux
# .venv\Scripts\activate           # Windows

# Install dependencies
pip install -r requirements.txt
```

## Authentication

Log in with your AWS SSO profile before running the script:

```bash
aws sso login --profile <your-profile>
```

## Usage

```bash
python aws_resource_inventory.py --profile <sso-profile-name>

# Custom output file
python aws_resource_inventory.py --profile <sso-profile-name> --output my_report.csv
```

## CSV columns

| Column | Description |
|---|---|
| `category` | High-level category (Compute, Storage, Network, Security, Messaging, Monitoring, Management, DevOps, Other) |
| `region` | AWS region where the resource lives |
| `resource_type` | `service:type` derived from the ARN (e.g. `ec2:instance`) |
| `resource_name` | Human-readable name (from `Name` tag or ARN suffix) |
| `arn` | Full Amazon Resource Name |

## Categories

| Category | Example resource types |
|---|---|
| Compute | EC2 instances, Lambda, ECS, EKS, Auto Scaling Groups |
| Storage | S3 buckets, DynamoDB tables, RDS, ElastiCache, EBS, EFS |
| Network | VPCs, Subnets, Security Groups, ELB, API Gateway, CloudFront |
| Security | IAM roles/policies, KMS keys, Secrets Manager, ACM, WAF |
| Messaging | SNS topics, SQS queues, EventBridge rules, Kinesis streams |
| Monitoring | CloudWatch alarms, Log Groups, CloudTrail trails |
| Management | CloudFormation stacks, SSM parameters, Config rules |
| DevOps | ECR repositories, CodeBuild projects, CodePipeline |

## How it works

1. **Resource Groups Tagging API** (`resourcegroupstaggingapi`) — primary sweep for tagged resources.
2. **Service-specific APIs** — supplements the tagging sweep to catch untagged resources:
   - EC2 (VPCs, subnets, security groups, IGWs, NAT GWs, route tables, volumes)
   - Lambda, RDS, DynamoDB, ELBv2, SQS, SNS, CloudFormation, KMS, Secrets Manager, ACM, ECR
3. Results are **deduplicated by ARN** before writing the report.
