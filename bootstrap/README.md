# Sistema di CI/CD

E' preso da un tutorial ed è ancora da perfezionare, in particolare
TODO: 
 - Aggiungere i test di integrazione ed ent-to-end, definire un meccanismo di promotion verso prod.
 - Implemntare i deploy verso regioni diverse da quelle di CI/CD
 
## Installazione
Al momento attuale l'installazione del sistema di CI/CD è fatta manualemnte dalla console di AWS
- I nomi dei file sono nella forma [Numero]\_[account]\_[descrizione]. 
  Il numero indica l'ordine di esecuzione; l'account indica in quale account AWS vanno creati o aggiornati 
  gli stack cloudformation contenuti nei file yaml.
- I file txt indicano come effettuare alcune semplici operazioni manuali

