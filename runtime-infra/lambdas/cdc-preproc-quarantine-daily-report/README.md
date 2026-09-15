# CDC Preproc Quarantine Daily Report

## Obiettivo

Generare un report giornaliero degli elementi presenti nell'area di quarantena del CDC Preprocessor su S3.

Il report permette di individuare le tabelle con record in quarantena nella giornata di riferimento e il numero di record per ciascuna tabella.

## Struttura S3

Gli elementi in quarantena sono organizzati secondo la seguente struttura:

```text
cdcTos3/cdc-preproc/quarantine/
└── TABLE_NAME_<table>/
    └── YYYY/
        └── MM/
            └── DD/
                └── HH/
                    └── <file>
```

## Requisiti

La soluzione:

- recupera le cartelle delle tabelle presenti sotto `quarantine/`;
- considera solamente le cartelle con prefisso `TABLE_NAME_`;
- utilizza come data di riferimento il giorno UTC precedente all'esecuzione;
- legge tutti i file della partizione giornaliera `YYYY/MM/DD`, includendo tutte le partizioni orarie;
- conta i record presenti nei file, considerando ogni riga non vuota come un record;
- aggrega il conteggio sull'intera giornata per tabella, senza dettaglio orario;
- include nel summary solamente le tabelle con almeno un record in quarantena;
- genera il summary anche quando non viene trovato alcun record.

## Output

Per ogni esecuzione viene prodotto un summary JSON con il conteggio giornaliero dei record per tabella.

Quando sono presenti record in quarantena viene prodotto anche un file di dettaglio `.csv` contenente i record originali in formato JSON Lines.

### Summary JSON

Il JSON contiene data e ora UTC di generazione, data di riferimento e conteggio dei record per tabella.

Esempio:

```json
{
  "generatedAt": "2026-08-14T07:00:03Z",
  "referenceDate": "2026-08-13",
  "tables": [
    {
      "tableName": "pn-UserAttributes",
      "recordCount": 5
    },
    {
      "tableName": "pn-Notifications",
      "recordCount": 12
    }
  ]
}
```

Se non sono presenti record, `tables` è una lista vuota.

### File di dettaglio

Il file `.csv` viene prodotto solamente quando nella giornata di riferimento sono presenti record in quarantena.

Il contenuto mantiene attualmente il formato JSON Lines, con un record JSON per riga.

Esempio:

```text
{"awsRegion":"eu-south-1","eventID":"e54489d8a5","eventName":"INSERT","userIdentity":null,"recordFormat":"application/json","tableName":"pn-Notifications",...}
{"awsRegion":"eu-south-1","eventID":"e545s1d8a5","eventName":"REMOVE","userIdentity":null,"recordFormat":"application/json","tableName":"pn-UserAttributes",...}
```

Il file viene costruito progressivamente in `/tmp` per evitare di mantenere l'intero dataset giornaliero in memoria.

Se non vengono trovati record, il file di dettaglio non viene salvato su S3 e il report viene pubblicato senza attachment.

## Salvataggio su S3

Il summary JSON viene sempre salvato sotto il prefisso di reporting, nella partizione relativa alla giornata di riferimento:

```text
reporting/cdcTos3/cdc-preproc/quarantine/YYYY/MM/DD/
```

Quando sono presenti record, nello stesso percorso viene salvato anche il file di dettaglio `.csv`.

Il nome dei file contiene la data di riferimento e la data e ora UTC di generazione:

```text
report_quarantine_<reference-date>_<generation-timestamp>.json
report_quarantine_<reference-date>_<generation-timestamp>.csv
```

### Esempio

Per un'esecuzione effettuata il `2026-09-11` relativa alla giornata `2026-09-10`, in presenza di record:

```text
s3://<LogsBucketName>/reporting/cdcTos3/cdc-preproc/quarantine/2026/09/10/report_quarantine_2026-09-10_20260911T070003Z.json
```

```text
s3://<LogsBucketName>/reporting/cdcTos3/cdc-preproc/quarantine/2026/09/10/report_quarantine_2026-09-10_20260911T070003Z.csv
```

In assenza di record viene salvato solamente il summary JSON.

## Warning Notifications

Se `ReportNotificationsEnabled=true`, la Lambda pubblica sul Warning SNS topic un evento con `eventType=report`.

Il producer utilizzato per il routing è:

```text
pn-cdc-quarantine-daily-report
```

L'evento contiene:

- data di riferimento;
- numero di tabelle con record in quarantena;
- numero totale di record;
- conteggio dei record per singola tabella;
- attachment del file `.csv`, quando sono presenti record in quarantena.

Quando l'attachment è presente, contiene una presigned URL utilizzata dal Warning Notification Dispatcher per recuperare il file.

Esempio con record presenti:

```json
{
  "schemaVersion": "1.0",
  "eventId": "<lambda-request-id>",
  "eventType": "report",
  "producer": "pn-cdc-quarantine-daily-report",
  "eventName": "cdc-quarantine-daily-report",
  "occurredAt": "2026-09-11T07:00:03+00:00",
  "severity": "info",
  "environment": "dev",
  "title": "CDC Preproc quarantine daily report",
  "data": {
    "metrics": {
      "Reference date": "2026-09-10",
      "Tables in quarantine": 2,
      "Records in quarantine": 17
    },
    "details": {
      "pn-Notifications": 12,
      "pn-UserAttributes": 5
    }
  },
  "links": {},
  "attachment": {
    "filename": "report_quarantine_2026-09-10_20260911T070003Z.csv",
    "contentType": "text/csv",
    "size": 12345,
    "downloadUrl": "<presigned-url>"
  }
}
```

