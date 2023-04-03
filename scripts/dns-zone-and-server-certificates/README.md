# DNS zone management
## main DNS zone (*notifichedigitali.it*)
The *create-or-update-parent-dns-zone.sh* script create the main DNS zone for 
"Piattaforma notifiche" and attach it to the global public DNS service.
The delegation process follow the guidelines described in the 
[DNS](https://pagopa.atlassian.net/wiki/spaces/EN/pages/286657478/DNS)
confluence page.

The structure of "main" DNS zone and "dev & test" subdomains adhere to 
guidelines of PagoPA [FQDNS](https://pagopa.atlassian.net/wiki/spaces/EN/pages/286558635/FQDNs).

Open the script for full list of created certificates and DNS entry.

## "dev & test" subdomains
The subdomains of "notifichedigitali.it" are used for development and test environments.
They are created by the script *create-or-update-all-test-dns-zones.sh*.

Open the script to see the full list of subdomains and certificates that are created.

# Certificate Renewal 
The generated certificates are issued from AWC Certificate manager (ACM)
as "public trusted" certificates. They are automatically renewed as described in
[AWS Documentation](https://docs.aws.amazon.com/acm/latest/userguide/dns-renewal-validation.html).
In case of automatic renewal issues ACM triggers an alarm: we handle it in 
CloudFormation template (devops-msg-sns-topics.yaml); more details and improvement 
in [PN-29](https://pagopa.atlassian.net/browse/PN-629).



# Folder content
This folder contains shell scripts and related cloudformation template to 
generate DNS zones needed by Piattafoma Notifiche.

## Script Entry Points 
 - *create-or-update-parent-dns-zone.sh* script that **create** AWS Route53 
   **DNS zone 'notifichedigitali.it'** from a cloudformation template dns-zone.yaml.
   Also generate and validate server certificates for defined DNS like 
   api.notifichedigitali.it, webapi.notifichedigitali.it, portale.notifichedigitali.it, ... .
   Check the script for exact list.
 - *create-or-update-all-test-dns-zones.sh* create DNS zones for all non production
   environments: dev, uat, beta, ... . This script also create and validate
   needed server certificates like api.beta.notifichedigitali.it, 
   portale.uat.notifichedigitali.it, ... . Check the script for exact list.
   

## Other Files
 - *create-or-update-one-aws-dns-zone.sh*: script used to create one DNS zone and 
   its delegation into its parent zone.
 - *create-or-renew-one-certificate.sh*: script used to create and validate one 
   server certificate, automatic renew is in charge to AWS Certificate Manager.  
 - *dns-zone.yaml*: CloudFormation template used to define a DNS zone 
 - *zone-delegation-recordset.yaml* CloudFormation template used to define a 
   zone delegation
   
