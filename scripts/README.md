# Folder content

Every child of this folder contains a different set of *nix shel scripts.

 - [**dns-zone-and-server-certificates**](./dns-zone-and-server-certificates) 
   contains the scripts used for initialization of 
   - pn.pagopa.it DNS zone (used by prod environment);
   - its children zones (used by non-prod environments) 
   - and the server certificates needed by that environments.

 - [**s3tables-update-schema**](./s3tables-update-schema)
   updates an existing S3 Tables schema with a compact preview and explicit
   confirmation before applying column changes.
