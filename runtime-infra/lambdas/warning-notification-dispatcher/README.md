# Warning report contract

I producer pubblicano sul warning SNS topic un messaggio JSON con `eventType=report`.
Il dispatcher seleziona la destinazione tramite la coppia `report,<producer>` configurata
in `Routes`.

## Schema

```json
{
  "schemaVersion": "1.0",
  "eventId": "request-id",
  "eventType": "report",
  "producer": "producer-name",
  "eventName": "report-name",
  "occurredAt": "2026-07-23T08:00:00Z",
  "severity": "info",
  "environment": "prod",
  "title": "Titolo del report",
  "data": {
    "metrics": {
      "Elementi analizzati": 100,
      "Elementi trovati": 12
    },
    "details": {
      "Tipologia A": 7,
      "Tipologia B": 5
    },
    "durationMs": 1250
  },
  "links": {
    "dashboard": "https://example.amazonaws.com/dashboard"
  },
  "attachment": {
    "filename": "report.csv",
    "contentType": "text/csv",
    "size": 1024,
    "downloadUrl": "https://presigned-url.amazonaws.com/report.csv"
  }
}
```

`title` è un oggetto `data.metrics` non vuoto sono obbligatori. `data.details`,
`data.durationMs`, `links` e `attachment` sono opzionali.

## Delivery mode

- `SUMMARY`: invia titolo, metriche, dettagli e link senza scaricare il CSV.
- `ATTACHMENT`: scarica `attachment.downloadUrl` e allega il CSV a Slack.
- `LINK`: aggiunge al messaggio il link temporaneo presente in `attachment.downloadUrl`.

Per `ATTACHMENT` e `LINK`, `attachment` deve indicare un file `text/csv` raggiungibile
tramite URL HTTPS AWS.
