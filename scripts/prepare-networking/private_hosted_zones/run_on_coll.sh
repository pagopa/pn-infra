#!/usr/bin/env bash

./create_and_share_private_hosted_zones.sh \
    -p-1 poste_pncore_coll \
    -d-1 core.pn.internal \
    -v-1 vpc-0a41767dedbde3532 \
    \
    -p-2 poste_helpdesk_coll \
    -d-2 helpdesk.pn.internal \
    -v-2 vpc-083959c9d41791cca \
    \
    -p-3 poste_confidential_coll \
    -d-3 confidential.pn.internal \
    -v-3 vpc-0df9bb5dbef233454 

