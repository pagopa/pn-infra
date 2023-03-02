## Check Rate Limit Api-Gw

this script test the rate limit of api-gwi by using curl command, the rate limit (rate + burst) must be edited outside this script.

The script must be executed with the fllowing parameters:

`./checkrateapigw.sh -e <env-type> -d <test-tax-id> -k <api-key> -t <time-curl>`

where:
- env-type is the envinroment that will be pointed to by the script, passed in the url
- test-tax-id is the fiscal code passed in the header
- api-key is the ApiKey passed in the header
- time-curl is the time between one curl and the next 
