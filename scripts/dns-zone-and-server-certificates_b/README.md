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

# Folder content
This folder contains shell scripts and related cloudformation template to 
generate DNS zones needed by Piattafoma Notifiche.

## Script Entry Points 
 - *ensure-public-dns.sh* create "principal environment DNS zone" 
   (example dev.notifichedigitali.it) and _spid_ children zone.

## Other Files
 - *create-or-update-one-aws-dns-zone.sh*: script used to create one DNS zone and 
   its delegation into its parent zone.
 - *cnf-templates/dns-zone.yaml*: CloudFormation template used to define a DNS zone 
 - *cnf-templates/spid-dns-zone.yaml*: CloudFormation template used to define child DNS zone
 - *cnf-templates/zone-delegation-recordset.yaml* CloudFormation template used to define a 
   zone delegation
   
