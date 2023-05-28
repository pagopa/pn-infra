## DEPLOY EFS WITH TERRAFORM:

The scripts deploy a EFS filesystem in a specific accounts with the following information:

- vpc_id (example: vpc-78.....)
- security_group (example: sg-0c2.....)

USAGE:

1 - export  AWS_PROFILE=${AWS_ACCOUNT} variable in your client environment
2 - execute terraform init
3 - execute terraform apply
4 - insert security_group_id where to attach EFS
5 - insert vpc_id  where to attach EFS
