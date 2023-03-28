## Get Metric in AWS:

This script gets metrics in json. The script generates a file for each metric.

The script must be executed in the sharing AWS account:

`./get_test_metrics.sh [-p <aws-profile>] -r <aws-region> -s <start-time> -e <end-time> [-P <period>]`

where:
- aws-profile is the AWS profile of the sharing account
- aws-region is the AWS region the cloudwatch data are stored into
- start-time is the time to start the export with the following format: YYYY-MM-DDTHH:MM:SSZ (es. 2023-03-23T20:00:00Z)
- end-time is the time to end the export with the following format: YYYY-MM-DDTHH:MM:SSZ (es. 2023-03-23T20:00:00Z)
- period is the time between data points (optional, default is 60s)
