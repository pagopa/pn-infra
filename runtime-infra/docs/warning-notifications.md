# Warning notifications: routing di allarmi e report verso Slack

## 1. Obiettivo

La soluzione permette di inviare gruppi selezionati di allarmi CloudWatch e report applicativi verso canali Slack dedicati usando un solo topic centrale, `pn-WarningSnsTopic`.

Le route possono anche sopprimere intenzionalmente un evento in uno specifico ambiente usando la destinazione `DROP`.

`pn-simulatore-recapiti` e `pn-iam-unused-access-analyzer` sono esempi di integrazione. Non sono dipendenze della piattaforma.

## 2. Principi

1. Gli eventi deviati pubblicano solamente su `pn-WarningSnsTopic`.
2. Gli eventi standard continuano a pubblicare solamente su `pn-AllAlarmSnsTopic`.
3. Pubblicare lo stesso allarme su entrambi i topic produce due notifiche.
4. Topic, SQS, DLQ e subscription costituiscono il trasporto stabile.
5. Dispatcher, template e route costituiscono il runtime modificabile.
6. Il producer non conosce il canale Slack e non possiede il bot token.
7. La soppressione e sempre esplicita con `DROP`; l'assenza di una route e un errore.

## 3. Architettura

```text
Producer core/confinfo
   | CloudWatch alarm oppure report JSON
   v
pn-WarningSnsTopic nell'account core
   | SNS subscription
   v
pn-Warning-Notification-Dispatcher (SQS)
   | Lambda event source mapping, batch size 1
   v
WarningNotificationDispatcher
   | prima route valida
   +--> channel ID --> Slack
   +--> DROP       --> log e completamento senza notifica

Errori ripetuti --> DLQ --> CloudWatch alarm
```

Il diagramma modificabile si trova in `runtime-infra/docs/alarm-routing-evolution.drawio`.

## 4. Separazione degli stack

### 4.1 Trasporto in infra

`runtime-infra/pn-infra-storage.yaml` crea nell'account core:

- `pn-WarningSnsTopic`;
- topic policy, inclusa la pubblicazione dal confinfo account;
- coda `pn-Warning-Notification-Dispatcher`;
- DLQ `pn-Warning-Notification-Dispatcher-DLQ`;
- subscription SNS verso SQS;
- allarme CloudWatch sulla DLQ.

Gli output principali sono `WarningSNSTopicArn`, `WarningSNSTopicName`, `WarningDispatcherName` e `WarningDispatcherQueueArn`.

Lo stack confinfo non crea un secondo topic. Ricostruisce l'ARN del topic core usando `PnCoreAwsAccountId` e `WarningSNSTopicName`.

### 4.2 Runtime nel post-deploy

`runtime-infra/pn-warning-notifications.yaml` crea:

- Lambda `WarningNotificationDispatcher`;
- event source mapping SQS;
- ruolo e policy;
- log group;
- allarmi tecnici della Lambda.

Il deploy viene eseguito come primo step del post-deploy da `pn-cicd/cd-cli/deployWarningNotifications.sh`.

Route, renderer e canali possono quindi essere aggiornati senza rieseguire l'intero deploy infrastrutturale.

## 5. Slack App

La Slack App deve avere almeno questi Bot Token Scopes:

- `chat:write` per i messaggi;
- `files:write` per i CSV.

Per un canale privato:

1. invitare il bot con `/invite @nome-app`;
2. recuperare il channel ID;
3. aggiungere la route nel cfg dell'ambiente;
4. eseguire il post-deploy.

Il bot token e letto dal secret:

```text
go/send-monitor-tpp-messages/slack-token
```

La Lambda supporta un secret in chiaro oppure un JSON con una delle chiavi `token`, `botToken` o `slackBotToken`.

Il token non deve essere inserito nei cfg o nei log.

Il dispatcher legge il token tramite AWS Parameters and Secrets Lambda Extension. L'estensione conserva il valore in una cache locale per execution environment con TTL predefinito di 300 secondi, configurabile tramite il parametro CloudFormation `SlackSecretCacheTtlSeconds` tra 0 e 300. Le invocazioni servite dalla cache non effettuano una chiamata a Secrets Manager; allo scadere del TTL, la prima invocazione aggiorna il valore. Un nuovo execution environment esegue comunque il primo caricamento del secret.

