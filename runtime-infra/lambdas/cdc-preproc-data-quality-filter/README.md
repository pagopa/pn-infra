# CDC Preprocessing Data Quality Processor

Lambda utilizzata come processor di Amazon Data Firehose per applicare controlli di Data Quality ai record CDC provenienti dalle tabelle DynamoDB.

La configurazione è centralizzata e consente di definire controlli differenti per ogni tabella senza inserire logiche specifiche direttamente nell'`index.py`.

## Struttura

```text
cdc-preproc-data-quality-filter/
├── __init__.py
├── index.py
├── README.md
├── processor/
│   ├── input_loader.py
│   ├── dq_executor.py
│   ├── payload_filter.py
│   └── ddb_utils.py
└── config/
    ├── manifest.yaml
    └── tables/
        ├── pn-user-attributes.yaml
        └── ...
```

## Flusso di elaborazione

Per ogni record ricevuto da Firehose, la Lambda:

1. decodifica il contenuto Base64;
2. recupera la tabella di origine dal campo `tableName`;
3. carica dal manifest la configurazione associata alla tabella;
4. seleziona l'immagine DynamoDB da controllare;
5. applica le eventuali regole di esclusione;
6. esegue i Data Quality check configurati;
7. determina il layer di destinazione;
8. applica i filtri previsti sul payload;
9. restituisce il record elaborato a Firehose.

## Selezione dell'immagine DynamoDB

I controlli vengono applicati alla prima immagine disponibile secondo la priorità definita nella configurazione:

```yaml
imageSelection:
  priority:
    - NewImage
    - OldImage
    - Keys
```

Comportamento atteso:

- `INSERT`: utilizzo di `NewImage`;
- `MODIFY`: utilizzo di `NewImage`;
- `REMOVE`: utilizzo di `OldImage`;
- assenza delle immagini: utilizzo di `Keys`.

La selezione viene gestita da `processor/ddb_utils.py`.

## Routing dei record

Il risultato dell'elaborazione determina il valore della partition key dinamica `PROCESSING_LAYER`.

| Layer | Descrizione |
|---|---|
| `clean` | Record che supera tutti i Data Quality check |
| `quarantine` | Record che non supera almeno un controllo |
| `excluded` | Record escluso esplicitamente tramite configurazione |
| `dropped` | Record appartenente a una tabella non configurata o disabilitata |
| `error` | Record non elaborabile a causa di un errore tecnico |

I record `clean`, `quarantine` ed `excluded` vengono restituiti a Firehose con risultato `Ok`.

Le tabelle non configurate vengono restituite con risultato `Dropped`.

Gli errori tecnici vengono restituiti con risultato `ProcessingFailed` e gestiti tramite l'`ErrorOutputPrefix` di Firehose.

## Manifest delle tabelle

Il file `config/manifest.yaml` contiene l'elenco delle tabelle abilitate e il riferimento alla relativa configurazione:

```yaml
version: 1.0

tables:
  pn-UserAttributes:
    enabled: true
    config: tables/pn-user-attributes.yaml
```

Per aggiungere una nuova tabella:

1. creare un nuovo file nella directory `config/tables`;
2. definire i controlli e i filtri specifici;
3. registrare la tabella nel `manifest.yaml`.

Non è necessario modificare l'`index.py` se i tipi di controllo richiesti sono già supportati da `dq_executor.py`.

## Configurazione della tabella

Ogni file presente in `config/tables` definisce il comportamento relativo a una singola tabella.

```yaml
version: 1.0

table: pn-UserAttributes

imageSelection:
  priority:
    - NewImage
    - OldImage
    - Keys

routing:
  cleanStatus: clean
  quarantineStatus: quarantine
  excludedStatus: excluded
```

Tutti i record elaborati provengono da DynamoDB CDC; non è quindi necessario specificare un `sourceType` nella configurazione.

## Esclusioni

La sezione `exclusions` individua i record che devono essere instradati direttamente nel layer `excluded`, senza eseguire i Data Quality check.

```yaml
exclusions:
  - name: excluded_pk_prefix
    type: starts_with_any
    field: pk
    values:
      - "VA#"
      - "VC#"
```

In questo esempio, i record con `pk` che inizia per `VA#` o `VC#` vengono instradati nel layer `excluded`.

## Data Quality check

La sezione `checks` contiene i controlli specifici della tabella:

```yaml
checks:
  - name: check_invalid_user_attributes
    description: User Attributes must be a Digital Domicile, Digital Address or Consent
    type: starts_with_any
    field: pk
    values:
      - "AB#"
      - "CO#"
    errorCode: DQ_INVALID_USER_ATTRIBUTES
```

Ogni controllo può utilizzare le seguenti proprietà:

| Proprietà | Descrizione |
|---|---|
| `name` | Nome identificativo del controllo |
| `description` | Descrizione funzionale |
| `type` | Tipo di controllo da eseguire |
| `field` / `fields` | Attributi DynamoDB interessati |
| `value` / `values` | Valori o prefissi attesi |
| `pattern` | Espressione regolare da verificare |
| `when` | Condizione per eseguire il controllo |
| `rules` | Regole applicate quando la condizione è soddisfatta |
| `errorCode` | Codice riportato nei log in caso di errore |

