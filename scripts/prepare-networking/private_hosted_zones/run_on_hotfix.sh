#!/usr/bin/env bash

./create_and_share_private_hosted_zones.sh \
    -p-1 cicd_hotfix_core \
    -d-1 core.pn.internal \
    -v-1 vpc-059fa461ed0c53203 \
    \
    -p-2 cicd_hotfix_helpdesk \
    -d-2 helpdesk.pn.internal \
    -v-2 vpc-0f76c4fcc28587b11 \
    \
    -p-3 cicd_hotfix_confidential \
    -d-3 confidential.pn.internal \
    -v-3 vpc-0819cb0ad75d93fd5