La lettura avviene durante la fase `INVOKE`, attraverso l'endpoint locale `localhost:2773`. Il ruolo della Lambda deve quindi continuare a consentire `secretsmanager:GetSecretValue`. Non aggiungere una cache globale senza scadenza nel codice: impedirebbe di recepire la rotazione del token finche il container rimane attivo.

## 6. Configurazione delle route

Le route sono configurate in:

```text
runtime-infra/pn-warning-notifications-<env>-cfg.json
```

Formato:

```text
type,match,destination;type,match,destination
```

Campi:

| Campo | Valori | Significato |
| --- | --- | --- |
| `type` | `alarm`, `report` | Tipo di evento |
| `match` | token con lettere, numeri, `_` o `-` | Nome logico da riconoscere |
| `destination` | channel ID `C...` oppure `DROP` | Azione da eseguire |

Il dispatcher usa la prima route valida. L'ordine e quindi significativo quando piu match possono intercettare lo stesso evento.

### 6.1 Route verso Slack

```text
alarm,pn-my-service,C0123456789
report,pn-my-report,C0987654321
```

### 6.2 Soppressione con DROP

```text
alarm,pn-my-service,DROP
```

Quando viene selezionata una route `DROP`, il dispatcher:

1. non scarica allegati;
2. non legge il secret Slack;
3. non chiama Slack;
4. scrive un log JSON con `action=DROP`;
5. completa il record con successo;
6. non genera retry o messaggi in DLQ.

Esempio di log:

```json
{
  "action": "DROP",
  "eventType": "cloudwatch-alarm",
  "match": "pn-simulatore-recapiti",
  "alarmName": "oncall-pn-simulatore-recapiti-lambda-Errors",
  "producer": null,
  "environment": "dev"
}
```

Non rimuovere semplicemente la route per sopprimere un evento. Senza route il dispatcher termina con errore, SQS ritenta e infine sposta il messaggio in DLQ.

### 6.3 Configurazione DEV corrente

```json
{
  "Parameters": {
    "Routes": "alarm,pn-simulatore-recapiti,DROP;alarm,pn-Warning-Notification-Dispatcher,C0BJTGVC75F;report,pn-iam-unused-access-analyzer,C0BJKCXS3U3"
  }
}
```

In DEV gli allarmi del simulatore sono soppressi. Gli allarmi tecnici del dispatcher e i report IAM Access Analyzer continuano verso i rispettivi canali.

Per riattivare il simulatore basta sostituire `DROP` con il channel ID e rieseguire il post-deploy.

## 7. Routing degli allarmi

Per `type=alarm`, il dispatcher cerca `match` dentro `AlarmName` rispettando i confini delimitati da `-`.

La route:

```text
alarm,pn-simulatore-recapiti,C0123456789
```

intercetta sia:

```text
pn-simulatore-recapiti-db-CPU-High
oncall-pn-simulatore-recapiti-lambda-Errors
```

Il prefisso `oncall-` non viene rimosso dal payload.

### 7.1 Modifica dello stack producer

Lo stack deve ricevere `WarningSNSTopicArn`:

```yaml
Parameters:
  WarningSNSTopicArn:
    Type: String
```

Gli allarmi deviati devono usare esclusivamente questo topic:

```yaml
MyAlarm:
  Type: AWS::CloudWatch::Alarm
  Properties:
    AlarmName: !Sub '${ProjectName}-pn-my-service-Errors'
    AlarmActions:
      - !Ref WarningSNSTopicArn
    OKActions:
      - !Ref WarningSNSTopicArn
```

Per un frammento:

```yaml
MyLambdaAlarms:
  Type: AWS::CloudFormation::Stack
  Properties:
    TemplateURL: !Sub '${TemplateBucketBaseUrl}/fragments/lambda-alarms.yaml'
    Parameters:
      FunctionName: !Ref MyLambda
      AlarmSNSTopicArn: !Ref WarningSNSTopicArn
```

Il dispatcher riconosce payload SNS nativi di CloudWatch Alarm. Un evento EventBridge diretto non contiene `AlarmName` e richiede un normalizzatore oppure un nuovo matcher e renderer.

### 7.2 Presentazione Slack

Gli allarmi usano un attachment con Block Kit e barra laterale:

