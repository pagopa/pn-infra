#!/bin/bash

echo insert apy key:

read curlapi

echo the entered api-key is $curlapi

apikey="x-api-key: $curlapi"

while true;

do 

curl  --request GET \
  --url 'https://api-io.hotfix.pn.pagopa.it/delivery/notifications/received/GEZG-TQPH-TPAQ-202303-D-1' \
  --header 'Content-Type: application/json' \
  --header "$apikey" \
  --header 'x-pagopa-cx-taxid: FRMTTR76M06B715E' \
  --data '{}' >>  output.txt && echo $(date +"%T.%N") >> output.txt  && echo >> output.txt;

sleep 0.001;

done
