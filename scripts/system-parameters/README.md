# Increase doc retention

Script che esegue una serie di comandi relativi ai parametri memorizzati nel Parameter Store.

## Tabella dei Contenuti

- [Descrizione](#descrizione)
- [Installazione](#installazione)
- [Utilizzo](#utilizzo)

## Descrizione

### Comando "Dump"
Scarica i parametri di un ambiente nella cartella di destinazione indicata come input.

### Comando "Compare"
Confronta i parametri di un ambiente con i valori presenti su AWS. E' necessario eseguire prima il "dump".

### Configurazione
Lo script supporta anche una configurazione in json che prevede il parametro "skipParameters" per evitare di fare dump/compare di specifici parametri.

### Naming convention
Ogni parametro viene memorizzato in un file che avrà la seguente convenzione:
- gli "slash" vengono sostituiti da "#"
- se il Tier del parametro è "Advanced" viene aggiunto al nome del parametro la seguente stringa: "##A##"

Ad. es un parametro Advanced con con nome /abc/def sarà memorizato in un file con nome `#abc#def##A##.param`

## Installazione

```bash
npm install
```

## Utilizzo
### Step preliminare

```bash
aws sso login --profile sso_pn-core-<env>
```

### Esecuzione
```bash  
node index.js --envName <envName> --cmd <cmd> --configPath <configPath>
```
Dove:
- `<envName>` è l'environment si intende eseguire la procedura;
- `<cmd>` è il nome del comando da eseguire ("dump" o "compare");
- `<configPath>` è il path della cartella pn-configuration dove vengono memorizzati i dump dei parametri affinché vengano tenuti sotto controllo di configurazione.