- `ALARM`: rosso;
- `OK`: verde;
- `INSUFFICIENT_DATA`: ambra;
- stato sconosciuto: grigio.

Il messaggio mostra una sola intestazione:

```text
pn-my-service-Errors

Stato:   ALARM
Regione: EU (Milan)
Env:     dev

Dettaglio: ...
CloudWatch: Apri allarme
```

Il link CloudWatch viene costruito usando regione e nome presenti nell'ARN dell'allarme.

### 7.3 Esempio Simulatore Recapiti

Nel repository `pn-simulatore-recapiti`, `WarningSNSTopicArn` viene passato agli allarmi ECS, Lambda, Aurora e agli allarmi CloudWatch relativi alle Step Functions.

Il servizio e soltanto un esempio di producer: qualsiasi altro stack puo usare lo stesso contratto.

## 8. Routing dei report

Per `type=report`, `match` deve essere uguale al campo `producer` dell'evento.

```text
report,pn-iam-unused-access-analyzer,C0987654321
```

### 8.1 Responsabilita del producer

Il producer deve:

1. produrre il riepilogo strutturato;
2. generare il CSV;
3. salvare il CSV nel proprio bucket S3;
4. generare una presigned URL HTTPS per `GetObject`;
5. pubblicare l'envelope JSON su `pn-WarningSnsTopic`;
6. pubblicare anche con conteggio zero quando e previsto un report per ogni esecuzione.

Il producer necessita di `s3:PutObject` e `sns:Publish`, ma non del bot token.

### 8.2 Presigned URL

Il client deve usare la regione corretta, SigV4 ed endpoint virtuale regionale:

```python
import os

import boto3
from botocore.config import Config

region = os.environ.get("AWS_REGION", "eu-south-1")
s3 = boto3.client(
    "s3",
    region_name=region,
    config=Config(
        signature_version="s3v4",
        s3={"addressing_style": "virtual"},
    ),
)

download_url = s3.generate_presigned_url(
    "get_object",
    Params={"Bucket": reports_bucket, "Key": report_key},
    ExpiresIn=3600,
)
```

La presigned URL evita policy `s3:GetObject` cross-account. Deve essere trattata come credenziale temporanea e non deve essere registrata nei log.

### 8.3 Envelope standard

```json
{
  "schemaVersion": "1.0",
  "eventId": "uuid",
  "eventType": "report",
  "producer": "pn-my-report",
  "eventName": "report-name",
  "occurredAt": "2026-07-22T08:07:18+00:00",
  "severity": "info",
  "environment": "dev",
  "data": {
    "accountRole": "core",
    "findingCount": 0,
    "findingTypeCounts": {}
  },
  "links": {
    "dashboard": "https://...",
    "report": "s3://bucket/key.csv"
  },
  "attachment": {
    "filename": "report.csv",
    "contentType": "text/csv",
    "size": 12345,
    "downloadUrl": "https://bucket.s3.eu-south-1.amazonaws.com/..."
  }
}
```

Il contenuto CSV non deve essere codificato Base64 nel messaggio SNS.

### 8.4 Renderer

L'envelope e comune, mentre `data` e specifico del report. Un nuovo report con campi diversi richiede un renderer nel dispatcher:

1. aggiungere `render_<report_name>`;
2. validare i campi specifici;
3. selezionarlo tramite `producer` e/o `eventName`;
4. riusare la gestione generica degli allegati;
5. aggiungere la route nel cfg;
6. eseguire il post-deploy.

Il renderer IAM corrente mostra:

```text
pn-iam-unused-access-analyzer

Finding: 521
Env:     DEV-CORE

Dettaglio per tipologia: ...
Dashboard CloudWatch: Apri dashboard
[CSV allegato]
```

Per il report confinfo l'etichetta e `DEV-CONFINFO`. L'account ID non viene mostrato.

### 8.5 CSV su Slack

Il dispatcher:

1. valida metadati, dimensione e hostname HTTPS AWS;
2. scarica il CSV dalla presigned URL;
3. usa `files.getUploadURLExternal` e `files.completeUploadExternal`;
4. pubblica un unico messaggio con blocchi e file;
5. usa `snippet_type=csv` fino a 1 MB per mostrare la preview;
6. allega un file normale tra 1 MB e 5 MiB;
7. oltre 5 MiB invia il riepilogo con avviso, senza allegato.

