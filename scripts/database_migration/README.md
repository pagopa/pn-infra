# Script Manutenzione del DB per ambienti di Test.

N.B: gli script presenti in questa directory non possono essere eseguiti più di uno alla volta e 
con una sola esecuzione con lo stesso filesystem. Questo perché i nomi dei file temporanei non sono 
randomizzati. E potrebbero anche coincidere tra script differenti.


## Rimuovere Notifiche che coinvolgono Persone Giuridiche
- remove_pg_recipients.sh

