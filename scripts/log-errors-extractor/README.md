## Check Errors in AWS log-group

## Setup sharing AWS account
This script search, in every log-group of the selected profile,  for particular strings that contains errors. The script generates a file for each log-group and a report file.

The script must be executed in the sharing AWS account:

`./log_errors_extractor.sh [-p <aws-profile>] -r <aws-region>`

where:
- aws-profile is the AWS profile of the sharing account
- aws-region is the AWS region the cloudwatch data are stored into
