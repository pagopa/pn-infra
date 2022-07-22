# Preparazione degli account
__Da eseguire una volta sola prima di ogni altro step__

I passi da fare solo sugli account fuori dall'organizzazione di 
Poste verranno contraddistinti come: _DevOnly_

## Elenco sintetico dei passi
 - Avere 3 account AWS: PN-CORE, HELP-DESK, SPID-HUB
 - _DevOnly_ eseguire script scripts/prepare-networking/pagopa_vpcs/prepare_networking_on_dev.sh
 - Preparare private Route53 hosted zone usando script nella directory scripts/prepare-networking/private_hosted_zones

