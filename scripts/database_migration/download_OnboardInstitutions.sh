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
    Usage: $(basename "${BASH_SOURCE[0]}") [-h] [-v] -p <aws-profile> -r <aws-region> [-w <work-dir>] [--table-name]
    [-h]                    : this help message
    [-v]                    : print commands
    -p <aws-profile>        : aws cli profile
    -r <aws-region>         : aws region as eu-south-1
    [-w <work-dir>]         : folder for temporary files
    [--table-name]          : Table to be copied
EOF
  exit 1
}

parse_params() {
  # default values of variables set from params
  work_dir=$TMPDIR
  aws_profile=""
  aws_region=""
  table_name="pn-OnboardInstitutions"

  while :; do
    case "${1-}" in
    -h | --help) usage ;;
    -v | --verbose) set -x ;;
    -p) 
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
    --table-name)
      table_name="${2-}"
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
  [[ -z "${table_name-}" ]] && usage
  return 0
}

dump_params(){
  echo ""
  echo "######      PARAMETERS      ######"
  echo "##################################"
  echo "Work directory:             ${work_dir}"
  echo "AWS region:                 ${aws_region}"
  echo "AWS profile:                ${aws_profile}"
  echo "Nome tabella:               ${table_name}"
}

# START SCRIPT

parse_params "$@"
dump_params

echo ""
echo ""
echo "===                          DUMP pn-OnboardInstitutions                          ==="
echo "====================================================================================="

aws --profile "$aws_profile" --region "$aws_region" \
        dynamodb scan \
        --table-name "$table_name" \
        --max-items 50000 \
      | jq -r '.Items | .[] | tojson' \
      > "OnboardInstitutions_dump.json"

itemsKeys="id $( cat "OnboardInstitutions_dump.json" | jq -r 'keys[]' | sort -u | grep -v "id" )"

jqExpression="{"
for key in $itemsKeys ; do
  jqExpression="$jqExpression \"$key\": .$key,"
done
jqExpression=$( echo $jqExpression | sed -e 's/,$/ } | tojson/')

echo " = Reorder dumped object keys with jq expression"
echo "   $jqExpression"
jq -r "$jqExpression" "OnboardInstitutions_dump.json" \
   > "OnboardInstitutions_dump.json.tmp"
mv "OnboardInstitutions_dump.json.tmp" "OnboardInstitutions_dump.json"

echo " = Dumped Institutions: "$( cat "OnboardInstitutions_dump.json" | wc -l)

