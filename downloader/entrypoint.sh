#!/bin/bash -e

./download.py ${DOWNLOAD_ARGS}
./prune.py ${PRUNE_ARGS}
