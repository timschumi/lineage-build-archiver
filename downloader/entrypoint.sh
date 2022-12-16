#!/bin/bash -e

while true; do
    ./download.py --output /builds "${@}"

    if [ -n "${POSTGRES_HOST}" ]; then
        # TODO: Clear non-existent local files from the database automatically.
        # TODO: Do this directly while downloading.
        ./index.py /builds
    fi

    sleep `expr 60 \* ${UPDATE_INTERVAL}`
done
