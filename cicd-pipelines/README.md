# Sistema di CI/CD

E' preso da un tutorial ed è ancora da perfezionare, in particolare
TODO: 
 - DevAccount va rimosso, nel nostro caso d'uso i repository sorgente sono su GitHub
 - Rinominare TestAccount in BetaAccount
 - Rinominare ToolsAccount in CicdAccount
 - Aggiungere i test di integrazione ed ent-to-end, definire un meccanismo di promotion verso prod.
 - Implemntare i deploy verso regioni diverse da quelle di CI/CD
 
## Installazione
Al momento attuale l'installazione del sistema di CI/CD è fatta manualemnte dalla console di AWS
- Creare lo stack cloudformation ToolsAcct/pre-reqs.yaml con l'account di CI/CD
- Segnarsi gli output di tale stack perché saranno parametri di tutti gli stack successivi
- Creare lo stack cloudformation DevAccount/toolsacct-codepipeline-codecommit.yaml con l'account di CI/CD
- Creare lo stack cloudformation TestAccount/toolsacct-codepipeline-cloudformation-deployer.yaml con l'account di Beta
- Creare lo stack cloudformation ToolsAcct/toolsacct-codepipeline-codecommit.yaml con l'account di CI/CD. Il parametro CrossAccountCondition deve essere "false".
- Aggiornare lo stack creato al passo precedente aggiornando il parametro CrossAccountCondition da false a true.

