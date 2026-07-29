#!/usr/bin/env bash
set -euo pipefail

# OpenSearch connection settings
OPENSEARCH_HOST="${OPENSEARCH_HOST:-localhost}"
OPENSEARCH_PORT="${OPENSEARCH_PORT:-5601}"
OPENSEARCH_SCHEME="${OPENSEARCH_SCHEME:-http}"
MASTER_USER="${MASTER_USER:-master1}"
MASTER_PASSWORD="${MASTER_PASSWORD:-${MASTER:-}}"
READER_PASSWORD="${READER_PASSWORD:-}"
WRITER_PASSWORD="${WRITER_PASSWORD:-}"
INSECURE_SSL="${INSECURE_SSL:-true}"
ENVIRONMENT="${ENVIRONMENT:-prod}"

usage() {
  cat <<'EOF'
Usage: init-opensearch-env.sh [options]

Options:
  -e, --environment <prod|test>   Target environment (default: prod)
      --host <host>               OpenSearch host (default: localhost)
      --port <port>               OpenSearch port (default: 5601)
      --scheme <http|https>       OpenSearch scheme (default: http)
      --master-user <user>        Master username (default: master)
      --master-password <pwd>     Master password
      --reader-password <pwd>     Reader user password
      --writer-password <pwd>     Writer user password
      --insecure                  Disable TLS verification (default)
      --secure                    Enable TLS verification
  -h, --help                      Show this help

You can also pass values via env vars:
  MASTER_PASSWORD (or MASTER), READER_PASSWORD, WRITER_PASSWORD,
  OPENSEARCH_HOST, OPENSEARCH_PORT, OPENSEARCH_SCHEME, MASTER_USER, ENVIRONMENT.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    -e|--environment)
      ENVIRONMENT="$2"
      shift 2
      ;;
    --host)
      OPENSEARCH_HOST="$2"
      shift 2
      ;;
    --port)
      OPENSEARCH_PORT="$2"
      shift 2
      ;;
    --scheme)
      OPENSEARCH_SCHEME="$2"
      shift 2
      ;;
    --master-user)
      MASTER_USER="$2"
      shift 2
      ;;
    --master-password)
      MASTER_PASSWORD="$2"
      shift 2
      ;;
    --reader-password)
      READER_PASSWORD="$2"
      shift 2
      ;;
    --writer-password)
      WRITER_PASSWORD="$2"
      shift 2
      ;;
    --insecure)
      INSECURE_SSL="true"
      shift
      ;;
    --secure)
      INSECURE_SSL="false"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "ERROR: unknown option: $1"
      usage
      exit 1
      ;;
  esac
done

if [[ "${ENVIRONMENT}" != "prod" && "${ENVIRONMENT}" != "test" ]]; then
  echo "ERROR: --environment must be 'prod' or 'test'"
  exit 1
fi

read_secret_if_missing() {
  local var_name="$1"
  local prompt="$2"

  if [[ -z "${!var_name}" ]]; then
    if [[ -t 0 ]]; then
      read -r -s -p "${prompt}: " "$var_name"
      echo
      export "$var_name"
    else
      echo "ERROR: missing ${var_name}. Pass it via CLI option or env var."
      exit 1
    fi
  fi
}

read_secret_if_missing "MASTER_PASSWORD" "Enter MASTER_PASSWORD"
read_secret_if_missing "READER_PASSWORD" "Enter READER_PASSWORD"
read_secret_if_missing "WRITER_PASSWORD" "Enter WRITER_PASSWORD"

if [[ -z "${MASTER_PASSWORD}" ]]; then
  echo "ERROR: missing MASTER_PASSWORD (or MASTER) environment variable"
  exit 1
fi

if [[ -z "${READER_PASSWORD}" ]]; then
  echo "ERROR: missing READER_PASSWORD environment variable"
  exit 1
fi

if [[ -z "${WRITER_PASSWORD}" ]]; then
  echo "ERROR: missing WRITER_PASSWORD environment variable"
  exit 1
fi

BASE_URL="${OPENSEARCH_SCHEME}://${OPENSEARCH_HOST}:${OPENSEARCH_PORT}"
CURL_SSL_ARGS=()
if [[ "${INSECURE_SSL}" == "true" ]]; then
  CURL_SSL_ARGS=(-k)
fi

