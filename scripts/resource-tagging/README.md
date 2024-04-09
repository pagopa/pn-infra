# resource_tagging

Script per assegnare i cost allocation tags alle risorse AWS create.

## Tabella dei Contenuti

- [Descrizione](#descrizione)
- [Installazione](#installazione)
- [Utilizzo](#utilizzo)

## Descrizione

Lo script costruisce una lista di risorse cloudformation a partire dal nome del microservizio, scorrendo ricorsivamente le risorse da due radici:
- {microserviceName}-storage-{envName}
- {microserviceName}-microsvc-{envName}

Per ogni risorsa la cui **ResourceType** sia diversa da `AWS::CloudFormation::Stack` e dalla lista **IGNORED_RESOURCE_TYPES** in `const.js`, viene generato l'ARN e la lista dei tags da associare; successivamente viene eseguita la chiamata ad AWS per taggare la risorsa.

Nel caso in cui il **microserviceName** non venga fornito in input allo script, questo userà la lista definita nella costante **ALL_MICROSERVICES** in `const.js`. La lista dei servizi da utilizzerà dipenderà dal valore del parametro **accontType** (core o confinfo).

Il file `resource-tags.json` contiene i tag da assegnare di default a tutte le risorse e può essere ulteriormente personalizzato se si vogliono aggiungere dei tag specifici in base una certa resource type. Sarà sufficiente aggiungere una chiave con il nome della risorsa Cloudformation e la mappa dei tag.

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
node Usage: index.js --envName <envName> --accountType <accountType> [--region <region>] [--microserviceName <microserviceName>] 
```

Dove:
- `<envName>` è il nome dell'ambiente sul quale eseguire l'operazione
- `<accountType>` è l'account su cui operare: core o confinfo
- `<region>` è la region AWS, di default "eu-south-1"
- `<microserviceName>` da valorizzare con il nome del microservizio, ad es. pn-delivery; se non viene passato, lo script utilizza la lista di microservizi per account type in const.js

