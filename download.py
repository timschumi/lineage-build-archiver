#!/usr/bin/env python3

"""
Copyright (C) 2022 Tim Schumacher

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

     http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

import argparse
import logging
import os
import requests
import sys
from update_verifier import update_verifier
import urllib

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--updater', '-u', action='store', help='The Updater instance that we want to download from', dest='updater', default='https://download.lineageos.org')
    parser.add_argument('--list', '-l', action='store', help='A URL to a list of devices in "hudson"-format', dest='list', default='https://raw.githubusercontent.com/LineageOS/hudson/master/lineage-build-targets')
    parser.add_argument('--device', '-d', action='store', help='A specific device selection (overrides hudson)', dest='device')
    parser.add_argument('--channel', '-c', action='store', help='The release channel to download', dest='channel', default='nightly')
    parser.add_argument('--output', '-o', action='store', help='The output folder to store downloads into', dest='output', required=True)
    parser.add_argument('--key', '-k', action='store', help='The public key to check file signatures against', dest='key', default='update_verifier/lineageos_pubkey')
    args = parser.parse_args()

    logging.basicConfig(format='%(asctime)s %(levelname)-8s %(message)s', level=logging.INFO, datefmt='%Y-%m-%d %H:%M:%S')

    if args.device:
        devices = [args.device]
    elif args.list:
        logging.info("Fetching device list from '%s'...", args.list)

        r = requests.get(args.list)

        if r.status_code != 200:
            logging.error("Got status code %d while fetching devices from '%s', exiting...", r.status_code, args.list)
            return 1

        devices = []

        for line in r.text.splitlines():
            line = line.strip()

            # Skip comments
            if line.startswith('#'):
                continue

            # Skip empty lines
            if len(line) == 0:
                continue

            # Line should be of format `<device> <build type> <branch name> <period>`
            line_splits = line.split()

            devices.append(line_splits[0])

        if len(devices) == 0:
            logging.error("Found no devices, exiting...")
            return 1

        logging.info("Found %d devices.", len(devices))
    else:
        logging.error("Need either a device selection or a list of devices, exiting...")
        return 1

    if not os.path.isdir(args.output):
        os.makedirs(args.output)

    for device in devices:
        url = f"{args.updater}/api/v1/{device}/{args.channel}/unused"

        r = requests.get(url)

        if r.status_code != 200:
            logging.warning("Got status code %d while requesting '%s', skipping...", r.status_code, url)
            continue

        data = r.json()['response']

        for entry in sorted(data, key=lambda x: x["datetime"], reverse=True):
            filepath = os.path.join(args.output, device, entry["version"], entry["filename"])

            if not os.path.isdir(filepath_dirname := os.path.dirname(filepath)):
                os.makedirs(filepath_dirname)

            if os.path.isfile(filepath):
                logging.info("File '%s' exists, skipping download.", filepath)
            elif os.path.isfile(oldpath := os.path.join(args.output, device, entry["filename"])):
                logging.info("Moving file '%s' to '%s'", oldpath, filepath)
                os.rename(oldpath, filepath)
            else:
                logging.info("Downloading '%s' to '%s'...", entry["url"], filepath)
                urllib.request.urlretrieve(entry["url"], filepath)

            filesize = os.path.getsize(filepath)
            if filesize != int(entry["size"]):
                logging.warning("File '%s' has wrong file size (expected: %d, actual: %d)", filepath, int(entry["size"]), filesize)
                os.remove(filepath)
                continue

            signed_file = update_verifier.SignedFile(filepath)
            try:
                signed_file.verify(args.key)
            except (update_verifier.SignatureError, ValueError, TypeError, OSError) as e:
                logging.warning("File '%s' failed the signature check: %s", filepath, e)
                os.remove(filepath)
                continue


if __name__ == '__main__':
    sys.exit(main())
