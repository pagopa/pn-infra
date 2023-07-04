# Cross account Cloudwatch

## Setup sharing AWS account
This scripts enables an AWS account to share cloudwatch data with other AWS accounts.

The script must be executed in the sharing AWS account:

`./setup-cloudwatch-shared-account.sh [-p <aws-profile>] -r <aws-region> -e <env-type> -a <monitoring-aws-accounts>`

where:
- aws-profile is the AWS profile of the sharing account (optional)
- aws-region is the AWS region the cloudwatch data are stored into
- env-type is the PN environment (svil, dev, hotfix ...)
- monitoring-aws-accounts is the comma separated list of the cloudwatch sharing target AWS account IDs (also called monitoring accounts)

## Setup monitoring AWS account

This operation can only be performed from the AWS Cloudwatch console of the monitoring AWS account.

You can follow the procedure described at [this link](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/Cross-Account-Cross-Region.html#enable-cross-account-cross-Region) at _Set up a monitoring account_ section.