Passi per la gestione della redirect da notifichedigitali.it a www.notifichedigitali.it

__N.B.__: da definire in che Account AWS avverrà il deploy della soluzione.

# Generazione certificato
- Generare con la console ACM (Amazon Certificate Manager) un certificato per notifichedigitali.it 
  con validazione DNS.
- Chiedere al dipartimento di Engineering la creazione del DNS necessario alla validazione 
  del certificato. 
- Aspettare che ACM validi il certificato
- Copiare l'ARN del certificato servità successivamente.

# Installazione stack
1. Verificare che dall'account AWS designato sia utilizzabile una VPC con 
  - almeno tre subnet che possano essere raggiunte da internet;
  - un internet gateway
  Se tale VPC non è presente occorre crearla con un template funzionalmente 
  equivalente a minimal-vpc.yaml. 

2. Fare il deploy da console AWS CloudFormation del template global-accelerator-redirect.yaml
  - Nome dello stack: _landing-static-ip_
  - Parametro "CertificateArn": incollare l'ARN del certificato creato in precedenza
  - Parametro "ClientAffinity": lasciare default (_NONE_)
  - Parametro "DNSHostname": il valore del dominio a cui vengono ridirezionate le chiamate. In produzione 
    sarà _www.notifichedigitali.it_
  - Parametro "GlobalAccName": _static-ip-landing-&lt;EnvName&gt;_ dove &lt;EnvName&gt; è uno tra dev, svil, 
    coll, cert, hotifx, prod
  - Parametro "Subnets": lista separata da virgole degli id delle 3 sottoreti richieste al punto 1.
  - Parametro "VpcId": id della VPC richieste al punto 1.

3. Copiare l'output "AcceleratorIPAddresses".


# Configurazione Entry DNS
- Comunicare al dipartimento di Engineering gli indiriziz IP statici per definire l'entry DNS di tipo A
  per il dominio _notifichedigitali.it_