call_api() {
  local name="$1"
  local method="$2"
  local path="$3"
  local payload="${4:-}"
  local tried_https_fallback="false"

  echo "\n==> ${name}"

  local response
  local http_code
  local body

  while true; do
    if [[ -n "${payload}" ]]; then
      response=$(curl -sS "${CURL_SSL_ARGS[@]}" \
        -u "${MASTER_USER}:${MASTER_PASSWORD}" \
        -H "Content-Type: application/json" \
        -X "${method}" \
        "${BASE_URL}${path}" \
        -d "${payload}" \
        -w "\n%{http_code}")
    else
      response=$(curl -sS "${CURL_SSL_ARGS[@]}" \
        -u "${MASTER_USER}:${MASTER_PASSWORD}" \
        -H "Content-Type: application/json" \
        -X "${method}" \
        "${BASE_URL}${path}" \
        -w "\n%{http_code}")
    fi

    http_code=$(echo "${response}" | tail -n 1)
    body=$(echo "${response}" | sed '$d')

    # Auto-fallback: retry once on HTTPS if target rejects plain HTTP.
    if [[ "${http_code}" == "400" && "${tried_https_fallback}" == "false" && "${body}" == *"plain HTTP request was sent to HTTPS port"* ]]; then
      OPENSEARCH_SCHEME="https"
      BASE_URL="${OPENSEARCH_SCHEME}://${OPENSEARCH_HOST}:${OPENSEARCH_PORT}"
      tried_https_fallback="true"
      echo "WARN: endpoint expects HTTPS. Retrying with ${BASE_URL}"
      continue
    fi

    break
  done

  if [[ "${http_code}" =~ ^2[0-9][0-9]$ ]]; then
    echo "OK (${http_code})"
    return 0
  fi

  # Idempotency: index may already exist
  if [[ "${http_code}" == "400" && "${body}" == *"resource_already_exists_exception"* ]]; then
    echo "WARN (${http_code}): resource already exists, continuing"
    return 0
  fi

  echo "ERROR (${http_code})"
  echo "${body}"
  return 1
}

routing_pipeline_payload='{
  "processors": [
    {
      "script": {
        "source": "if (ctx.tags != null && ctx.tags.size() > 0) { for (String tag : ctx.tags) { if (tag.equals(\"AUDIT5Y\")) { ctx._index = \"pn-logs5y\"; } else if (tag.equals(\"AUDIT10Y\")) { ctx._index = \"pn-logs10y\"; } else { ctx._index = \"pn-logs120d\"; } } } else { ctx._index = \"pn-logs120d\"; }"
      }
    }
  ]
}'

ingest_pipeline_payload='{
  "processors": [
    {
      "grok": {
        "field": "trace_id",
        "patterns": [
          "^.*;Root=%{DATA:root_trace_id};.*$"
        ],
        "ignore_failure": true
      }
    },
    {
      "grok": {
        "ignore_failure": true,
        "field": "uid",
        "patterns": [
          "^%{UID_PREFIX:uid_prefix}-%{DATA:uid}$"
        ],
        "pattern_definitions": {
          "UID_PREFIX": "IO-PF|IO-PG|IO-PA"
        }
      }
    }
  ]
}'

index_template_120d='{
  "index_patterns": ["pn-logs120d*"],
  "template": {
    "settings": {
      "index": {
        "final_pipeline": "import",
        "opendistro": {
          "index_state_management": {
            "rollover_alias": "pn-logs120d"
          }
        },
        "number_of_shards": "1",
        "number_of_replicas": "1"
      }
    },
    "mappings": {
      "dynamic_templates": [
        {
          "strings_as_keyword": {
            "match_mapping_type": "string",
            "mapping": {
              "type": "keyword"
            }
          }
        }
      ],
      "properties": {
        "@timestamp": {
          "type": "date"
        }
      }
    },
    "aliases": {
      "pn-logs": {}
    }
  },
  "composed_of": []
}'

index_template_5y='{
  "index_patterns": ["pn-logs5y*"],
  "template": {
    "settings": {
      "index": {
        "final_pipeline": "import",
        "opendistro": {
          "index_state_management": {
            "rollover_alias": "pn-logs5y"
          }
        },
        "number_of_shards": "1",
        "number_of_replicas": "1"
      }
    },
    "mappings": {
      "dynamic_templates": [
        {
          "strings_as_keyword": {
            "match_mapping_type": "string",
            "mapping": {
              "type": "keyword"
            }
          }
        }
      ],
      "properties": {
        "@timestamp": {
          "type": "date"
        }
      }
    },
    "aliases": {
      "pn-logs": {}
    }
  },
  "composed_of": []
}'