I nomi degli attributi sono case-sensitive e devono corrispondere esattamente a quelli presenti nelle immagini DynamoDB, ad esempio:

```text
pk
sk
created
lastModified
addresshash
accepted
```

## Controlli condizionali

I controlli condizionali vengono eseguiti soltanto quando la proprietà `when` è verificata.

```yaml
- name: check_addresshash_not_null
  description: AddressHash must not be null for Digital Domiciles and Addresses
  type: conditional
  when:
    field: pk
    operator: starts_with
    value: "AB#"
  rules:
    - type: required
      fields:
        - addresshash
  errorCode: DQ_ADDRESSHASH_NOT_NULL
```

In questo esempio, il controllo su `addresshash` viene eseguito soltanto per i record con `pk` che inizia per `AB#`.

## Tipi di controllo supportati

| Tipo | Descrizione |
|---|---|
| `required` | Verifica la presenza e la valorizzazione dei campi |
| `not_null` | Verifica che un campo sia valorizzato |
| `starts_with` | Verifica un singolo prefisso |
| `starts_with_any` | Verifica una lista di prefissi ammessi |
| `allowed_values` | Verifica che il valore sia tra quelli ammessi |
| `matches_regex` | Verifica il valore tramite espressione regolare |
| `conditional` | Applica una o più regole quando una condizione è soddisfatta |

L'aggiunta di un nuovo tipo di controllo richiede l'implementazione del relativo handler in `processor/dq_executor.py`.

## Errori Data Quality

Quando un record non supera uno o più controlli:

- viene assegnato al layer `quarantine`;
- viene restituito a Firehose con risultato `Ok`;
- gli `errorCode` vengono riportati nei log CloudWatch;
- il payload CDC non viene arricchito con attributi tecnici aggiuntivi.

Esempio di log:

```text
Data Quality checks failed.
RecordId=test-record-1,
TableName=pn-UserAttributes,
ImageSource=NewImage,
Errors=[
  {
    "code": "DQ_INVALID_USER_ATTRIBUTES",
    "check": "check_invalid_user_attributes"
  }
]
```

## Filtri sul payload

La sezione `filters` definisce le modifiche da applicare al payload dopo l'esecuzione dei Data Quality check.

```yaml
filters:
  - name: remove_addresshash
    type: remove_fields
    images:
      - NewImage
      - OldImage
    fields:
      - addresshash
    applyTo:
      - clean
      - quarantine
      - excluded
```

Il flusso è il seguente:

1. i controlli vengono eseguiti sul payload originale;
2. `addresshash` può essere utilizzato dai controlli;
3. dopo i controlli, `addresshash` viene rimosso da `NewImage` e `OldImage`;
4. il payload filtrato viene restituito a Firehose.

Il payload non viene modificato ulteriormente e non vengono aggiunti attributi tecnici.

## Responsabilità dei file

### `index.py`

Entry point della Lambda. Gestisce:

- ricezione e decodifica dei record Firehose;
- recupero della `tableName`;
- caricamento della configurazione;
- coordinamento dei controlli;
- applicazione dei filtri;
- assegnazione delle partition key;
- costruzione della risposta Firehose;
- contatori e log del batch.

### `processor/input_loader.py`

Gestisce:

- caricamento del `manifest.yaml`;
- individuazione della configurazione tramite `tableName`;
- caricamento del file specifico della tabella;
- cache delle configurazioni tra le invocazioni Lambda.

### `processor/dq_executor.py`

Gestisce:

- selezione dell'immagine DynamoDB;
- applicazione delle esclusioni;
- esecuzione dei Data Quality check;
- generazione degli `errorCode`;
- determinazione del layer `clean`, `quarantine` o `excluded`.

### `processor/payload_filter.py`

Applica al payload i filtri definiti nella configurazione dopo l'esecuzione dei controlli.

Attualmente supporta il filtro:

```yaml
type: remove_fields
```

### `processor/ddb_utils.py`

Contiene le funzioni comuni per:

- recuperare `NewImage`, `OldImage` o `Keys`;
- leggere i valori tipizzati DynamoDB;
- verificare la valorizzazione degli attributi;
- rimuovere gli attributi dalle immagini.

## Aggiunta di una nuova tabella

Per integrare una nuova tabella:

1. aggiungere la tabella al `manifest.yaml`;
2. creare il relativo file in `config/tables`;
3. definire la selezione dell'immagine;
4. definire routing, esclusioni, check e filtri;
5. verificare che i tipi di controllo utilizzati siano supportati da `dq_executor.py`.

```yaml
tables:
  pn-UserAttributes:
    enabled: true
    config: tables/pn-user-attributes.yaml
```

La Lambda carica automaticamente la configurazione corretta utilizzando il valore `tableName` presente nel payload CDC.