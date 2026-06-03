#!/usr/bin/env python3
"""
AWS Resource Inventory Script

Scans AWS resources in eu-south-1 and eu-central-1, categorizes them by type,
and generates a CSV report.

Usage:
    python aws_resource_inventory.py --profile <sso-profile-name> [--output report.csv]

Requirements:
    pip install boto3
"""

import argparse
import csv
import sys
from datetime import datetime
from typing import Optional

import boto3
from botocore.exceptions import ClientError, NoCredentialsError

REGIONS = ["eu-south-1", "eu-central-1"]

# ---------------------------------------------------------------------------
# Resource types to exclude from the inventory (lowercase "service:type")
# ---------------------------------------------------------------------------
EXCLUDED_RESOURCE_TYPES: set[str] = {
    "batch:job-definition",
    "ecs:task-definition",
    "ecs:task",
    "glue:session",
    "ssm:session",
    "cloudformation:stack",
    "backup:recovery-point",
    "ssm:opsitem"
}

# ---------------------------------------------------------------------------
# Category mapping  (service:resource-type  ->  category)
# ---------------------------------------------------------------------------
RESOURCE_CATEGORIES: dict[str, str] = {
    # Compute
    "ec2:instance": "Compute",
    "ec2:spot-instances-request": "Compute",
    "ec2:launch-template": "Compute",
    "ec2:image": "Compute",
    "lambda:function": "Compute",
    "ecs:cluster": "Compute",
    "ecs:service": "Compute",
    "ecs:task": "Compute",
    "ecs:task-definition": "Compute",
    "eks:cluster": "Compute",
    "eks:nodegroup": "Compute",
    "autoscaling:autoScalingGroup": "Compute",
    "autoscaling:launchConfiguration": "Compute",
    "batch:compute-environment": "Compute",
    "batch:job-definition": "Compute",
    "batch:job-queue": "Compute",
    "elasticbeanstalk:application": "Compute",
    "elasticbeanstalk:environment": "Compute",
    # Storage
    "s3:bucket": "Storage",
    "dynamodb:table": "Storage",
    "rds:db": "Storage",
    "rds:cluster": "Storage",
    "rds:snapshot": "Storage",
    "rds:cluster-snapshot": "Storage",
    "elasticache:cluster": "Storage",
    "elasticache:replication-group": "Storage",
    "ec2:volume": "Storage",
    "ec2:snapshot": "Storage",
    "efs:file-system": "Storage",
    "backup:backup-vault": "Storage",
    "backup:backup-plan": "Storage",
    "glacier:vaults": "Storage",
    "opensearch:domain": "Storage",
    "es:domain": "Storage",
    "redshift:cluster": "Storage",
    "dax:cluster": "Storage",
    # Network
    "ec2:vpc": "Network",
    "ec2:subnet": "Network",
    "ec2:security-group": "Network",
    "ec2:route-table": "Network",
    "ec2:internet-gateway": "Network",
    "ec2:nat-gateway": "Network",
    "ec2:network-acl": "Network",
    "ec2:vpn-gateway": "Network",
    "ec2:vpn-connection": "Network",
    "ec2:vpc-peering-connection": "Network",
    "ec2:transit-gateway": "Network",
    "ec2:transit-gateway-attachment": "Network",
    "ec2:network-interface": "Network",
    "ec2:elastic-ip": "Network",
    "ec2:vpc-endpoint": "Network",
    "ec2:vpc-endpoint-service": "Network",
    "elasticloadbalancing:loadbalancer": "Network",
    "elasticloadbalancing:targetgroup": "Network",
    "cloudfront:distribution": "Network",
    "route53:hostedzone": "Network",
    "route53resolver:resolver-endpoint": "Network",
    "apigateway:restapis": "Network",
    "apigateway:apis": "Network",
    "apigatewayv2:apis": "Network",
    "globalaccelerator:accelerator": "Network",
    # Security
    "iam:role": "Security",
    "iam:policy": "Security",
    "iam:user": "Security",
    "iam:group": "Security",
    "kms:key": "Security",
    "secretsmanager:secret": "Security",
    "acm:certificate": "Security",
    "wafv2:webacl": "Security",
    "waf:webacl": "Security",
    "waf-regional:webacl": "Security",
    "shield:protection": "Security",
    "guardduty:detector": "Security",
    "securityhub:hub": "Security",
    "cognito-idp:userpool": "Security",
    "cognito-identity:identitypool": "Security",
    # Messaging / Integration
    "sns:topic": "Messaging",
    "sqs:queue": "Messaging",
    "events:rule": "Messaging",
    "events:event-bus": "Messaging",
    "kinesis:stream": "Messaging",
    "firehose:deliverystream": "Messaging",
    "mq:broker": "Messaging",
    "kafka:cluster": "Messaging",
    # Monitoring / Observability
    "cloudwatch:alarm": "Monitoring",
    "cloudwatch:dashboard": "Monitoring",
    "logs:log-group": "Monitoring",
    "cloudtrail:trail": "Monitoring",
    "xray:group": "Monitoring",
    "synthetics:canary": "Monitoring",
    # Management / Automation
    "cloudformation:stack": "Management",
    "ssm:document": "Management",
    "ssm:parameter": "Management",
    "config:config-rule": "Management",
    "servicecatalog:portfolio": "Management",
    # DevOps / CI-CD
    "codecommit:repository": "DevOps",
    "codebuild:project": "DevOps",
    "codedeploy:application": "DevOps",
    "codepipeline:pipeline": "DevOps",
    "ecr:repository": "DevOps",
}

