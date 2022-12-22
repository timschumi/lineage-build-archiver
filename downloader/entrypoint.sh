#!/bin/bash -e

while true; do
    ./download.py --output /builds "${@}"

    if [ -n "${POSTGRES_HOST}" ]; then
        # TODO: Do this directly while downloading.
        ./index.py --prune-local-sources /builds
    fi

    sleep `expr 60 \* ${UPDATE_INTERVAL}`
done
