#!/bin/bash

set -e
# To run this script you need to run the following command in a separate terminals:
#   > kli witness demo

kli init --name External --salt 0ACDEyMzQ1Njc4OWxtbm9ext --nopasscode --config-dir ${SENTINEL_SCRIPT_DIR} --config-file sentinel-config
kli incept --name External --alias External --file ${SENTINEL_SCRIPT_DIR}/data/base-aid.json

kli init --name QVI --salt 0ACDEyMzQ1Njc4OWxtbm9qvi --nopasscode --config-dir ${SENTINEL_SCRIPT_DIR} --config-file sentinel-config
kli incept --name QVI --alias QVI --file ${SENTINEL_SCRIPT_DIR}/data/base-aid.json

