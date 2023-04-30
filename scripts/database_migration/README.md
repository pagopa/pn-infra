# Script Manutenzione del DB per ambienti di Test.

__N.B:__ gli script presenti in questa directory non possono essere eseguiti più di uno alla 
volta e con una sola esecuzione con lo stesso filesystem. Questo perché i nomi dei file 
temporanei non sono randomizzati. E potrebbero anche coincidere tra script differenti.


## Script per il caricamento delle configurazioni
- Per le tabelle pn-PaperCap, pn-PaperZone, pn-PaperCost, pn-PaperDeliveryDriver, 
  pn-PaperDeliveryFile, pn-PaperTender, rifarsi al microservizio pn-paper-channel. 
  Cartella _pn-paper-channel/scripts/aws/migration_ per quanto riguarda le prime due 
  tabelle mentre per le altre tabelle si usa la funzionalità di BackOffice 
  _Gestione gare__
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
_id_ è correlato a SelfCare ed è differente in ogni ambiente, per questo non si può fare 
una semplice copia. 
La procedura è composta di due scipt, 
- _download_OnboardInstitutions.sh_ per preparare un file che andrà modificato per adeguare 
  i valori del campo _id_, 
- _upload_OnboardInstitutions.sh_ per caricare il file modificato nell'ambiente di destinazione.


## Script ricopia contatori
- pn-counter, in caso serva copiarla si può usare lo script _copy_counter_table.sh_ 
  
  


## Elenco script di rimozione dati
- __remove_pg_recipients.sh__: Rimuove dalle tabelle pn-Notifications e pn-NotificationsMetadata 
  le informazioni relative alle notifiche con destinatari di tipo Persona Giuridica.
- __delete_all_data_except_configurations.sh__ Rimuove tutti i dati dal database __eccetto__ le 
  tabelle di configurazione ovvero: pn-aggregates, pn-apiKey, pn-AuditStorage, pn-counter,
  pn-LastPollForFutureActionTable, pn-OnboardInstitutions, pn-paAggregations, pn-PaperCap,
  pn-PaperCost, pn-PaperDeliveryDriver, pn-PaperDeliveryFile, pn-PaperTender, pn-PaperZone,
  pn-PnDeliveryPushShedLock, terraform-lock, pn-AuditStorage, pn-EcAnagrafica, pn-SmStates, 
  pn-SsAnagraficaClient, pn-SsTipologieDocumenti

