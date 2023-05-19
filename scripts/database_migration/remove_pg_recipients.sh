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
    Usage: $(basename "${BASH_SOURCE[0]}") [-h] [-v] -p <aws-profile> -r <aws-region> [-w <work-dir>] [--notification-table] [--metadata-table]
    [-h]                    : this help message
    [-v]                    : print commands
    -p <aws-profile>        : aws cli profile (optional)
    -r <aws-region>         : aws region as eu-south-1
    [-w <work-dir>]         : folder for temporary files
    [--notification-table]  : Notifications table name
    [--metadata-table]      : NotificationsMetadata table name
EOF
  exit 1
}

parse_params() {
  # default values of variables set from params
  work_dir=$TMPDIR
  aws_profile=""
  aws_region=""
  NotificationsMetadataTableName="pn-NotificationsMetadata"
  NotificationsTableName="pn-Notifications"

  while :; do
    case "${1-}" in
    -h | --help) usage ;;
    -v | --verbose) set -x ;;
    -p | --profile) 
      aws_profile="${2-}"
      shift
      ;;
    -r | --region) 
      aws_region="${2-}"
      shift
      ;;
    -w | --work-dir) 
      work_dir="${2-}"
      shift
      ;;
    --notification-table)
      NotificationsTableName="${2-}"
      shift
      ;;
    --metadata-table)
      NotificationsMetadataTableName="${2-}"
      shift
      ;;
    -?*) die "Unknown option: $1" ;;
    *) break ;;
    esac
    shift
  done

  args=("$@")

  # check required params and arguments
  [[ -z "${aws_region-}" ]] && usage
  [[ -z "${aws_profile-}" ]] && usage
  return 0
}

dump_params(){
  echo ""
  echo "######      PARAMETERS      ######"
  echo "##################################"
  echo "Work directory:             ${work_dir}"
  echo "AWS region:                 ${aws_region}"
  echo "AWS profile:                ${aws_profile}"
  echo "Nome tabella Notification:  ${NotificationsTableName}"
  echo "Nome tabella Metadati:      ${NotificationsMetadataTableName}"
}

# START SCRIPT

parse_params "$@"
dump_params


echo "=== Base AWS command parameters"
aws_command_base_args="--output json"
if ( [ ! -z "${aws_profile}" ] ) then
  aws_command_base_args="${aws_command_base_args} --profile $aws_profile"
fi
if ( [ ! -z "${aws_region}" ] ) then
  aws_command_base_args="${aws_command_base_args} --region  $aws_region"
fi


echo "===                        SEARCH FOR IUN TO BE REMOVED                        ==="
echo "=================================================================================="

echo "=== Query NotificationMetadataTable"
aws $aws_command_base_args \
    dynamodb scan \
      --table-name "$NotificationsMetadataTableName" \
      --index-name "recipientId" \
      --filter-expression "begins_with( recipientId_creationMonth , :recId )" \
      --expression-attribute-values '{ ":recId" : {"S":"PG-" }}' \
      --projection-expression "tableRow.iun,recipientId_creationMonth,recipientIds,sentAt" \
      --max-items 50000 \
  | tee  "$work_dir/iun_with_PG_recipients.json"


echo "=== Prepare deletion for metadata"
cat "$work_dir/iun_with_PG_recipients.json" \
    | jq -r '.Items | .[] | { "iun": .tableRow.M.iun.S, "sentAt": .sentAt.S, "recIds": (.recipientIds.L | map( .S )) } | tojson ' \
    | tee "$work_dir/NotificationMetadata_deletion_keys_step_01.json" \
    | jq -r '. as $all | .recIds[] | { "recId": ., "iun": $all.iun, "sentAt": $all.sentAt } | tojson' \
    | tee "$work_dir/NotificationMetadata_deletion_keys_step_02.json" \
    | jq -r '{ "iun_recipientId": { "S": (.iun + "##" + .recId) }, "sentAt": { "S": .sentAt } }' \
    | tee "$work_dir/NotificationsMetadata_deletion_keys.json"


echo "=== Extract IUNs"
cat "$work_dir/iun_with_PG_recipients.json" \
    | jq '.Items | .[] | .tableRow.M.iun.S' \
    | sort -u \
    | jq -r '{ "iun": {"S": . }}' \
    | tee "$work_dir/Notifications_deletion_keys.json"




# Funzione per cancellare un set di chiavi da una tabella
function deleteFromOneTable() {
  tableName=$1
  keySet=$2

  echo "= prepare deletion commands list"
  cat "$keySet" \
    | jq -r ". | {\"DeleteRequest\": {\"Key\": . }} | tojson" \
    | jq --slurp -r ' _nwise(25) | { "'$tableName'": . } | tojson' \
    > "$work_dir/delete_list.json"


  nrows=$(cat $work_dir/delete_list.json | wc -l)
  echo "$nrows deletions needed"
  for (( n=1; n<=${nrows}; n++ )); do
    cat "$work_dir/delete_list.json" | head -n $n | tail -1 > "$work_dir/delete_command.json"
    
    echo "########## $tableName step $n of $nrows"
    aws $aws_command_base_args \
        dynamodb batch-write-item --request-items "file://$work_dir/delete_command.json"
  done
}


echo ""
echo ""
echo "===                           DELETE NOTIFICATIONS                             ==="
echo "=================================================================================="
deleteFromOneTable $NotificationsTableName "$work_dir/Notifications_deletion_keys.json"

echo ""
echo ""
echo "===                       DELETE NOTIFICATIONS METADATA                        ==="
echo "=================================================================================="
deleteFromOneTable $NotificationsMetadataTableName "$work_dir/NotificationsMetadata_deletion_keys.json"

