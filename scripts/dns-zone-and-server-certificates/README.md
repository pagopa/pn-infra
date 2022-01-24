# DNS zone management
## main DNS zone (*pn.pagopa.it*)
The *create-or-update-parent-dns-zone.sh* script create the main DNS zone for 
"Piattaforma notifiche" and attach it to the global public DNS service.
The delegation process follow the guidelines described in the 
[DNS](https://pagopa.atlassian.net/wiki/spaces/EN/pages/286657478/DNS)
confluence page.

The structure of "main" DNS zone and "dev & test" subdomains adhere to 
guidelines of PagoPA [FQDNS](https://pagopa.atlassian.net/wiki/spaces/EN/pages/286558635/FQDNs).

Open the script for full list of created certificates and DNS entry.

## "dev & test" subdomains
The subdomains of "pn.pagopa.it" are used for development and test environments.
They are created by the script *create-or-update-all-test-dns-zones.sh*.

Open the script to see the full list of subdomains and certificates that are created.


# Folder content
This folder contains shell scripts and related cloudformation template to 
generate DNS zones needed by Piattafoma Notifiche.

## Script Entry Points 
 - *create-or-update-parent-dns-zone.sh* script that **create** AWS Route53 
   **DNS zone 'pn.pagopa.it'** from a cloudformation template dns-zone.yaml.
   Also generate and validate server certificates for defined DNS like 
   api.pn.pagopa.it, webapi.pn.pagopa.it, portale.pn.pagopa.it, ... .
   Check the script for exact list.
 - *create-or-update-all-test-dns-zones.sh* create DNS zones for all non production
   environments: devel, uat, beta, ... . This script also create and validate
   needed server certificates like api.beta.pn.pagopa.it, 
   portale.uat.pn.pagopa.it, ... . Check the script for exact list.
   

## Other Files
 - *create-or-update-one-aws-dns-zone.sh*: script used to create one DNS zone and 
   its delegation into its parent zone.
 - *create-or-renew-one-certificate.sh*: script used to create and validate one 
   server certificate, automatic renew is in charge to AWS Certificate Manager.  
 - *dns-zone.yaml*: CloudFormation template used to define a DNS zone 
 - *zone-delegation-recordset.yaml* CloudFormation template used to define a 
   zone delegation
   
