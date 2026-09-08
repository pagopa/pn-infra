# CDC Preproc Quarantine Daily Report

## Obiettivo

Realizzare una Lambda per generare un report giornaliero degli elementi presenti nell'area di quarantena del CDC Preprocessor su S3.

Il report permette di individuare rapidamente quali tabelle presentano elementi in quarantena nella giornata di riferimento e quanti file sono presenti per ciascuna tabella.

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

## Definizione dei requisiti

La soluzione:

- recupera le cartelle delle tabelle presenti sotto `quarantine/`;
- considera solamente le cartelle con prefisso `TABLE_NAME_`;
- verifica la presenza di elementi per la giornata di riferimento;
- conta il numero di file presenti per ogni tabella;
- non legge il contenuto dei file;
- riporta solamente le tabelle con almeno un elemento in quarantena;
- genera il report anche quando non viene trovato alcun elemento.

### Formato di output

Il report viene prodotto in formato JSON e contiene:

- data e ora UTC di generazione;
- data di riferimento del check;
- nome delle tabelle con elementi in quarantena;
- numero di file per ogni tabella.

Esempio:

```json
{
  "generatedAt": "2026-09-03T09:00:38Z",
  "referenceDate": "2026-09-03",
  "tables": [
    {
      "tableName": "pn-UserAttributes",
      "filesCount": 1
    }
  ]
}
```

Nel caso in cui non siano presenti elementi in quarantena, il report viene comunque generato con una lista di tabelle vuota e un messaggio esplicativo.

### Salvataggio del report

I report vengono salvati sotto:

```text
cdcTos3/cdc-preproc/quarantine/report/
```

Il nome del file contiene la data di riferimento del check e la data e ora UTC di generazione.

- Formato: `report_quarantine_<reference-date>_<generation-timestamp>.json`
- Esempio: `report_quarantine_2026-09-03_20260903T090038Z.json`

## Notifica

Al termine dell'elaborazione, la Lambda può pubblicare un riepilogo tramite il sistema centralizzato Warning Notifications.

La notifica utilizza il formato `eventType: report` e riporta:

- data di riferimento;
- numero di tabelle con elementi in quarantena;
- numero complessivo di file individuati;
- dettaglio del numero di file per ciascuna tabella;
- riferimento al report JSON salvato su S3.

La pubblicazione è controllata tramite il parametro `ReportNotificationsEnabled`.

## Scheduling

La Lambda viene eseguita tramite EventBridge Scheduler e utilizza come data di riferimento la giornata UTC di esecuzione.

La frequenza di esecuzione è configurabile tramite il parametro `ScheduleExpression`.

Lo scheduler può essere abilitato o disabilitato tramite il parametro `EnableSchedule`, consentendo di mantenere disattivata l'esecuzione automatica durante le fasi di test.
