#!/usr/bin/env bash

./create_and_share_private_hosted_zones.sh \
    -p-1 pn_dev \
    -d-1 core.pn.internal \
    -v-1 vpc-02246785c97c06e4b \
    \
    -p-2 pn_logs \
    -d-2 helpdesk.pn.internal \
    -v-2 vpc-00681fd502cc47260 \
    \
    -p-3 pn_confidential \
    -d-3 confidential.pn.internal \
    -v-3 	vpc-073b889f8459d6a2e