# Prefix-based fallback (service -> category) when exact match is not found
SERVICE_CATEGORY_FALLBACK: dict[str, str] = {
    "ec2": "Compute",
    "lambda": "Compute",
    "ecs": "Compute",
    "eks": "Compute",
    "autoscaling": "Compute",
    "batch": "Compute",
    "s3": "Storage",
    "rds": "Storage",
    "dynamodb": "Storage",
    "elasticache": "Storage",
    "efs": "Storage",
    "backup": "Storage",
    "redshift": "Storage",
    "opensearch": "Storage",
    "es": "Storage",
    "dax": "Storage",
    "elasticloadbalancing": "Network",
    "route53": "Network",
    "route53resolver": "Network",
    "apigateway": "Network",
    "apigatewayv2": "Network",
    "cloudfront": "Network",
    "globalaccelerator": "Network",
    "iam": "Security",
    "kms": "Security",
    "secretsmanager": "Security",
    "acm": "Security",
    "wafv2": "Security",
    "cognito-idp": "Security",
    "cognito-identity": "Security",
    "guardduty": "Security",
    "securityhub": "Security",
    "shield": "Security",
    "sns": "Messaging",
    "sqs": "Messaging",
    "events": "Messaging",
    "kinesis": "Messaging",
    "firehose": "Messaging",
    "mq": "Messaging",
    "cloudwatch": "Monitoring",
    "logs": "Monitoring",
    "cloudtrail": "Monitoring",
    "xray": "Monitoring",
    "cloudformation": "Management",
    "ssm": "Management",
    "config": "Management",
    "codecommit": "DevOps",
    "codebuild": "DevOps",
    "codedeploy": "DevOps",
    "codepipeline": "DevOps",
    "ecr": "DevOps",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_category(resource_type: str) -> str:
    """Return the category for a given 'service:type' resource_type string."""
    rt_lower = resource_type.lower()
    # Exact match
    for key, cat in RESOURCE_CATEGORIES.items():
        if rt_lower == key.lower():
            return cat
    # Prefix match on service
    service = rt_lower.split(":")[0]
    return SERVICE_CATEGORY_FALLBACK.get(service, "Other")


def extract_resource_type_from_arn(arn: str) -> str:
    """
    Parse service and resource-type from an ARN.

    ARN format:  arn:partition:service:region:account:resource
    'resource' may be:  resource-id | resource-type/resource-id | resource-type:resource-id
    """
    parts = arn.split(":")
    if len(parts) < 6:
        return "unknown"

    service = parts[2]
    resource_part = ":".join(parts[5:])  # everything after account-id

    if "/" in resource_part:
        resource_type = resource_part.split("/")[0]
    elif len(parts) > 6:
        # e.g. arn:aws:sqs:region:account:queue-name  (no slash, no extra colon)
        resource_type = parts[5]
    else:
        resource_type = resource_part

    return f"{service}:{resource_type}"


def extract_name_from_arn(arn: str) -> str:
    """Best-effort extraction of a human-readable name from an ARN."""
    parts = arn.split(":")
    if len(parts) < 6:
        return arn
    resource_part = ":".join(parts[5:])
    if "/" in resource_part:
        return resource_part.split("/")[-1]
    return resource_part.split(":")[-1]


def extract_region_from_arn(arn: str) -> str:
    parts = arn.split(":")
    return parts[3] if len(parts) > 3 else ""


def build_record(arn: str, tags: dict, region: Optional[str] = None) -> Optional[dict]:
    resource_type = extract_resource_type_from_arn(arn)
    if resource_type.lower() in EXCLUDED_RESOURCE_TYPES:
        return None
    name = tags.get("Name") or tags.get("name") or extract_name_from_arn(arn)
    resolved_region = region or extract_region_from_arn(arn) or "global"
    return {
        "category": get_category(resource_type),
        "region": resolved_region,
        "resource_type": resource_type,
        "resource_name": name,
        "arn": arn,
    }


# ---------------------------------------------------------------------------
# Scanners
# ---------------------------------------------------------------------------

def scan_tagged_resources(session: boto3.Session, region: str) -> list[dict]:
    """Fetch all tagged resources via Resource Groups Tagging API."""
    client = session.client("resourcegroupstaggingapi", region_name=region)
    results: list[dict] = []
    paginator = client.get_paginator("get_resources")
    try:
        for page in paginator.paginate(ResourcesPerPage=100):
            for resource in page.get("ResourceTagMappingList", []):
                arn = resource.get("ResourceARN", "")
                tags = {t["Key"]: t["Value"] for t in resource.get("Tags", [])}
                results.append(build_record(arn, tags, region=region))
    except ClientError as exc:
        print(f"  [WARN] resourcegroupstaggingapi in {region}: {exc}", file=sys.stderr)
    return results


def scan_ec2_untagged(session: boto3.Session, region: str) -> list[dict]:
    """Supplement tagging API with common EC2 resources (including untagged)."""
    ec2 = session.client("ec2", region_name=region)
    results: list[dict] = []
    account_id = session.client("sts").get_caller_identity()["Account"]
    partition = "aws"

    def name_from_tags(tags_list: list) -> str:
        for t in (tags_list or []):
            if t.get("Key") == "Name":
                return t["Value"]
        return ""

    # VPCs
    try:
        for vpc in ec2.describe_vpcs()["Vpcs"]:
            arn = f"arn:{partition}:ec2:{region}:{account_id}:vpc/{vpc['VpcId']}"
            results.append(build_record(arn, {}, region=region))
    except ClientError:
        pass

    # Subnets
    try:
        paginator = ec2.get_paginator("describe_subnets")
        for page in paginator.paginate():
            for subnet in page["Subnets"]:
                arn = f"arn:{partition}:ec2:{region}:{account_id}:subnet/{subnet['SubnetId']}"
                tags = {"Name": name_from_tags(subnet.get("Tags", []))}
                results.append(build_record(arn, tags, region=region))
    except ClientError:
        pass

    # Security Groups
    try:
        paginator = ec2.get_paginator("describe_security_groups")
        for page in paginator.paginate():
            for sg in page["SecurityGroups"]:
                arn = f"arn:{partition}:ec2:{region}:{account_id}:security-group/{sg['GroupId']}"
                tags = {"Name": name_from_tags(sg.get("Tags", [])) or sg.get("GroupName", "")}
                results.append(build_record(arn, tags, region=region))
    except ClientError:
        pass

    # Internet Gateways
    try:
        for igw in ec2.describe_internet_gateways()["InternetGateways"]:
            arn = f"arn:{partition}:ec2:{region}:{account_id}:internet-gateway/{igw['InternetGatewayId']}"
            tags = {"Name": name_from_tags(igw.get("Tags", []))}
            results.append(build_record(arn, tags, region=region))
    except ClientError:
        pass

    # NAT Gateways
    try:
        paginator = ec2.get_paginator("describe_nat_gateways")
        for page in paginator.paginate():
            for ngw in page["NatGateways"]:
                arn = f"arn:{partition}:ec2:{region}:{account_id}:nat-gateway/{ngw['NatGatewayId']}"
                tags = {"Name": name_from_tags(ngw.get("Tags", []))}
                results.append(build_record(arn, tags, region=region))
    except ClientError:
        pass

    # Route Tables
    try:
        paginator = ec2.get_paginator("describe_route_tables")
        for page in paginator.paginate():
            for rt in page["RouteTables"]:
                arn = f"arn:{partition}:ec2:{region}:{account_id}:route-table/{rt['RouteTableId']}"
                tags = {"Name": name_from_tags(rt.get("Tags", []))}
                results.append(build_record(arn, tags, region=region))
    except ClientError:
        pass

    # EBS Volumes
    try:
        paginator = ec2.get_paginator("describe_volumes")
        for page in paginator.paginate():
            for vol in page["Volumes"]:
                arn = f"arn:{partition}:ec2:{region}:{account_id}:volume/{vol['VolumeId']}"
                tags = {"Name": name_from_tags(vol.get("Tags", []))}
                results.append(build_record(arn, tags, region=region))
    except ClientError:
        pass

    return results


def scan_s3_buckets(session: boto3.Session) -> list[dict]:
    """List all S3 buckets (global but scoped to this account)."""
    s3 = session.client("s3", region_name="eu-south-1")
    results: list[dict] = []
    account_id = session.client("sts").get_caller_identity()["Account"]
    try:
        buckets = s3.list_buckets().get("Buckets", [])
        for bucket in buckets:
            name = bucket["Name"]
            arn = f"arn:aws:s3:::{name}"
            # Resolve bucket region
            try:
                loc = s3.get_bucket_location(Bucket=name).get("LocationConstraint") or "us-east-1"
            except ClientError:
                loc = "unknown"
            results.append(build_record(arn, {"Name": name}, region=loc))
    except ClientError as exc:
        print(f"  [WARN] S3 list_buckets: {exc}", file=sys.stderr)
    return results


def scan_rds(session: boto3.Session, region: str) -> list[dict]:
    """Scan RDS instances and clusters."""
    rds = session.client("rds", region_name=region)
    results: list[dict] = []
    try:
        paginator = rds.get_paginator("describe_db_instances")
        for page in paginator.paginate():
            for db in page["DBInstances"]:
                arn = db["DBInstanceArn"]
                results.append(build_record(arn, {"Name": db["DBInstanceIdentifier"]}, region=region))
    except ClientError:
        pass
    try:
        paginator = rds.get_paginator("describe_db_clusters")
        for page in paginator.paginate():
            for cluster in page["DBClusters"]:
                arn = cluster["DBClusterArn"]
                results.append(build_record(arn, {"Name": cluster["DBClusterIdentifier"]}, region=region))
    except ClientError:
        pass
    return results


def scan_lambda(session: boto3.Session, region: str) -> list[dict]:
    """Scan Lambda functions."""
    client = session.client("lambda", region_name=region)
    results: list[dict] = []
    paginator = client.get_paginator("list_functions")
    try:
        for page in paginator.paginate():
            for fn in page["Functions"]:
                arn = fn["FunctionArn"]
                results.append(build_record(arn, {"Name": fn["FunctionName"]}, region=region))
    except ClientError as exc:
        print(f"  [WARN] lambda list_functions in {region}: {exc}", file=sys.stderr)
    return results


def scan_elbv2(session: boto3.Session, region: str) -> list[dict]:
    """Scan ELBv2 load balancers and target groups."""
    client = session.client("elbv2", region_name=region)
    results: list[dict] = []
    try:
        paginator = client.get_paginator("describe_load_balancers")
        for page in paginator.paginate():
            for lb in page["LoadBalancers"]:
                arn = lb["LoadBalancerArn"]
                results.append(build_record(arn, {"Name": lb["LoadBalancerName"]}, region=region))
    except ClientError:
        pass
    try:
        paginator = client.get_paginator("describe_target_groups")
        for page in paginator.paginate():
            for tg in page["TargetGroups"]:
                arn = tg["TargetGroupArn"]
                results.append(build_record(arn, {"Name": tg["TargetGroupName"]}, region=region))
    except ClientError:
        pass
    return results


def scan_sqs(session: boto3.Session, region: str) -> list[dict]:
    """Scan SQS queues."""
    client = session.client("sqs", region_name=region)
    results: list[dict] = []
    paginator = client.get_paginator("list_queues")
    try:
        for page in paginator.paginate():
            for url in page.get("QueueUrls", []):
                # Derive ARN from queue URL: https://sqs.region.amazonaws.com/account/name
                parts = url.rstrip("/").split("/")
                if len(parts) >= 2:
                    account_id = parts[-2]
                    queue_name = parts[-1]
                    arn = f"arn:aws:sqs:{region}:{account_id}:{queue_name}"
                    results.append(build_record(arn, {"Name": queue_name}, region=region))
    except ClientError as exc:
        print(f"  [WARN] sqs list_queues in {region}: {exc}", file=sys.stderr)
    return results


def scan_sns(session: boto3.Session, region: str) -> list[dict]:
    """Scan SNS topics."""
    client = session.client("sns", region_name=region)
    results: list[dict] = []
    paginator = client.get_paginator("list_topics")
    try:
        for page in paginator.paginate():
            for topic in page["Topics"]:
                arn = topic["TopicArn"]
                results.append(build_record(arn, {}, region=region))
    except ClientError as exc:
        print(f"  [WARN] sns list_topics in {region}: {exc}", file=sys.stderr)
    return results


def scan_dynamodb(session: boto3.Session, region: str) -> list[dict]:
    """Scan DynamoDB tables."""
    client = session.client("dynamodb", region_name=region)
    results: list[dict] = []
    account_id = session.client("sts").get_caller_identity()["Account"]
    paginator = client.get_paginator("list_tables")
    try:
        for page in paginator.paginate():
            for table_name in page["TableNames"]:
                arn = f"arn:aws:dynamodb:{region}:{account_id}:table/{table_name}"
                results.append(build_record(arn, {"Name": table_name}, region=region))
    except ClientError as exc:
        print(f"  [WARN] dynamodb list_tables in {region}: {exc}", file=sys.stderr)
    return results


def scan_cloudformation(session: boto3.Session, region: str) -> list[dict]:
    """Scan CloudFormation stacks."""
    client = session.client("cloudformation", region_name=region)
    results: list[dict] = []
    paginator = client.get_paginator("list_stacks")
    active_statuses = [
        "CREATE_COMPLETE", "UPDATE_COMPLETE", "ROLLBACK_COMPLETE",
        "UPDATE_ROLLBACK_COMPLETE", "IMPORT_COMPLETE",
    ]
    try:
        for page in paginator.paginate(StackStatusFilter=active_statuses):
            for stack in page["StackSummaries"]:
                arn = stack.get("StackId", "")
                name = stack.get("StackName", "")
                results.append(build_record(arn, {"Name": name}, region=region))
    except ClientError as exc:
        print(f"  [WARN] cloudformation list_stacks in {region}: {exc}", file=sys.stderr)
    return results


def scan_kms(session: boto3.Session, region: str) -> list[dict]:
    """Scan customer-managed KMS keys."""
    client = session.client("kms", region_name=region)
    results: list[dict] = []
    paginator = client.get_paginator("list_keys")
    try:
        for page in paginator.paginate():
            for key in page["Keys"]:
                key_id = key["KeyId"]
                arn = key["KeyArn"]
                try:
                    meta = client.describe_key(KeyId=key_id)["KeyMetadata"]
                    if meta.get("KeyManager") != "CUSTOMER":
                        continue
                    alias = meta.get("Description", key_id)
                except ClientError:
                    alias = key_id
                results.append(build_record(arn, {"Name": alias}, region=region))
    except ClientError as exc:
        print(f"  [WARN] kms list_keys in {region}: {exc}", file=sys.stderr)
    return results


def scan_secretsmanager(session: boto3.Session, region: str) -> list[dict]:
    """Scan Secrets Manager secrets."""
    client = session.client("secretsmanager", region_name=region)
    results: list[dict] = []
    paginator = client.get_paginator("list_secrets")
    try:
        for page in paginator.paginate():
            for secret in page["SecretList"]:
                arn = secret["ARN"]
                name = secret["Name"]
                results.append(build_record(arn, {"Name": name}, region=region))
    except ClientError as exc:
        print(f"  [WARN] secretsmanager in {region}: {exc}", file=sys.stderr)
    return results


def scan_acm(session: boto3.Session, region: str) -> list[dict]:
    """Scan ACM certificates."""
    client = session.client("acm", region_name=region)
    results: list[dict] = []
    paginator = client.get_paginator("list_certificates")
    try:
        for page in paginator.paginate():
            for cert in page["CertificateSummaryList"]:
                arn = cert["CertificateArn"]
                name = cert.get("DomainName", extract_name_from_arn(arn))
                results.append(build_record(arn, {"Name": name}, region=region))
    except ClientError as exc:
        print(f"  [WARN] acm in {region}: {exc}", file=sys.stderr)
    return results


def scan_ecr(session: boto3.Session, region: str) -> list[dict]:
    """Scan ECR repositories."""
    client = session.client("ecr", region_name=region)
    results: list[dict] = []
    paginator = client.get_paginator("describe_repositories")
    try:
        for page in paginator.paginate():
            for repo in page["repositories"]:
                arn = repo["repositoryArn"]
                name = repo["repositoryName"]
                results.append(build_record(arn, {"Name": name}, region=region))
    except ClientError as exc:
        print(f"  [WARN] ecr in {region}: {exc}", file=sys.stderr)
    return results


# ---------------------------------------------------------------------------
# Main orchestration
# ---------------------------------------------------------------------------

def collect_all_resources(profile: str) -> list[dict]:
    """Run all scanners and return deduplicated list of resource records."""
    print(f"Authenticating with AWS SSO profile: {profile}")
    try:
        session = boto3.Session(profile_name=profile)
        sts = session.client("sts")
        identity = sts.get_caller_identity()
        print(f"  Account : {identity['Account']}")
        print(f"  UserID  : {identity['UserId']}")
    except NoCredentialsError:
        print("ERROR: No credentials found. Run `aws sso login --profile <profile>` first.", file=sys.stderr)
        sys.exit(1)
    except ClientError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    all_records: dict[str, dict] = {}  # keyed by ARN to deduplicate

    def merge(records: list[dict]) -> None:
        for r in records:
            if r is None:
                continue
            arn = r["arn"]
            if arn and arn not in all_records:
                all_records[arn] = r

    # S3 is global – scan once
    print("\nScanning S3 (global)...")
    merge(scan_s3_buckets(session))

    for region in REGIONS:
        print(f"\nScanning region: {region}")

        print(f"  [1/12] Resource Groups Tagging API (tagged resources)...")
        merge(scan_tagged_resources(session, region))

        print(f"  [2/12] EC2 core resources (VPCs, Subnets, SGs, IGWs, NAT GWs, Routes, Volumes)...")
        merge(scan_ec2_untagged(session, region))

        print(f"  [3/12] Lambda functions...")
        merge(scan_lambda(session, region))

        print(f"  [4/12] RDS instances and clusters...")
        merge(scan_rds(session, region))

        print(f"  [5/12] DynamoDB tables...")
        merge(scan_dynamodb(session, region))

        print(f"  [6/12] ELBv2 load balancers and target groups...")
        merge(scan_elbv2(session, region))

        print(f"  [7/12] SQS queues...")
        merge(scan_sqs(session, region))

        print(f"  [8/12] SNS topics...")
        merge(scan_sns(session, region))

        print(f"  [9/12] CloudFormation stacks...")
        merge(scan_cloudformation(session, region))

        print(f"  [10/12] KMS customer-managed keys...")
        merge(scan_kms(session, region))

        print(f"  [11/12] Secrets Manager secrets...")
        merge(scan_secretsmanager(session, region))

        print(f"  [12/12] ACM certificates + ECR repositories...")
        merge(scan_acm(session, region))
        merge(scan_ecr(session, region))

    return list(all_records.values())


def write_csv(records: list[dict], output_path: str) -> None:
    """Write records to a CSV file."""
    fieldnames = ["category", "region", "resource_type", "resource_name", "arn"]
    # Sort: category, region, resource_type, resource_name
    records_sorted = sorted(records, key=lambda r: (r["category"], r["region"], r["resource_type"], r["resource_name"]))
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records_sorted)


def print_summary(records: list[dict]) -> None:
    from collections import Counter
    cat_counts = Counter(r["category"] for r in records)
    region_counts = Counter(r["region"] for r in records)
    print("\n=== Summary ===")
    print(f"Total resources: {len(records)}")
    print("\nBy category:")
    for cat, count in sorted(cat_counts.items()):
        print(f"  {cat:<15} {count:>5}")
    print("\nBy region:")
    for region, count in sorted(region_counts.items()):
        print(f"  {region:<20} {count:>5}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate an AWS resource inventory CSV for eu-south-1 and eu-central-1."
    )
    parser.add_argument(
        "--profile", "-p",
        required=True,
        help="AWS SSO profile name (from ~/.aws/config)",
    )
    parser.add_argument(
        "--output", "-o",
        default=f"aws_inventory_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        help="Output CSV file path (default: aws_inventory_<timestamp>.csv)",
    )
    args = parser.parse_args()

    records = collect_all_resources(args.profile)
    write_csv(records, args.output)
    print_summary(records)
    print(f"\nReport written to: {args.output}")


if __name__ == "__main__":
    main()
