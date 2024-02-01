# dynamo_db_load_batch

Script di inserimento anagrafiche SEND a partire da dump DynamoDB versionati su pn-configuration

## Tabella dei Contenuti

- [Descrizione](#descrizione)
- [Installazione](#installazione)
- [Utilizzo](#utilizzo)

## Descrizione

Lo Script cerca il file con la seguente logica:
    - cerca prima in {configPath}/<envName>/_conf/<accountName>/dynamodb/<tableName>.json
- se non viene trovato, cerca nella cartella global di pn-configuration, ossia {configPath}/_conf/<accountName>/dynamodb/<tableName>.json

Nota: <accountName> viene recuperato dal file config.json presente nella root di questo script che associa il nome della tabella all'account "core" o "confinfo".

## Installazione

```bash
npm install
```

## Utilizzo
### Step preliminare

```bash
aws sso login --profile <profile>
```

### Esecuzione
```bash
node Usage: index.js --envName <envName> --tableName <tableName> --configPath <configPath> [--batchDimension <batchDimension>] [--withRole <withRole>]
```
Dove:
- `<envName>` è il nome dell'ambiente sul quale eseguire l'operazione
- `<tableName>` è la tabella in cui vengono inseriti i dati
- `<configPath>` è il path locale dove è stato scaricato il repository pn-configuration
- `<batchDimension>` è la dimensione del batch che si vuole sottomettere (default:25)
- `<withRole>` se impostato, il comando viene eseguito con il ruolo di default AWS