index_template_10y='{
  "index_patterns": ["pn-logs10y*"],
  "template": {
    "settings": {
      "index": {
        "final_pipeline": "import",
        "opendistro": {
          "index_state_management": {
            "rollover_alias": "pn-logs10y"
          }
        },
        "number_of_shards": "1",
        "number_of_replicas": "1"
      }
    },
    "mappings": {
      "dynamic_templates": [
        {
          "strings_as_keyword": {
            "match_mapping_type": "string",
            "mapping": {
              "type": "keyword"
            }
          }
        }
      ],
      "properties": {
        "@timestamp": {
          "type": "date"
        }
      }
    },
    "aliases": {
      "pn-logs": {}
    }
  },
  "composed_of": []
}'

policy_120d='{
  "policy": {
    "description": "Rollover audit120d",
    "default_state": "rollover",
    "states": [
      {
        "name": "rollover",
        "actions": [
          {
            "rollover": {
              "min_size": "20gb",
              "min_index_age": "3d"
            }
          }
        ],
        "transitions": [
          {
            "state_name": "delete",
            "conditions": {
              "min_index_age": "120d"
            }
          }
        ]
      },
      {
        "name": "delete",
        "actions": [
          {
            "delete": {}
          }
        ],
        "transitions": []
      }
    ],
    "ism_template": [
      {
        "index_patterns": ["pn-logs120d*"],
        "priority": 100
      }
    ]
  }
}'

policy_5y='{
  "policy": {
    "description": "Rollover audit5y",
    "default_state": "rollover",
    "states": [
      {
        "name": "rollover",
        "actions": [
          {
            "rollover": {
              "min_size": "20gb",
              "min_index_age": "3d"
            }
          }
        ],
        "transitions": [
          {
            "state_name": "delete",
            "conditions": {
              "min_index_age": "1825d"
            }
          }
        ]
      },
      {
        "name": "delete",
        "actions": [
          {
            "delete": {}
          }
        ],
        "transitions": []
      }
    ],
    "ism_template": [
      {
        "index_patterns": ["pn-logs5y*"],
        "priority": 100
      }
    ]
  }
}'

policy_10y='{
  "policy": {
    "description": "Rollover audit10y",
    "default_state": "rollover",
    "states": [
      {
        "name": "rollover",
        "actions": [
          {
            "rollover": {
              "min_size": "20gb",
              "min_index_age": "3d"
            }
          }
        ],
        "transitions": [
          {
            "state_name": "delete",
            "conditions": {
              "min_index_age": "3650d"
            }
          }
        ]
      },
      {
        "name": "delete",
        "actions": [
          {
            "delete": {}
          }
        ],
        "transitions": []
      }
    ],
    "ism_template": [
      {
        "index_patterns": ["pn-logs10y*"],
        "priority": 100
      }
    ]
  }
}'

policy_7d_test='{
  "policy": {
    "description": "Rollover audit7d",
    "default_state": "rollover",
    "states": [
      {
        "name": "rollover",
        "actions": [
          {
            "retry": {
              "count": 3,
              "backoff": "exponential",
              "delay": "1m"
            },
            "rollover": {
              "min_index_age": "1d"
            }
          }
        ],
        "transitions": [
          {
            "state_name": "delete",
            "conditions": {
              "min_index_age": "1d"
            }
          }
        ]
      },
      {
        "name": "delete",
        "actions": [
          {
            "retry": {
              "count": 3,
              "backoff": "exponential",
              "delay": "1m"
            },
            "delete": {}
          }
        ],
        "transitions": []
      }
    ],
    "ism_template": [
      {
        "index_patterns": [
          "pn-logs10y*",
          "pn-logs2y*",
          "pn-logs5y*",
          "pn-logs120d*"
        ],
        "priority": 101
      }
    ]
  }
}'

index_120d='{
  "aliases": {
    "pn-logs120d": {
      "is_write_index": true
    }
  }
}'

index_5y='{
  "aliases": {
    "pn-logs5y": {
      "is_write_index": true
    }
  }
}'

index_10y='{
  "aliases": {
    "pn-logs10y": {
      "is_write_index": true
    }
  }
}'

routing_index='{
  "settings": {
    "index.default_pipeline": "routing_pipeline"
  }
}'

