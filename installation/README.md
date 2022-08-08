Guida all'installazione di un singolo ambiente di Piattaforma Notifiche

# Prima di cominciare

- Decidere il nome dell'ambiente, ad esempio _cert_
- Creare 4 account AWS:
  - __SPIDHUB__
  - __CONFIDENTIAL-INFORMATION__ 
  - __PN-CORE__
  - __HELPDESK__
- Per ognuno di questi account definire un profilo di AWS CLI con i diritti di amministrazione. 
  In seguito chiameremo questi profili:
  - __profilo_spidhub__ (relativo all'account _SPIDHUB_)
  - __profilo_confidential__ (relativo all'account _CONFIDENTIAL-INFORMATION_)
  - __profilo_core__ (relativo all'account _PN-CORE_)
  - __profilo_helpdesk__ (relativo all'account _HELPDESK_)
- Comunicare ai gestori dell'account di Continuous Integration (Team Piattaforma Notifiche core) 
  gli AWS Account id _CONFIDENTIAL-INFORMATION_, _PN-CORE_, _HELPDESK_ allo scopo di abilitare 
  l'accesso agli artefatti da installare.
- Profilo __dns_delegator__: per definire questo profilo è necessario chiedere delle credenziali 
  per l'utente CreateDnsColl dell'account 946373734005 o per un ruolo equivalente. 
  Tale account (946373734005), allo stato attuale, contiene la zona DNS principale di Piattaforma
  Notifiche, ovvero _pn.pagopa.it_. Tali credenziali verranno usate solo nella fase 
  _Preparazione Networking_._Zone DNS pubbliche_ per creare una delega verso l'ambiente che si
  sta installando per la prima volta.
- Richiedere i __secrets__ contenenti le API key necessarie alla definizione dei secret come 
  descritto nella pagina "Configurazioni Secrets" di confluence.

# Preparazione Networking

__Prerequisiti__: account e profili descritti nel paragrafo _Prima di cominciare_

## VPC e Transit Gateway
- Definire networking tra account dello stesso ambiente come da diagramma
  ![Networking interno ad un installazione di Piattaforma Notifiche](hl_network_infra.drawio.png).
  _Già implementato sull'infrastruttura attuale_


## Zone DNS private

### Prerequisiti
 - aver completato gli step precedenti.

### Scopo
 - in ognuno degli account _CONFIDENTIAL-INFORMATION_, _PN-CORE_, _HELPDESK_ dovrà essere presente
   una private hosted zone e i nomi DNS registrati dovranno essere risolvibili da ognuno degli account
   nominati.

### Procedimento
  - Effettuare il clone del repository github [pn-infra](https://github.com/pagopa/pn-infra)
  - Effettuare il checkout del branch main
  - Impostare la directory corrente al folder `scripts/prepare-networking/private_hosted_zones`
  - Eseguire lo script bash [create_and_share_private_hosted_zones.sh](../scripts/prepare-networking/private_hosted_zones/create_and_share_private_hosted_zones.sh) 
    seguendo la seguente parametrizzazione:
    ```
    ./create_and_share_private_hosted_zones.sh \
        -p-1 profilo_core \
        -d-1 core.pn.internal \
        -v-1 <id-della-vpc-privata-account-core> \
        \
        -p-2 profilo_helpdesk \
        -d-2 helpdesk.pn.internal \
        -v-2 <id-della-vpc-privata-account-helpdesk> \
        \
        -p-3 profilo_confidential \
        -d-3 confidential.pn.internal \
        -v-3 <id-della-vpc-privata-account-confidential-info>
    ```
  - `<id-della-vpc-privata-account-core>` deve essere sostituito col il _VPC id_ della VPC
    privata presente nell'account _PN-CORE_.
  - `<id-della-vpc-privata-account-helpdesk>` deve essere sostituito col il _VPC id_ della VPC
    privata presente nell'account _HELPDESK_.
  - `<id-della-vpc-privata-account-confidential-info>` deve essere sostituito col il _VPC id_ 
    della VPC privata presente nell'account _CONFIDENTIAL-INFORMATION_.

### Test
  - Per ogni account _CONFIDENTIAL-INFORMATION_, _PN-CORE_, _HELPDESK_ creare macchine EC2 nelle 
    VPC private ed eseguire i comandi
    - `dig -t TXT testdns.core.pn.internal` 
      il cui risultato atteso è _"Test DNS entry for Zone core.pn.internal"_
    - `dig -t TXT testdns.helpdesk.pn.internal` 
      il cui risultato atteso è _"Test DNS entry for Zone helpdesk.pn.internal"_
    - `dig -t TXT testdns.confidential.pn.internal` 
      il cui risultato atteso è _"Test DNS entry for Zone confidential.pn.internal"_


## Zone DNS pubbliche

### Prerequisiti
 - aver completato con successo gli step precedenti.

### Scopo
 - Generare un dominio DNS nella forma `<nome-ambiente>.pn.pagopa.it` in cui registrare i DNS delle api 
   e delle applicazioni web dello specifico ambiente di piattaforma notifiche.

### Procedimento
  - Effettuare il clone del repository github [pn-infra](https://github.com/pagopa/pn-infra)
  - Effettuare il checkout del branch main
  - Impostare la directory corrente al folder `scripts/dns-zone-and-server-certificates`
  - Eseguire lo script bash [ensure-public-dns-and-certificates.sh](../scripts/dns-zone-and-server-certificates/ensure-public-dns-and-certificates.sh) 
    seguendo la seguente parametrizzazione:
    ```
    ./ensure-public-dns-and-certificates.sh \
        -e <nome-ambiente> \
        -p profilo_core \
        -P profilo_dns_delegator \
        -l profilo_spidhub
    ```
    Dove `<nome-ambiente>` va sostituito, ad esempio, con _"cert"_
### Test
  - Da un computer esterno ad AWS 
    - il comando `dig -t TXT testdns.cert.pn.pagopa.it` 
      deve rispondere _"Test DNS entry for PN cert"_
    - il comando `dig -t TXT testdns.spid.cert.pn.pagopa.it` 
      deve rispondere _"Test DNS entry for PN SPID cert"_
  - Nell'account _PN-CORE_ devono essere presenti e in stato issued i seguenti certificati:
    - Region _eu-south-1_: api.cert.pn.pagopa.it, webapi.cert.pn.pagopa.it, api-io.cert.pn.pagopa.it
    - Region _us-east-1_: portale.cert.pn.pagopa.it, portale-pa.cert.pn.pagopa.it, portale-login.cert.pn.pagopa.it



# Installazione SpidHub

## Prerequisiti
  - aver completato con successo gli step precedenti.
  - Avere un api-key di accesso a UserRegistry. Vedere pagina "Configurazioni Secrets" di confluence

## Scopo
Installare il sistema di login utilizzato dai destinatari delle notifiche.

## Preparazione dei file di configurazione
- Clonare il repository [pn-hub-spid-login-aws](https://github.com/pagopa/pn-hub-spid-login-aws)
- Nella cartella _"pn-spid-login-aws/scripts/deploy/environments"_ sono presenti le sottocartelle 
  contenenti le configurazioni, una per ambiente. Allo stato attuale i nuovi ambienti vengono creati
  copiando una cartella e sostituendo il nome dle vecchio ambiente con il nuovo.

  Fanno eccezione alcuni parametri del file __params.json__
  - __FrontEndVpcId__: deve essere valorizzato con l'id della VPC PAGOPA-CORENETWORK-INGRESS-CERT-VPC
  - __BackEndVpcId__: deve essere valorizzato con l'id della VPC PAGOPA-CERT-HUBSPIDLOGIN-VPC
  - __FrontEndSubnets__: deve essere valorizzato con gli id delle subnet PAGOPA-CORENETWORK-INGRESS-CERT-DMZ-A, PAGOPA-CORENETWORK-INGRESS-CERT-DMZ-B, PAGOPA-CORENETWORK-INGRESS-CERT-DMZ-C
  - __BackEndSubnets__: deve essere valorizzato con gli id delle subnet PAGOPA-CERT-HUBSPIDLOGIN-GENERIC-A, PAGOPA-CERT-HUBSPIDLOGIN-GENERIC-B, PAGOPA-CERT-HUBSPIDLOGIN-GENERIC-C
  - __InternalNlbIps__: "10.<BackEndVpc-CIDR-second-octect-from-left>.63.200,10.<BackEndVpc-CIDR-second-octect-from-left>.127.200,10.<BackEndVpc-CIDR-second-octect-from-left>.191.200"
  - __HostedZoneId__: deve essere valorizzato lo zone id della hosted zone spid.cert.pn.pagopa.it
  

## Procedimento d'installazione
  - Eseguire il comando 
    ```
      aws --profile profilo_spidhub \
        iam create-service-linked-role \
            --aws-service-name ecs.amazonaws.com
    ```
    Per assicurarsi che l'utente possa creare cluster ECS.
  
 - Eseguire il comando
   ```
   ./setup.sh profilo_spidhub eu-south-1 cert <UserRegistryApiKeyForPF>
   ```
   Ove `UserRegistryApiKeyForPF` va valorizzato con il valore _UserRegistryApiKeyForPF_ 
   del secret _pn-PersonalDataVault-Apikey_
- Quando il deploy dello stack è terminato bisogna:
  - Accedere alla console web del servizio AWS ECS dell'account _SPIDHUB_ regione eu-south-1.
  - Selezionare il cluster ECS presente
  - Riavviare tutti i task del servizio `spidhub-<nome-ambiente>-hub-login`. Questo riavvio serve
    per supportare l'idp di test (non necessario in prod perché non sarà necessario l'idp di test).

### Test
  - Dal proprio browser navigare all'url `https://hub-login.spid.cert.pn.pagopa.it/login?entityID=xx_testenv2&authLevel=SpidL2`
  - Effettuare il login con le credenziali di un utente di test
  - Verificare che, dopo la login, la navigazione venga direzionata all'url `https://portale.cert.pn.pagopa.it/`



# Installazione DATA VAULT

## Precondizioni

### Preparazione configurazioni

Nel repository [pn-cicd](https://github.com/pagopa/pn-cicd) aggiungere le configurazioni relative al
nuovo ambiente (ad esempio cert) nella cartella pn-cicd/cd-cli/custom-config/pn-data-vault. 

Le configurazioni sono composte da due file:

- `cd-cli/custom-config/pn-data-vault/scripts/aws/cfn/once4account/coll.yaml` che va 
  ricopiato in `cert.yaml` nella stessa posizione ed eventualmente personalizzare l'invio degli allarmi su slack o per mail. 
  Fondamentale è mantenere gli output esistenti.
- `cd-cli/custom-config/pn-data-vault/scripts/aws/cfn/microservice-coll-cfg.json`che va ricopiato in
  `microservice-cert-cfg.json` nella stessa posizione e modificato nei seguenti parametri:
  - __VpcId__: Id della VPC PAGOPA-CERT-CONFIDENTIALINFO-VPC
  - __VpcCidr__: CIDR della VPC PAGOPA-CERT-CONFIDENTIALINFO-VPC
  - __VpcSubnets__: id delle sotto reti PAGOPA-CERT-CONFIDENTIALINFO-GENERIC-A, PAGOPA-CERT-CONFIDENTIALINFO-GENERIC-B, PAGOPA-CERT-CONFIDENTIALINFO-GENERIC-C
  - __VpcSubnetsRoutingTables__: id della tabella di routing PAGOPA-CERT-CONFIDENTIALINFO-GENERIC-RT
  - __PrivateHostedZone__: id della hosted zone privata `confidential.pn.internal` presente nell'account _CONFIDENTIAL-INFORMATION_,
  - __EcsDefaultSecurityGroup__: id del security group PAGOPA-CERT-CONFIDENTIALINFO-MAIN-SG,
- Una volta aggiornate le configurazioni il repository va aggiornato e memorizzato il __commit-id__

### Preparazione file con la versioni degli script di deploy (__desired-commit-ids-env.sh__)
- Va scaricato dall'ambiente di collaudo il file 
 `s3://cd-pipeline-datavault-cdartifactbucket-1lf70f4dd9hib/config/desired-commit-ids-env.sh`
 e modificato sostituendo il _cd_scripts_commitId_ con il __commit-id__ memorizzato alla fine del paragrafo
 precedente.

## Procedimento d'installazione

Tutte le operazioni vanno eseguite nell'account _CONFIDENTIAL-INFORMATION_ nella regione _eu-south-1_
- Definire un secret contenente le necessarie API-Key seguendo quanto descritto nella pagina
  confluence _Configurazioni Secrets_ al paragrafo _pn-PersonalDataVault-Apikey_.
- Tramite console web del servizio AWS CloudFormation effettuare il deploy del template 
  [data-vault-only-pipeline.yaml](https://github.com/pagopa/pn-cicd/blob/main/cd-cli/cnf-templates/data-vault-only-pipeline.yaml)
- Nello stack creato al punto precedente localizzare la risorsa "Bucket S3" con nome logico _CdArtifactBucket_
- Nel bucket _CdArtifactBucket_ creare la cartella __config__
- Nel bucket _CdArtifactBucket_ caricare:
  - il file [empty.zip](https://github.com/pagopa/pn-cicd/blob/main/cd-cli/cnf-templates/empty.zip) sulla radice
  - il file _desired-commit-ids-env.sh_ preparato in precedenza nella cartella _config_
- Eseguire la pipeline _pn-env-update-pipeline_

## Test
- Verificare che sia stato creato un cluster ECS con nome _pn-confidential-ecs-cluster_ e che abbia
  un servizio con nome che cominci per _pn-data-vault-microsvc-cert-DataVaultMicroservice-_ in esecuzione.


# Installazione PN-CORE

## Precondizioni

### Pacchettizzazione Front End

Richiedere al team di front-end di aggiungere gli artifact dei siti web dedicati all'ambiente specifico.

### Preparazione configurazioni

Breve sintesi dei parametri da configurare per maggiori dettagli riferirsi alla pagina confluence
[Configurazioni Prodotto](https://pagopa.atlassian.net/wiki/spaces/PN/pages/527433857/Configurazioni+prodotto).

Nel repository [pn-cicd](https://github.com/pagopa/pn-cicd) aggiungere le configurazioni relative al
nuovo ambiente (ad esempio cert) in tutte le sottocartelle di `cd-cli/custom-config`. Le configurazioni, 
allo stato attuale, sono ottenibili da quelle di un altro ambiente sostituendo il nome dell'ambiente 
vecchio con il nuovo.

Modificare i seguenti parametri:
- File `pn-delivery/scripts/aws/cfn/microservice-cert-cfg.json`
  - __SandboxSafeStorageBaseUrl__: valorizzato all'url di safe-storage dello specifico ambiente
- File `pn-delivery-push/scripts/aws/cfn/microservice-cert-cfg.json`
  - __SandboxSafeStorageBaseUrl__: valorizzato all'url di safe-storage dello specifico ambiente
  - __ExternalChannelBaseUrl__ che va valorizzato all'url di external-channel dello specifico ambiente
- File `pn-frontend/aws-cdn-templates/cert/env-cdn.sh`
  - __ZONE_ID__: valorizzato con l'identificativo della zona cert.pn.pagopa.it
  - __PORTALE_PA_CERTIFICATE_ARN__: valorizzato con l'arn del certificato per l'URL portale-pa.cert.pn.pagopa.it
  - __PORTALE_PF_CERTIFICATE_ARN__: valorizzato con l'arn del certificato per l'URL portale.cert.pn.pagopa.it
  - __PORTALE_PF_LOGIN_CERTIFICATE_ARN__: valorizzato con l'arn del certificato per l'URL portale-login.cert.pn.pagopa.i
  - Frammento __&lt;NomeBucketLegalInput&gt;__: sostituito con il nome del bucket utilizzato 
    per l'input di allegati alle notifiche per lo specifico ambiente
- File `pn-infra/runtime-infra/pn-infra-cert-cfg.json`
  - __VpcId__: Id della VPC PAGOPA-CERT-PNCORE-VPC
  - __VpcCidr__: CIDR della VPC PAGOPA-CERT-PNCORE-VPC
  - __VpcSubnets__: id delle sottoreti PAGOPA-CERT-PNCORE-GENERIC-A, PAGOPA-CERT-PNCORE-GENERIC-B, PAGOPA-CERT-PNCORE-GENERIC-C
  - __VpcSubnetsRoutingTables__: id della tabella di routing PAGOPA-CERT-PNCORE-GENERIC-RT
  - __PrivateHostedZone__: id della hosted zone privata `core.pn.internal` presente nell'account _CONFIDENTIAL-INFORMATION_,
  - __EcsDefaultSecurityGroup__: id del security group PAGOPA-CERT-PNCORE-MAIN-SG
- File `pn-infra/runtime-infra/pn-ipc-cert-cfg.json`
  - __ApiCertificateArn__: ARN del certificato per il DNS api.cert.pn.pagopa.it
  - __WebApiCertificateArn__: ARN del certificato per il DNS webapi.cert.pn.pagopa.it
  - __IoApiCertificateArn__: ARN del certificato per il DNS api-io.cert.pn.pagopa.it
  - __HostedZoneId__: l'id della zona DNS cert.pn.pagopa.it
  - __SafeStorageAccountId__: l'id dell'account AWS in cui si trovano safe-storage ed external channel
- File `pn-user-attributes/scripts/aws/cfn/microservice-cert-cfg.json`
  - __ExternalChannelBasePath__: l'url di external-channel per lo specifico ambiente

__N.B.:__ Una volta aggiornate le configurazioni sul repository git memorizzare il __commit-id__ da utilizzare
nel passo successivo.

### Preparazione file con i _commit-id_ (__desired-commit-ids-env.sh__)

- Va scaricato dall'ambiente di collaudo il file 
 `s3://cd-pipeline-cdartifactbucket-4z3nf89jd2zy/config/desired-commit-ids-env.sh`
 e va modificato sostituendo il _cd_scripts_commitId_ con il __commit-id__ memorizzato alla fine del paragrafo
 precedente.

## Procedimento d'installazione

Tutte le operazioni vanno eseguite nell'account _PN-CORE_ nella regione _eu-south-1_

- Definire un secret contenente le necessarie API-Key seguendo quanto descritto nella pagina
  confluence _Configurazioni Secrets_ ai paragrafi _pn-ExternalRegistries-Secrets_ e _DataLake_.
- Tramite console web del servizio AWS CloudFormation effettuare il deploy del template 
  [complete-pipeline.yaml](https://github.com/pagopa/pn-cicd/blob/main/cd-cli/cnf-templates/complete-pipeline.yaml)
- Nello stack creato al punto precedente localizzare la risorsa "Bucket S3" con nome logico _CdArtifactBucket_
- Nel bucket _CdArtifactBucket_ creare la cartella __config__
- Nel bucket _CdArtifactBucket_ caricare:
  - il file [empty.zip](https://github.com/pagopa/pn-cicd/blob/main/cd-cli/cnf-templates/empty.zip) sulla radice
  - il file _desired-commit-ids-env.sh_ preparato in precedenza nella cartella _config_
- Eseguire la pipeline _pn-env-update-pipeline_

## Test

Testare il nuovo ambiente di PN


