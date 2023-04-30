#!/usr/bin/env bash -e


#set -Eeuo pipefail
#trap cleanup SIGINT SIGTERM ERR EXIT

cleanup() {
  trap - SIGINT SIGTERM ERR EXIT
  # script cleanup here
  echo "SIGINT SIGTERM ERR EXIT"
}

script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" &>/dev/null && pwd -P)


usage() {
      cat <<EOF
    Usage: $(basename "${BASH_SOURCE[0]}") [-h] [-v] -p <aws-profile-core> -P <aws-profile-confinfo> -r <aws-region> [-w <work-dir>]
    [-h]                      : this help message
    [-v]                      : print commands
    -p <aws-profile-core>     : aws cli profile pn-core
    -P <aws-profile-confinfo> : aws cli profile pn-confinfo
    -r <aws-region>           : aws region as eu-south-1
    [-w <work-dir>]           : folder for temporary files
EOF
  exit 1
}

parse_params() {
  # default values of variables set from params
  work_dir=$TMPDIR
  AWS_PROFILE=""
  AWS_REGION=""
  aws_profile_confinfo=""

  while :; do
    case "${1-}" in
    -h | --help) usage ;;
    -v | --verbose) set -x ;;
    -p) 
      AWS_PROFILE="${2-}"
      shift
      ;;
    -r | --region) 
      AWS_REGION="${2-}"
      shift
      ;;
    -w | --work-dir) 
      work_dir="${2-}"
      shift
      ;;
    -P) 
      aws_profile_confinfo="${2-}"
      shift
      ;;
    -?*) die "Unknown option: $1" ;;
    *) break ;;
    esac
    shift
  done

  args=("$@")

  # check required params and arguments
  [[ -z "${AWS_REGION-}" ]] && usage
  [[ -z "${AWS_PROFILE-}" ]] && usage
  [[ -z "${aws_profile_confinfo-}" ]] && usage
  return 0
}

dump_params(){
  echo ""
  echo "######      PARAMETERS      ######"
  echo "##################################"
  echo "Work directory:         ${work_dir}"
  echo "AWS region:             ${AWS_REGION}"
  echo "AWS profile core:       ${AWS_PROFILE}"
  echo "AWS profile confinfo:   ${aws_profile_confinfo}"
}

# START SCRIPT

parse_params "$@"
dump_params




delete_some_records() {
  DYNAMO_TABLE="$1"
  KEY_LIST="$2"

  echo "Delete some records from table $DYNAMO_TABLE"
  date

  if ( [ "key" == "$KEY_LIST" ]) then
    aws --profile "$AWS_PROFILE" --region "$AWS_REGION" \
        dynamodb scan \
        --table-name "$DYNAMO_TABLE" \
        --projection-expression "#c" \
        --expression-attribute-names '{"#c":"'$KEY_LIST'"}' \
        --max-items 50000 \
      > "$work_dir/deletion_keys.json"
  else
    aws --profile "$AWS_PROFILE" --region "$AWS_REGION" \
        dynamodb scan \
        --table-name "$DYNAMO_TABLE" \
        --projection-expression "$KEY_LIST" \
        --max-items 50000 \
      > "$work_dir/deletion_keys.json"
  fi

  cat "$work_dir/deletion_keys.json" | jq -r ".Items[] | {\"DeleteRequest\": {\"Key\": . }} | tojson" \
      | jq --slurp -r ' _nwise(25) | { "'${DYNAMO_TABLE}'": . } | tojson' \
      > "$work_dir/deletion_list.json"


  nrows=$(cat "$work_dir/deletion_list.json" | wc -l)
  for (( n=1; n<=${nrows}; n++ )); do
    cat "$work_dir/deletion_list.json" | head -n $n | tail -1 > "$work_dir/deletion_command.json"
    
    echo "########## $DYNAMO_TABLE step $n of $nrows"
    aws --profile "$AWS_PROFILE" --region "$AWS_REGION" \
        dynamodb batch-write-item --request-items file://$work_dir/deletion_command.json
  done

  date
}


delete_some_records "pn-NotificationsMetadata" "iun_recipientId,sentAt"

delete_some_records "pn-Notifications" "iun"

delete_some_records "pn-NotificationsCost" "creditorTaxId_noticeCode"

delete_some_records "pn-NotificationsQR" "aarQRCodeValue"

delete_some_records "pn-NotificationDelegationMetadata" "iun_recipientId_delegateId_groupId,sentAt"

delete_some_records "pn-DocumentCreationRequestTable" "key"

delete_some_records "pn-Timelines" "iun,timelineElementId"

delete_some_records "pn-TimelinesForInvoicing" "paId_invoicingDay,invoincingTimestamp_timelineElementId"

delete_some_records "pn-Mandate" "pk,sk"

delete_some_records "pn-MandateHistory" "pk,sk"

delete_some_records "pn-UserAtttributes" "pk,sk"

delete_some_records "pn-Action" "actionId"

delete_some_records "pn-FutureAction" "timeSlot,actionId"

delete_some_records "pn-PaperNotificationFailed" "recipientId,iun"

delete_some_records "pn-PaperEvents" "pk,sk"

delete_some_records "pn-PaperAddress" "requestId,addressType"

delete_some_records "pn-PaperRequestDelivery" "requestId"

delete_some_records "pn-PaperRequestError" "requestId,created"

delete_some_records "pn-ProgressionSensorData" "entityName_type_relatedEntityId,id"

delete_some_records "pn-radd-transaction" "operationId,operationType"

delete_some_records "pn-operations-iuns" "id"

delete_some_records "pn-WebhookEvents" "hashKey,sortKey"

delete_some_records "pn-batchPolling" "batchId"

delete_some_records "pn-batchRequests" "correlationId"





AWS_PROFILE="${aws_profile_confinfo}"

delete_some_records "pn-ConfidentialObjects" "hashKey,sortKey"

delete_some_records "pn-SsDocumenti" "documentKey"

