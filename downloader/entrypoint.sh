#!/bin/bash -e

while true; do
    ./download.py --output /builds "${@}"

    sleep `expr 60 \* ${UPDATE_INTERVAL}`
done
