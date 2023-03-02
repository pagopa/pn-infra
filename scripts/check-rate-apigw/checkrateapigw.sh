#!/bin/bash

echo "insert apy key:"

read curlapi

echo "the entered api-key is $curlapi"

echo "insert time  between one curl and the next (es. 1 for 1 seconds or 0.01 for 10 milliseconds):"

read curltime

echo "the entered time between curl is $curltime"

apikey="x-api-key: $curlapi"


while true;

do 

curl  --request GET \
  --url 'https://api-io.hotfix.pn.pagopa.it/delivery/notifications/received/GEZG-TQPH-TPAQ-202303-D-1' \
  --header 'Content-Type: application/json' \
  --header "$apikey" \
  --header 'x-pagopa-cx-taxid: FRMTTR76M06B715E' \
  --data '{}' >>  output.txt  && echo >> output.txt;

sleep $timecurl;

done
