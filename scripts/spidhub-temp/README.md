# SpidHub for test environments

Scripts to deploy a temporary solution to use the SPID login for dev and test environments.

This folder contains scripts to deploy and configure an EC2 instance with this containers:

- [spid-testenv2](https://github.com/italia/spid-testenv2): SPID Idp and Sp for test purpose
- [hub-spid-login-ms](https://github.com/pagopa/hub-spid-login-ms)
  - Entry point for SPID login 
  - Integration with SelfCare UserRegistry
  - JWT integration

The _create-new-spidhub.sh_ script automate the EC2 instance creation using the _cfn-templates/vpc_with_public_ec2.yaml_
Cloud Formation template, creating the key pair to connect via ssh and exposing it on the DNS domain.

It store the private key in _$HOME/.spidhub_keys_ directory.

All file in _remote-scripts_ directory are copied in the EC2 instance and used to:
1. install _docker_ and _docker compose_
2. clone the [hub-spid-login-ms](https://github.com/pagopa/hub-spid-login-ms) repo
3. apply the needed configuration (create certificate for SAM, key pairs for JWT, configure _.env_ file)
4. launch container with docker compose

Esempio:

```bash
./create-new-spidhub.sh dev eu-west-1 https://www.pn-develop.pn.pagopa.it/ <user registry apikey>
```