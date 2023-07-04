# Script Manutenzione del DB per ambienti di Test.

__N.B:__ gli script presenti in questa directory non possono essere eseguiti più di uno alla 
volta e con una sola esecuzione con lo stesso filesystem. Questo perché i nomi dei file 
temporanei non sono randomizzati. E potrebbero anche coincidere tra script differenti.


## Script per il caricamento delle configurazioni
- Per le tabelle pn-PaperCap, pn-PaperZone, pn-PaperCost, pn-PaperDeliveryDriver, 
  pn-PaperDeliveryFile, pn-PaperTender, rifarsi al microservizio pn-paper-channel. 
  Cartella _pn-paper-channel/scripts/aws/migration_ per quanto riguarda le prime due 
  tabelle mentre per le altre tabelle si usa la funzionalità di BackOffice 
  __Gestione gare__. Negli ambienti di test i dati delle gare si possono caricare anche
  con lo script _scripts/aws/migration/tender.sh_ del progetto 
  [pn-paper-channel](https://github.com/pagopa/pn-paper-channel)
- Le tabelle pn-aggregates, pn-apiKey, pn-paAggregations, non sono ricopiabili e vanno 
  rigenerate tramite chiamate rest, eventualmente eseguite tramite funzionalità di test 
  dell'API-GW di AWS. FIXME generare procedura
- pn-AuditStorage, viene ricostruita alla prima esecuzione di pn-logsaver-be
- pn-LastPollForFutureActionTable, viene ricostruita alla prima esecuzione di pn-delivery-push
- pn-OnboardInstitutions, non può essere copiata perchè ambienti diversi hanno identificativi 
  selfcare differenti. Vedere procedura sottostante.
- terraform-lock, pn-PnDeliveryPushShedLock, non vanno migrate, vengono popolate in automatico
  dai software che le usano.
- pn-SsTipologieDocumenti, pn-SsAnagraficaClient, pn-SmStates utilizzare lo script presente 
  nel repository _pn-ss_ nel file _scripts/dynamoDBLoad.sh_
- pn-EcAnagrafica, n-SmStates utilizzare lo script presente 
  nel repository _pn-ec_ nel file _scripts/dynamoDBLoad.sh_

## Copia tabella pn-OnboardInstitutions con bonifica degli id
La tabella pn-OnboardInstitutions contiene l'elenco delle PA che hanno attivato PN, il campo 
_id_ è correlato a SelfCare ed è differente in ogni ambiente, per questo la semplice copia 
funziona solo tra ambienti di Piattaforma Notifiche che puntano allo stesso ambiente di 
SelfCare.
La procedura è composta di due scipt, 
- _download_OnboardInstitutions.sh_ per preparare un file che andrà modificato per adeguare 
  i valori del campo _id_, 
- _upload_OnboardInstitutions.sh_ per caricare il file modificato nell'ambiente di destinazione.
__N.B.__: su SelfCare va registrato un nuovo prodotto "Piattaforma Notifiche &lt;EnvName&gt;" e
vanno configurate le autorizzazioni di Pubbliche Amministrazioni e loro utenti su tale prodotto.

## Script ricopia contatori
- pn-counter, in caso serva copiarla si può usare lo script _copy_counter_table.sh_. Questa 
  tabella serve perché alcuni servizi (attualmente uno) invocati da _pn-national-registries_
  richiedono un identificativo di richieste numerico monotono crescente.


## Elenco script di rimozione dati
- __remove_pg_recipients.sh__: Rimuove dalle tabelle pn-Notifications e pn-NotificationsMetadata 
  le informazioni relative alle notifiche con destinatari di tipo Persona Giuridica.
- __delete_all_data_except_configurations.sh__ Rimuove tutti i dati dal database __eccetto__ le 
  tabelle di configurazione ovvero: pn-aggregates, pn-apiKey, pn-AuditStorage, pn-counter,
  pn-LastPollForFutureActionTable, pn-OnboardInstitutions, pn-paAggregations, pn-PaperCap,
  pn-PaperCost, pn-PaperDeliveryDriver, pn-PaperDeliveryFile, pn-PaperTender, pn-PaperZone,
  pn-PnDeliveryPushShedLock, terraform-lock, pn-AuditStorage, pn-EcAnagrafica, pn-SmStates, 
  pn-SsAnagraficaClient, pn-SsTipologieDocumenti
- __Rimozione dati da OpenSearch__, ci sono due opzioni:
  - Una facile ma poco performante, una query per cancellare tutti i documenti:
    ```
    POST pn-logs* /_delete_by_query
    {
      "query":{
        "match_all": {}
      }
    }
    ```
  - __L'altra, più performante__, richiede la cancellazione di tutti gli indici il cui nome 
    comincia con ```pn-logs``` utilizzando una volta per indice il comando ```DELETE <index_name>```.
    Gli indici vanno ricreati con i seguenti 3 comandi:
    ```
    PUT /pn-logs10y-000001
    {
      "aliases": {
        "pn-logs10y": {
          "is_write_index": true
        }
      }
    }
    ```
    
    ```
    PUT /pn-logs5y-000001
    {
      "aliases": {
        "pn-logs5y": {
          "is_write_index": true
        }
      }
    }
    ```
    
    ```
    PUT /pn-logs120d-000001
    {
      "aliases": {
        "pn-logs120d": {
          "is_write_index": true
        }
      }
    }
    ```

