#!/bin/bash -e

while true; do
    ./download.py ${DOWNLOAD_ARGS}
    ./prune.py ${PRUNE_ARGS}

    sleep `expr 60 \* ${UPDATE_INTERVAL}`
done
