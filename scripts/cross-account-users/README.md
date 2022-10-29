# Overview
Those templates aim at providing a dynamic way to allow users in a central account (here, the CICD account) to access other accounts (here, the Dev and Hotfix accounts), with specific permissions. 

The use case is the following: 
- Admin Users, part of specific IAM Groups, in the CICD Account wish to assume AdministratorAccess in the other accounts
- Developers, part of specific IAM Groups, in the CICD Account wish to assume ReadOnlyAccess in the other accounts
- When a new Admin User joins one of the Admin Group, they need to be able to assume the AdministratorAccess in the other accounts
- When a new Developer joins one of the Developer Group, they need to be able to assume the ReadOnlyAccess in the other accounts
- No manual action should be done to operate this cross-account access
- The environments must remain secure and the least privileged principle is to be applied

# Architecture

![image info](./architecture.png)

In this architecture, users are tagged with the tags of the policies attached to the IAM Group they belong to. Proceeding like this allows to only focus on the tags of the policies that allow this cross-account access. 

For example, let's assume we have the following policies:
- Policy A: allows to assume the ReadOnlyAccess role in Dev
- Policy B: allows to assume the AdminAccess role in Dev
- Policy C: allows to assume the AdminAccess role in Hotfix

And the following IAM Groups: 
- Italy Developers: can only assume ReadOnlyAccess in Dev (policy A)
- France Developers: can only assume ReadOnlyAccess in Dev (policy A)
- Spain Developers: can only assume ReadOnlyAccess in Dev (policy A)
- Italy Super Developers: can assume AdminAccess in Dev (policy B)
- France Super Developers: can assume AdminAccess in Dev (policy B)
- Executive Team: can assume AdminAccess in Dev and AdminAccess in Hotfix (policy B and C)

With this architecture, the ReadOnlyAccess role in Dev can be assumed if users bear the tag of the Policy A. That is, the Italy, France and Spain Developers can assume this role in Dev and only by specifying one tag condition in the trust policy.

Overall, here are the main benefits of this architecture:
- We only have to define in the trust policy of the roles in Dev/Hotfix the tag which allows access (i.e. a tag from the policy A/B/C)
- Whenever a user is added to an IAM Group, it will bear the tags of the policies attached to the group, giving them cross-account access. Reversely, if a user is removed, the user will be untagged. 
- Whenever a policy is attached to an IAM Group, the users in the group will bear the tags of the policy, giving them cross account access. Reversely, if a policy is detached, the users will be untagged. 

Remark: if users already belong to their IAM Group and Policies are already attached to the IAM Groups before deploying these templates, it will not work. One will need to either:
- Remove IAM Users and add them back to their IAM Group 
- OR detach the IAM policies and attach them back to the IAM Groups


# How to deploy

1. Make sure you have AWS Credentials profiles for the CICD, Dev and HotFix accounts. If not, follow the instructions here: https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-profiles.html

2. Launch the bash script with the following parameters:
- REGION: region to deploy the templates in
- CICD_PROFILE: name of the profile for the CICD account
- DEV_PROFILES: list of profile names for the DEV account
- HOTFIX_PROFILES: list of profile names for the HOTFIX account

```
./bash-script.sh REGION=us-east-1 CICD_PROFILE=my-cicd-profile DEV_PROFILES="my-dev-profile1, my-dev-profile2, my-dev-profile3" HOTFIX_PROFILES=my-hotfix-profile1, my-hotfix-profile2, my-hotfix-profile3
```


# Detailed Steps

This section details the steps in the bash script. 

Note: `cross-account-roles.yaml` and `hotfix-account-X.yaml` are identical (except for the description)

1. Deploy `cross-account-roles.yaml`. It creates an AdministratorAccess role and a ReadOnly role that are to be assumed by specific groups in the CICD account. 

```
  aws --profile $profile --region $region cloudformation deploy \
    --stack-name ${stackName} \
    --template-file ${scriptDir}/cnf-templates/${templateFile} \
    --capabilities CAPABILITY_NAMED_IAM \
    --parameter-override $@ \
    TrustedAccountId=$cicdAccount
    Environment=${account}

```

2. Note down the ARN of `RoleAdministratorAccess` and `RoleReadOnlyAccess` of both accounts. The CICD Account will create policies that will allow to assume those roles. 

3. Deploy `cicd-account.yaml`. It deploys the IAM policies that are to be attached to IAM Groups, allowing a specific group to assume a specific role in the Dev and Hotfix accounts. It also creates the Lambda function and the event bridge rule that will trigger it. 

```
aws cloudformation deploy \
--stack-name cross-account-1-cicd \
--template-file ./cf-templates/cicd-account-1.yaml \
--capabilities CAPABILITY_NAMED_IAM \
--parameter-overrides \
--profile $CICD_PROFILE \
--region $REGION
```

4. Since the IAM events are only registered in the us-east-1 region, in case you need to deploy the lambdas in a different region, we need to redirect these events to the specified region in the situation where $REGION is not us-east-1. Note down the ARN of the default event bus in $REGION and input it as parameter. 

```
aws cloudformation deploy \
--stack-name cross-account-event-routing \
--template-file ./cf-templates/cicd-account-event-routing.yaml \
--capabilities CAPABILITY_NAMED_IAM \
--parameter-overrides \
CrossRegionDestinationBus=$EventBus_ARN \
--profile $CICD_PROFILE \
--region us-east-1
```