# Post SNS notifications from AWS to Slack Bot App 
Follow the steps in this ReadMe to deploy a Slack bot which will receive SNS notifications from AWS CodeBuild, AWS CodePipeline and AWS CloudWatch Alarms and post them to your specified channel, within your workspace.

The Slack bot uses Web API to post messages in your Slack workspace. Authentication for your Web API requests require a bearer token, which identifies the workspace-application relationship. Register your application with Slack to obtain credentials for use with our OAuth 2.0 implementation, which allows you to negotiate tokens on behalf of users and workspaces. https://api.slack.com/web 

## SlackAPI - Post message to channel
1. Create a Slack workspace https://slack.com/help/articles/206845317-Create-a-Slack-workspace
2. Create a new application in Slack with read and write permissions to your workspace. https://api.slack.com/start/building.
3. Once you have created your Slack app, copy the bearer token, starting with a "xoxb" and create a new secret under AWS Secret Manager with the following properties. 
    Secret Name: SlackToken
    Secret Key: SlackToken 
    Secret Value: "bearer token"
4. Copy the ARN of the Secret you have just created.
5. Login in to AWS and upload the State_Change_Notifications.yaml and Message_enrichment.yaml to S3 under the folder /fragments.
6. Deploy the dev.yaml CloudFormation template


## Requirements
1. Install slack_sdk: https://slack.dev/python-slack-sdk/
2. Upload Lamza with dependencies: https://docs.aws.amazon.com/lambda/latest/dg/python-package.html 