reader_role='{
  "cluster_permissions": [
    "read",
    "data_access",
    "search",
    "get",
    "indices_monitor"
  ],
  "index_permissions": [
    {
      "index_patterns": [
        "pn-logs*"
      ],
      "dls": "",
      "fls": [],
      "masked_fields": [],
      "allowed_actions": [
        "read",
        "data_access",
        "search",
        "get",
        "indices_monitor"
      ]
    }
  ],
  "tenant_permissions": []
}'

writer_role='{
  "cluster_permissions": [
    "write",
    "index"
  ],
  "index_permissions": [
    {
      "index_patterns": [
        "routing_index",
        "pn-logs*"
      ],
      "dls": "",
      "fls": [],
      "masked_fields": [],
      "allowed_actions": [
        "write",
        "index"
      ]
    }
  ]
}'

reader_user_payload="{
  \"password\": \"${READER_PASSWORD}\"
}"

writer_user_payload="{
  \"password\": \"${WRITER_PASSWORD}\"
}"

reader_mapping='{
  "users": ["pn-log-extractor-reader"]
}'

writer_mapping='{
  "users": ["pn-lambda-writer"]
}'

echo "Starting OpenSearch initialization on ${BASE_URL} (environment=${ENVIRONMENT})"

# 1) Preliminary security configuration: roles and users
call_api "CREATE ROLE pn-log-extractor-reader" "PUT" "/_plugins/_security/api/roles/pn-log-extractor-reader" "${reader_role}"
call_api "CREATE ROLE pn-lambda-writer" "PUT" "/_plugins/_security/api/roles/pn-lambda-writer" "${writer_role}"
call_api "CREATE USER pn-log-extractor-reader" "PUT" "/_plugins/_security/api/internalusers/pn-log-extractor-reader" "${reader_user_payload}"
call_api "CREATE USER pn-lambda-writer" "PUT" "/_plugins/_security/api/internalusers/pn-lambda-writer" "${writer_user_payload}"
call_api "MAP USER pn-log-extractor-reader -> ROLE" "PUT" "/_plugins/_security/api/rolesmapping/pn-log-extractor-reader" "${reader_mapping}"
call_api "MAP USER pn-lambda-writer -> ROLE" "PUT" "/_plugins/_security/api/rolesmapping/pn-lambda-writer" "${writer_mapping}"

# 2) OpenSearch bootstrap (pipelines, templates, policies, indexes)
call_api "BOOTSTRAP ROUTING INGEST PIPELINE" "PUT" "/_ingest/pipeline/routing_pipeline" "${routing_pipeline_payload}"
call_api "BOOTSTRAP INGEST PIPELINE" "PUT" "/_ingest/pipeline/import" "${ingest_pipeline_payload}"

call_api "BOOTSTRAP INDEX TEMPLATE 120D" "PUT" "/_index_template/ism_rollover120d" "${index_template_120d}"
call_api "BOOTSTRAP INDEX TEMPLATE 5Y" "PUT" "/_index_template/ism_rollover5y" "${index_template_5y}"
call_api "BOOTSTRAP INDEX TEMPLATE 10Y" "PUT" "/_index_template/ism_rollover10y" "${index_template_10y}"

if [[ "${ENVIRONMENT}" == "test" ]]; then
  call_api "BOOTSTRAP LIFECYCLE POLICY 7D (TEST)" "PUT" "/_plugins/_ism/policies/rollover7d" "${policy_7d_test}"
fi

call_api "BOOTSTRAP LIFECYCLE POLICY 120D" "PUT" "/_plugins/_ism/policies/rollover120d" "${policy_120d}"
call_api "BOOTSTRAP LIFECYCLE POLICY 5Y" "PUT" "/_plugins/_ism/policies/rollover5y" "${policy_5y}"
call_api "BOOTSTRAP LIFECYCLE POLICY 10Y" "PUT" "/_plugins/_ism/policies/rollover10y" "${policy_10y}"

call_api "BOOTSTRAP INDEX 10Y" "PUT" "/pn-logs10y-000001" "${index_10y}"
call_api "BOOTSTRAP INDEX 5Y" "PUT" "/pn-logs5y-000001" "${index_5y}"
call_api "BOOTSTRAP INDEX 120D" "PUT" "/pn-logs120d-000001" "${index_120d}"

call_api "BOOTSTRAP ROUTING INDEX" "PUT" "/routing_index" "${routing_index}"

echo "\nInitialization completed successfully."