Se non sono presenti record, l'evento viene pubblicato senza `attachment`, ad esempio:

```json
{
  "schemaVersion": "1.0",
  "eventId": "<lambda-request-id>",
  "eventType": "report",
  "producer": "pn-cdc-quarantine-daily-report",
  "eventName": "cdc-quarantine-daily-report",
  "occurredAt": "2026-09-11T07:00:03+00:00",
  "severity": "info",
  "environment": "dev",
  "title": "CDC Preproc quarantine daily report",
  "data": {
    "metrics": {
      "Reference date": "2026-09-10",
      "Tables in quarantine": 0,
      "Records in quarantine": 0
    },
    "details": {}
  },
  "links": {}
}
```

La modalità di consegna verso Slack è configurata nella route del Warning Notification Dispatcher.

Con una route `ATTACHMENT`:

- se il report contiene un attachment, il dispatcher recupera il file tramite presigned URL e lo allega alla notifica Slack;
- se il report non contiene un attachment, il dispatcher invia solamente il summary su Slack.

## Configurazione

I principali parametri applicativi sono definiti in `runtime-infra/pn-cdc-analytics.yaml` e propagati alla Lambda tramite CloudFormation.

Sono configurabili:

- prefisso S3 della quarantine;
- prefisso S3 dei report;
- prefisso delle cartelle delle tabelle;
- producer del report;
- event name;
- titolo del report;
- scheduling;
- stato dello scheduler;
- abilitazione delle notifiche;
- retention dei log.

Le configurazioni specifiche di ambiente possono sovrascrivere i relativi valori tramite i file:

```text
runtime-infra/pn-cdc-analytics-<env>-cfg.json
```

## Scheduling

La Lambda viene eseguita tramite EventBridge Scheduler.

Ad ogni esecuzione vengono elaborati tutti i record presenti nella partizione `YYYY/MM/DD` relativa alla giornata UTC precedente, includendo tutte le partizioni orarie.

La schedulazione è configurabile tramite:

```text
QuarantineReportScheduleExpression
```

mentre lo stato dello scheduler è controllato tramite:

```text
QuarantineReportScheduleState
```

Ad esempio, in DEV la configurazione può essere definita in:

```text
runtime-infra/pn-cdc-analytics-dev-cfg.json
```

Eventuali modifiche alla frequenza o allo stato dello scheduler non richiedono modifiche al codice della Lambda.

## Logging

La Lambda utilizza un CloudWatch Log Group dedicato creato tramite:

```text
fragments/log-group.yaml
```

Il Log Group viene associato esplicitamente alla Lambda tramite `LoggingConfig`.

La retention utilizza il parametro `LogRetention` fornito dall'infrastruttura e propagato fino a `LogGroupRetention`.

I log applicativi riportano le principali fasi dell'elaborazione:

- avvio del report;
- numero di cartelle delle tabelle individuate;
- numero di record trovati per tabella;
- completamento della scrittura dei report su S3;
- percorsi S3 degli output generati;
- assenza di record in quarantena e pubblicazione del report senza attachment;
- pubblicazione della notifica;
- completamento dell'elaborazione.

In caso di errore tecnico viene prodotto un log `ERROR` e l'eccezione viene rilanciata in modo che l'invocazione Lambda risulti fallita.

## Allarmi

Gli allarmi tecnici della Lambda vengono creati tramite:

```text
fragments/lambda-alarms.yaml
```

Gli allarmi sono relativi ai fallimenti tecnici della Lambda e sono separati dal report applicativo inviato tramite Warning Notifications.

In particolare vengono considerate:

- le righe di log con livello `ERROR`;
- la metrica nativa `AWS/Lambda Errors`.

Gli allarmi vengono pubblicati sul topic configurato tramite `AlarmSNSTopicArn`.

## Note

- Lo scheduler può essere abilitato o disabilitato tramite configurazione.
- La data di riferimento è sempre il giorno UTC precedente all'esecuzione.
- Il conteggio viene effettuato sull'intera giornata senza dettaglio orario.
- Le tabelle senza record in quarantena non vengono incluse nel summary.
- Il summary JSON viene generato anche quando non sono presenti record in quarantena.
- Il file di dettaglio viene salvato su S3 e allegato alla notifica solamente quando sono presenti record.
- In assenza di record, la notifica contiene solamente il summary con `Tables in quarantine = 0` e `Records in quarantine = 0`.
- Il file di dettaglio utilizza attualmente JSON Lines anche se salvato con estensione `.csv`.
- L'eventuale evoluzione verso un CSV strutturato per colonne può essere gestita separatamente senza modificare il formato del summary.
- `WarningSNSTopicArn` viene utilizzato per il report applicativo, mentre `AlarmSNSTopicArn` viene utilizzato per gli allarmi tecnici della Lambda.
