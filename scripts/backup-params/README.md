# Script di backup di secrets e parameters

## Pre-requisiti
Sono necessari i seguenti software:
- aws-cli
- jq

## Backup parameters

`./backup-params.sh -p <aws-profile> -r <aws-region> -f <prefix> -s <skip-prefix>` 

Dove:
- aws-profile è il profilo AWS (opzionale)
- aws-region è la regione AWS (opzionale, default "eu-south-1")
- prefix è il prefisso che verrà assegnato al nuovo parametro (ad es. nel caso in cui il parametro originale si chiami "myParam" ed il prefisso "bck_20230623", il nuovo parametro sarà "/bck_20230623/myParam")
- skip-prefix è il prefisso che verrà ignorato dal processo di backup; questo per evitare di fare "backup di backup"; il valore di default è "bck_"


## Backup secrets

`./backup-secrets.sh -p <aws-profile> -r <aws-region> -f <prefix> -s <skip-prefix>` 

Dove:
- aws-profile è il profilo AWS (opzionale)
- aws-region è la regione AWS (opzionale, default "eu-south-1")
- prefix è il prefisso che verrà assegnato al nuovo secret (ad es. nel caso in cui il secret originale si chiami "mySecret" ed il prefisso "bck_20230623", il nuovo parametro sarà "bck_20230623-mySecret")
- skip-prefix è il prefisso che verrà ignorato dal processo di backup; questo per evitare di fare "backup di backup"; il valore di default è "bck_"


## Cleanup parameters

Lo script elimina i parametri per prefisso; è utile per eliminare i backup non più necessari.

`./cleanup-params.sh -p <aws-profile> -r <aws-region> -f <prefix>` 

Dove:
- aws-profile è il profilo AWS (opzionale)
- aws-region è la regione AWS (opzionale, default "eu-south-1")
- prefix è il prefisso che verrà usato per filtrare i parametri da eliminare; ad es. se si fornisce `bck_` come prefissso, saranno eliminati i parametri del tipo `/bck_.../...` 

## Cleanup parameters

Lo script elimina i parametri per prefisso; è utile per eliminare i backup non più necessari.

`./cleanup-secrets.sh -p <aws-profile> -r <aws-region> -f <prefix>` 

Dove:
- aws-profile è il profilo AWS (opzionale)
- aws-region è la regione AWS (opzionale, default "eu-south-1")
- prefix è il prefisso che verrà usato per filtrare i secrets da eliminare; ad es. se si fornisce `bck_` come prefissso, saranno eliminati i secrets del tipo `bck_...-...` 
