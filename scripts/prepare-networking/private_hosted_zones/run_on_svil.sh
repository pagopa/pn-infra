#!/usr/bin/env bash

./create_and_share_private_hosted_zones.sh \
    -p-1 poste_pncore_svil \
    -d-1 core.pn.internal \
    -v-1 vpc-0481e419f6467daa9 \
    \
    -p-2 poste_helpdesk_svil \
    -d-2 helpdesk.pn.internal \
    -v-2 vpc-09fb415a2a4ab21ee \
    \
    -p-3 poste_confidential_svil \
    -d-3 confidential.pn.internal \
    -v-3 vpc-000f6dbe5cb177a5e \