Se la URL e scaduta o il download fallisce, il report arriva comunque senza CSV e il dettaglio S3 viene scritto nei log.

### 8.6 Esempio IAM Access Analyzer

`pn-iam-unused-access-analyzer` genera un report per ogni esecuzione quando `ReportNotificationsEnabled=true`, anche con zero finding. Salva il CSV nel bucket locale, crea una presigned URL e pubblica sul topic core.

Il CSV rimane su S3 secondo la retention configurata anche se la consegna Slack fallisce.

## 9. Failure mode

| Caso | Comportamento |
| --- | --- |
| Route Slack valida | Invio al canale |
| Route `DROP` | Log e completamento senza notifica |
| Nessuna route | Retry SQS, poi DLQ |
| Slack non disponibile | Retry SQS |
| CSV oltre 5 MiB | Report senza allegato |
| CSV tra 1 MB e 5 MiB | Allegato senza preview snippet |
| Presigned URL non valida o scaduta | Report senza allegato |
| Stesso allarme su topic standard e warning | Due notifiche |

SQS offre consegna at-least-once. `eventId` permette di distinguere un retry da due esecuzioni reali del producer.

## 10. Test

### 10.1 Allarme verso Slack

1. Forzare `ALARM`.
2. Verificare barra rossa, campi e link CloudWatch.
3. Forzare `OK`.
4. Verificare barra verde.
5. Verificare che non arrivi nel workflow standard.

### 10.2 Allarme soppresso

1. Configurare `alarm,<match>,DROP` nell'ambiente.
2. Pubblicare un allarme corrispondente.
3. Verificare il log JSON `action=DROP`.
4. Verificare assenza su Slack.
5. Verificare che coda e DLQ siano vuote.

### 10.3 Report

1. Invocare una volta il producer.
2. Verificare CSV su S3.
3. Verificare `sns report sent`.
4. Verificare route, testo e CSV nel canale.
5. Ripetere con zero elementi.
6. Verificare preview sotto 1 MB e file normale sopra 1 MB.

## 11. Ordine di deploy

Per un nuovo ambiente:

1. deploy `infra-storage` core;
2. propagazione output verso confinfo;
3. deploy degli stack producer nella pipeline infra;
4. deploy delle route come primo step del post-deploy;
5. test end-to-end.

Nel breve intervallo tra infra e post-deploy, SQS conserva gli eventi gia pubblicati. La configurazione della route deve comunque essere inclusa nello stesso rilascio del producer o in un rilascio precedente.

Per cambiare channel ID o `DROP` e sufficiente aggiornare `pn-warning-notifications-<env>-cfg.json` ed eseguire il post-deploy.

## 12. Checklist

### Nuovo allarme

- [ ] `AlarmName` contiene un match stabile.
- [ ] Lo stack riceve `WarningSNSTopicArn`.
- [ ] `AlarmActions` e `OKActions` puntano solamente al topic desiderato.
- [ ] La route Slack o `DROP` esiste prima della pubblicazione.
- [ ] Sono stati testati `ALARM` e `OK`.

### Nuovo report

- [ ] Il producer salva il CSV su S3.
- [ ] La presigned URL usa regione corretta e SigV4.
- [ ] Il producer ha `sns:Publish`.
- [ ] L'envelope contiene i campi comuni.
- [ ] Il dispatcher ha un renderer per il report.
- [ ] La route esiste.
- [ ] Sono stati testati report vuoto, normale e oltre limite.

## 13. Riferimenti

- [AWS SNS Publish](https://docs.aws.amazon.com/sns/latest/api/API_Publish.html)
- [Slack chat.postMessage](https://docs.slack.dev/reference/methods/chat.postMessage/)
- [Slack files.getUploadURLExternal](https://docs.slack.dev/reference/methods/files.getUploadURLExternal/)
- [Slack files.completeUploadExternal](https://docs.slack.dev/reference/methods/files.completeUploadExternal/)
- [Slack file object e snippet](https://docs.slack.dev/reference/objects/file-object/)
- [Slack attachment colorati](https://docs.slack.dev/legacy/legacy-messaging/legacy-secondary-message-attachments/)
