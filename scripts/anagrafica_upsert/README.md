# dynamo_db_load_batch

Script di inserimento anagrafiche SEND a partire da dump DynamoDB versionati su pn-configuration

## Tabella dei Contenuti

- [Descrizione](#descrizione)
- [Installazione](#installazione)
- [Utilizzo](#utilizzo)

## Descrizione

Lo Script cerca il file con la seguente logica:
- se withSecretValues è presente:
    - cerca prima in {configPath}/<envName>/_conf/<accountName>/dynamodb/<tableName>-secrets.json
    - se non viene trovato, cerca nella cartella global di pn-configuration, ossia {configPath}/_conf/<accountName>/dynamodb/<tableName>-secrets.json
- se withSecretValues non è presente:
    - cerca prima in {configPath}/<envName>/_conf/<accountName>/dynamodb/<tableName>.json
    - se non viene trovato, cerca nella cartella global di pn-configuration, ossia {configPath}/_conf/<accountName>/dynamodb/<tableName>.json

Nota: <accountName> viene recuperato dal file config.json presente nella root di questo script che associa il nome della tabella all'account "core" o "confinfo".

Per le righe dei file "-secrets.json", il file config.json determina su quali di queste ci si aspetta un secret in base alle condizioni "Key" e su quali attributi (si assume che siano tutti di tipo "String"). I secret, essendo risolti tramite AWS Secrets Manager, sono codificati con "<secret:{SecretName}>"; se lo script non rileva questa sintassi nel valore dell'attributo, solleva un'eccezione.

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
node Usage: index.js --envName <envName> --tableName <tableName> --configPath <configPath> [--batchDimension <batchDimension>] [--withSecretsValues]
```
Dove:
- `<envName>` è il nome dell'ambiente sul quale eseguire l'operazione
- `<tableName>` è la tabella in cui vengono inseriti i dati
- `<configPath>` è il path locale dove è stato scaricato il repository pn-configuration
- `<withSecretsValues>` se impostato, attiva la procedura di import elementi di anagrafica che contengono valori segreti
- `<batchDimension>` è la dimensione del batch che si vuole sottomettere (default:25)

