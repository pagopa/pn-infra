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
- legge tutti i file della partizione giornaliera `YYYY/MM/DD`, senza dettaglio orario;
- conta i record presenti nei file, considerando ogni riga non vuota come un record;
- aggrega il conteggio per tabella;
- include nel summary solamente le tabelle con almeno un record in quarantena;
- genera il report anche quando non viene trovato alcun record.

## Output

Per ogni esecuzione vengono prodotti un summary JSON e un CSV.

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

### CSV

Il CSV contiene i record originali presenti in quarantena nella giornata di riferimento, una riga per record.

Esempio:

```text
{"awsRegion":"eu-south-1","eventID":"e54489d8a5","eventName":"INSERT","userIdentity":null,"recordFormat":"application/json","tableName":"pn-Notifications",...}
{"awsRegion":"eu-south-1","eventID":"e545s1d8a5","eventName":"REMOVE","userIdentity":null,"recordFormat":"application/json","tableName":"pn-UserAttributes",...}
```

Il CSV viene costruito progressivamente in `/tmp` per evitare di mantenere l'intero dataset giornaliero in memoria.

## Salvataggio su S3

JSON e CSV vengono salvati nella partizione relativa alla giornata di riferimento:

```text
cdcTos3/cdc-preproc/quarantine/report/YYYY/MM/DD/
```

Il nome contiene la data di riferimento e la data e ora UTC di generazione.

```text
report_quarantine_<reference-date>_<generation-timestamp>.json
report_quarantine_<reference-date>_<generation-timestamp>.csv
```

## Esempio degli output prodotti

Per una esecuzione effettuata il `2026-09-11` relativa alla giornata `2026-09-10`:

### JSON su S3

```text
s3://<LogsBucketName>/cdcTos3/cdc-preproc/quarantine/report/2026/09/10/report_quarantine_2026-09-10_20260911T070003Z.json
```

```json
{
  "generatedAt": "2026-09-11T07:00:03Z",
  "referenceDate": "2026-09-10",
  "tables": [
    {
      "tableName": "pn-Notifications",
      "recordCount": 12
    },
    {
      "tableName": "pn-UserAttributes",
      "recordCount": 5
    }
  ]
}
```

### CSV su S3

```text
s3://<LogsBucketName>/cdcTos3/cdc-preproc/quarantine/report/2026/09/10/report_quarantine_2026-09-10_20260911T070003Z.csv
```

```text
{"awsRegion":"eu-south-1","eventID":"e54489d8a5","eventName":"INSERT","userIdentity":null,"recordFormat":"application/json","tableName":"pn-Notifications",...}
{"awsRegion":"eu-south-1","eventID":"e545s1d8a5","eventName":"REMOVE","userIdentity":null,"recordFormat":"application/json","tableName":"pn-UserAttributes",...}
```

### Report inviato a Warning Notifications

Se `ReportNotificationsEnabled=true`, viene pubblicato sul Warning SNS topic un evento `report` con metriche, dettaglio per tabella e attachment CSV.

Esempio:

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

Con una route in modalità `ATTACHMENT`, il dispatcher utilizza la presigned URL per inviare su Slack il riepilogo e il CSV allegato.

## Notifica

La pubblicazione del report è controllata tramite il parametro `ReportNotificationsEnabled`.

Il producer utilizzato per il routing è:

```text
pn-cdc-quarantine-daily-report
```

## Scheduling

La Lambda viene eseguita ogni giorno alle 07:00 UTC tramite EventBridge Scheduler e produce un report relativo alla giornata UTC precedente.

La frequenza di esecuzione è configurata nel file runtime-infra\pn-cdc-analytics-dev-cfg.json tramite il parametro dedicato alla schedulazione, mentre l'attivazione o la disattivazione dello scheduler è controllata dal relativo parametro di stato.

**Note**
- Lo scheduler può essere abilitato o disabilitato tramite configurazione.
- Il report analizza i record presenti in quarantena nel periodo compreso tra le 00:00:00 e le 23:59:59 UTC del giorno precedente.
- Eventuali modifiche alla frequenza di esecuzione possono essere effettuate aggiornando la configurazione nel file runtime-infra\pn-cdc-analytics-dev-cfg.json, senza necessità di intervenire sul codice della Lambda.