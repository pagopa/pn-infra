#! /bin/bash

if ( [ $# -ne 5 ] ) then
  echo "This script create or renew a certificate for a server domain name"
  echo "Usage: $0 <domain-name> <zone> <profile> <certificate-region> <zone-region>"
  echo "<domain-name> last domain part; for example pa, cittadini, api, webapi, ..."
  echo "<zone>: pn.pagopa.it, beta.pn.pagopait, uat.pn.pagopa.it, ...."
  echo ""
  echo "This script require following executable configured in the PATH variable:"
  echo " - aws cli 2.0 "
  echo " - jq"
  echo " - sha256"

  if ( [ "$BASH_SOURCE" = "" ] ) then
    return 1
  else
    exit 1
  fi
fi

domainName=$1
zoneName=$2
profile=$3
certificateRegion=$4
zoneRegion=$5

fullDomain="${domainName}.${zoneName}"


certificateArn=$( aws acm --profile $profile --region $certificateRegion list-certificates \
    | jq ".CertificateSummaryList[] | select(.DomainName==\"${fullDomain}\") | .CertificateArn" )

if ( [ "" = "$certificateArn" ] ) then
  echo "Do not exist a certificate for $fullDomain, require one"
  aws acm --profile $profile --region $certificateRegion request-certificate \
        --domain-name $fullDomain \
        --validation-method DNS

  echo "Give 5 second to request creation"
  sleep 5

  certificateArn=$( aws acm --profile $profile --region $certificateRegion list-certificates \
    | jq ".CertificateSummaryList[] | select(.DomainName==\"${fullDomain}\") | .CertificateArn" )
  if ( [ "" = "$certificateArn" ] ) then
    echo "!!!! CANNOT CREATE A CERTIFICATE REQUEST"

    if ( [ "$BASH_SOURCE" = "" ] ) then
      return 1
    else
      exit 1
    fi
  fi
fi

# clean " character derived from json representation
certificateArn=$( echo $certificateArn | tr -d '"' )

echo ""
echo "Certificate for ${fullDomain} has ARN ${certificateArn}"

certificateDescription=$( aws acm --profile $profile --region $certificateRegion describe-certificate \
                                  --certificate-arn $certificateArn )

echo "Certificate Description"
echo "$certificateDescription"

certificateStatus=$( echo "$certificateDescription" | jq '.Certificate.Status' | tr -d '"' )

echo "Certificate status = $certificateStatus"


if ( [ "PENDING_VALIDATION" = "$certificateStatus" ] ) then
  echo "Certificate needs validation"
  validationDnsName=$( echo "$certificateDescription" | jq '.Certificate.DomainValidationOptions[0].ResourceRecord.Name' | tr -d '"' )
  validationDnsType=$( echo "$certificateDescription" | jq '.Certificate.DomainValidationOptions[0].ResourceRecord.Type' | tr -d '"' )
  validationDnsValue=$( echo "$certificateDescription" | jq '.Certificate.DomainValidationOptions[0].ResourceRecord.Value' | tr -d '"' )

  echo "validation needs DNS entry"
  echo " - Name: $validationDnsName"
  echo " - Type: $validationDnsType"
  echo " - Value: $validationDnsValue"

  echo -e "{ \"Changes\": [{ \n"\
       "    \"Action\": \"CREATE\", \n"\
       "    \"ResourceRecordSet\": { \n"\
       "        \"Name\": \"${validationDnsName}\",\n"\
       "        \"Type\": \"${validationDnsType}\",\n"\
       "        \"TTL\": 300,"\
       "        \"ResourceRecords\": [{ \"Value\": \"${validationDnsValue}\"}] \n"\
       "    }\n"\
       "}]}" \
        > /tmp/route53RecordSetChanges.json

  echo "DNS Record change request"
  cat /tmp/route53RecordSetChanges.json | jq

  echo "Look for hosted zone id"
  hostedZoneId=$( aws --profile $profile --region $zoneRegion route53 list-hosted-zones-by-name \
             --dns-name ${zoneName} | jq ".HostedZones[] | select(.Name==\"${zoneName}.\") | .Id"\
              | sed -e 's|/hostedzone/||' | tr -d '"')
  if ( [ "" = "$hostedZoneId" ] ) then
    echo "Hosted zone not found"
    if ( [ "$BASH_SOURCE" = "" ] ) then
      return 1
    else
      exit 1
    fi
  fi
  echo "hosted zone Id: $hostedZoneId"

  echo "Create DNS records for validation"
  aws --profile $profile --region $zoneRegion route53 change-resource-record-sets \
      --hosted-zone-id "${hostedZoneId}" --change-batch file:///tmp/route53RecordSetChanges.json

  echo "Wait for Automatic Validation"
  certificateStatus=$( echo "$certificateDescription" | jq -r '.Certificate.Status' )
  counter=1
  while ( [  "$certificateStatus" != "ISSUED" -a $counter -lt 30 ] )
  do
    sleep 2
    echo -n "."
    counter=$[ $counter + 1 ]
    certificateDescription=$( aws acm --profile $profile --region $certificateRegion describe-certificate \
                                  --certificate-arn $certificateArn )
    certificateStatus=$( echo "$certificateDescription" | jq -r '.Certificate.Status' )
  done
  echo ""
  echo "Certificate status = $certificateStatus"
fi


