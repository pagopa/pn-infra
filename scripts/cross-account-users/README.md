# Overview
Those templates aim at providing a dynamic way to allow users in a central account (here, the CICD account) to access other accounts (here, the Dev and Hotfix accounts), with specific permissions. 

The use case is the following: 
- Admin Users, part of a specific IAM Group, in the central account wish to assume AdministratorAccess in the other accounts
- Developers, part of a specific IAM Group, in the central account wish to assume ReadOnlyAccess in the other accounts
- When a new Admin User joins the Admin Group, they need to be able to assume the AdministratorAccess in the other accounts
- When a new Developer joins the Developer Group, they need to be able to assume the ReadOnlyAccess in the other accounts
-  No manual action should be done to operate this cross-account access
- The environments must remain secure and the least privileged principle is to be applied

# Architecture

![image info](./architecture.png)

With this architecture, every time a user is added to a group, the EventBridge rule triggers the Lambda function. Depending on the group the user was added to, the trust policy of a specific role is updated in the Dev or HotFix accounts. To know which group maps to which role, there is a `MAPPING_GROUP_TO_ROLE_IAM` variable in the Lambda Function. Reversly, if a user is removed from a group, the trust policy is also updated to stop allowing the user to assume the role. 

# How to deploy

1. Make sure you have AWS Credentials profiles for the CICD, Dev and HotFix accounts. If not, follow the instructions here: https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-profiles.html

2. Launch the bash script with the following parameters:
- REGION: region to deploy the templates in
- CICD_PROFILE: name of the profile for the CICD account
- DEV_PROFILE: name of the profile for the DEV account
- HOTFIX_PROFILE: name of the profile for the HOTFIX account

```
./bash-script.sh REGION=us-east-1 CICD_PROFILE=my-cicd-profile DEV_PROFILE=my-dev-profile HOTFIX_PROFILE=my-hotfix-profile
```


# Detailed Steps

This section details the steps in the bash script. 

Note: `dev-account-X.yaml` and `hotfix-account-X.yaml` are identical (except for the description)

1. Deploy `dev-account-1.yaml` and `hotfix-account-1.yaml`. They create an AdministratorAccess role and a ReadOnly role that are to be assumed by specific groups in the CICD account. 

```
aws cloudformation deploy \
--stack-name cross-account-1-dev \
--template-file ./cf-templates/dev-account-1.yaml \
--capabilities CAPABILITY_NAMED_IAM \
--profile $DEV_PROFILE \
--region $REGION
```

```
aws cloudformation deploy \
--stack-name cross-account-1-hotfix \
--template-file ./cf-templates/hotfix-account-1.yaml \
--capabilities CAPABILITY_NAMED_IAM \
--profile $HOTFIX_PROFILE \
--region $REGION
```

2. Note down the ARN of `RoleAdministratorAccess` and `RoleReadOnlyAccess` of both accounts. The CICD Account will create policies that will allow to assume those roles. 

3. Deploy `cicd-account-1.yaml`. It deploys the IAM policies that are to be attached to IAM Groups, allowing a specific group to assume a specific role in the Dev and Hotfix accounts. It also creates the role for the Lambda function, function that will be created in `cicd-account-2.yaml`.

```
aws cloudformation deploy \
--stack-name cross-account-1-cicd \
--template-file ./cf-templates/cicd-account-1.yaml \
--capabilities CAPABILITY_NAMED_IAM \
--parameter-overrides \
  RoleAdministratorAccessDEV=$RoleAdministratorAccessARN_DEV \
  RoleReadOnlyAccessDEV=$RoleReadOnlyAccessARN_DEV \
  RoleAdministratorAccessHOTFIX=$RoleAdministratorAccessARN_HOTFIX \
  RoleReadOnlyAccessHOTFIX=$RoleReadOnlyAccessARN_HOTFIX \
--profile $CICD_PROFILE \
--region $REGION
```

4. Note down the ARN of the Lambda's execution role that was just created in the CICD Account. This ARN will be used in the trust policies to allow the Lambda function to assume roles in Dev and HotFix Accounts.

5. Deploy `dev-account-2.yaml` and `hotfix-account-2.yaml`. They deploy the role and policy that the Lambda Function will assume to make updates on the trust policies.

```
aws cloudformation deploy \
--stack-name cross-account-2-dev \
--template-file ./cf-templates/dev-account-2.yaml \
--capabilities CAPABILITY_NAMED_IAM \
--parameter-overrides \
  ExecutionRoleLambdaUpdateTrustPolicies=$RoleLambdaUpdateTrustPolicies_ARN \
  FirstPartCrossAccountStack=cross-account-1-dev \
--profile $DEV_PROFILE \
--region $REGION
```

```
aws cloudformation deploy \
--stack-name cross-account-2-hotfix \
--template-file ./cf-templates/hotfix-account-2.yaml \
--capabilities CAPABILITY_NAMED_IAM \
--parameter-overrides \
  ExecutionRoleLambdaUpdateTrustPolicies=$RoleLambdaUpdateTrustPolicies_ARN \
  FirstPartCrossAccountStack=cross-account-1-hotfix \
--profile $HOTFIX_PROFILE \
--region $REGION
```

6. Note down the ARNs of `RoleUpdateTrustPolicy` in both the Dev and Hotfix accounts. The Lambda that will be created in the CICD Account will need those ARNs in order to assume those roles in the Dev and Hotfix accounts. 

7. Deploy `cicd-account-2.yaml`. It will deploy the Lambda function, the EventBrigdge rule and a Policy for the Lambda function to assume the specific roles in the Dev and Hotfix accounts. 

```
aws cloudformation deploy \
--stack-name cross-account-2-cicd \
--template-file ./cf-templates/cicd-account-2.yaml \
--capabilities CAPABILITY_NAMED_IAM \
--parameter-overrides \
  RoleUpdateTrustPoliciesDEV=$RoleUpdateTrustPolicy_ARN_DEV \
  RoleUpdateTrustPoliciesHOTFIX=$RoleUpdateTrustPolicy_ARN_HOTFIX \
  FirstPartCrossAccountStack=cross-account-1-cicd \
--profile $CICD_PROFILE \
--region $REGION
```

8. Since the IAM events are only registered in the us-east-1 region, we need to redirect these events to the specified region in the situation where $REGION is not us-east-1. Note down the ARN of the default event bus in $REGION and input it as parameter. 

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