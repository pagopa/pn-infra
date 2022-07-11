
templateBucketHttpsBaseUrl="https://s3.eu-south-1.amazonaws.com/cd-pipeline-cdartifactbucket-up55jiob2cs/pn-infra/47043714abcdafd58bba558b10059905daec4d80/runtime-infra"
aws_param="--region eu-south-1 --profile staging"

echo ""

logsBucketName=$( aws ${aws_param} cloudformation describe-stacks --stack-name pn-ipc-dev \
    | jq -r '.Stacks[0].Outputs | .[] | select(.OutputKey=="LogsBucketName") | .OutputValue' )

logsExporterRoleArn=$( aws ${aws_param} cloudformation describe-stacks --stack-name pn-ipc-dev \
    | jq -r '.Stacks[0].Outputs | .[] | select(.OutputKey=="LogsExporterRoleArn") | .OutputValue' )


echo "LOGS Bucker: ${logsBucketName}"
echo "LOGS Role Arn: ${logsExporterRoleArn}"



echo ""
echo ""

timelineCdcStreamArn=$( aws ${aws_param} cloudformation describe-stacks --stack-name pn-delivery-push-storage-dev \
    | jq -r '.Stacks[0].Outputs | .[] | select(.OutputKey=="TimelineCdcKinesisStreamArn") | .OutputValue' )

timelineCdcSKeyArn=$( aws ${aws_param} cloudformation describe-stacks --stack-name pn-delivery-push-storage-dev \
    | jq -r '.Stacks[0].Outputs | .[] | select(.OutputKey=="TimelineCdcKinesisKeyArn") | .OutputValue' )

echo "Timeline CDC Stream: ${timelineCdcStreamArn}"
echo "Timeline CDC Key: ${timelineCdcSKeyArn}"


aws ${aws_param} cloudformation deploy \
      --stack-name pn-logs-export-dev \
      --capabilities CAPABILITY_NAMED_IAM \
      --template-file runtime-infra/pn-logs-export.yaml \
      --parameter-overrides \
        TemplateBucketBaseUrl="$templateBucketHttpsBaseUrl" \
        ProjectName=pn \
        LogsBucketName="${logsBucketName}" \
        LogsExporterRoleArn="${logsExporterRoleArn}" \
        Version="cd_scripts_commitId=${cd_scripts_commitId},pn_infra_commitId=${pn_infra_commitid}"


# aws ${aws_param} cloudformation deploy \
#       --stack-name pn-logs-export-dev \
#       --capabilities CAPABILITY_NAMED_IAM \
#       --template-file runtime-infra/pn-logs-export.yaml \
#       --parameter-overrides \
#         TemplateBucketBaseUrl="$templateBucketHttpsBaseUrl" \
#         ProjectName=pn \
#         LogsBucketName="${logsBucketName}" \
#         ActivateCloudwatchSubscription="true" \
#         LogsExporterRoleArn="${logsExporterRoleArn}" \
#         Version="cd_scripts_commitId=${cd_scripts_commitId},pn_infra_commitId=${pn_infra_commitid}"



