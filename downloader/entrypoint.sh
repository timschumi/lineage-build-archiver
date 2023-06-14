#!/bin/bash -e

while true; do
    ./download.py "${@}"

    sleep `expr 60 \* ${UPDATE_INTERVAL}`
done
