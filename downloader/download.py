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
import datetime
import hashlib
import logging
import os
import pathlib
import psycopg
import requests
import statsd
import sys
import time
import typing
from update_verifier import update_verifier
import urllib

POSTGRES_HOST = os.environ.get("POSTGRES_HOST")
POSTGRES_USER = os.environ.get("POSTGRES_USER")
POSTGRES_PASSWORD = os.environ.get("POSTGRES_PASSWORD")
POSTGRES_DATABASE = os.environ.get("POSTGRES_DATABASE")

STATSD_HOST = os.environ.get("STATSD_HOST")
STATSD_PORT = os.environ.get("STATSD_PORT")

stats = statsd.StatsClient(STATSD_HOST, STATSD_PORT, prefix="downloader")


def db() -> psycopg.Connection[typing.Any]:
    if hasattr(db, "connection"):
        try:
            db.connection.cursor().execute("SELECT 1")
        except psycopg.OperationalError:
            stats.incr("database_connection_errors")
            del db.connection

    if not hasattr(db, "connection") or db.connection.closed:
        db.connection = psycopg.connect(
            f"host={POSTGRES_HOST}"
            f" user={POSTGRES_USER}"
            f" password={POSTGRES_PASSWORD}"
            f" dbname={POSTGRES_DATABASE}"
        )

    return db.connection


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--updater",
        action="store",
        help="The Updater instance that we want to download from",
        dest="updater",
        default="https://download.lineageos.org",
    )
    parser.add_argument(
        "--list",
        action="store",
        help='A URL to a list of devices in "hudson"-format',
        dest="list",
        default="https://raw.githubusercontent.com/LineageOS/hudson/master/lineage-build-targets",
    )
    parser.add_argument(
        "--device",
        action="store",
        help="A specific device selection (overrides hudson)",
        dest="device",
    )
    parser.add_argument(
        "--channel",
        action="store",
        help="The release channel to download",
        dest="channel",
        default="nightly",
    )
    parser.add_argument(
        "--output",
        action="store",
        help="The output folder to store downloads into",
        dest="output",
        required=True,
    )
    parser.add_argument(
        "--key",
        action="store",
        help="The public key to check file signatures against",
        dest="key",
        default="update_verifier/lineageos_pubkey",
    )
    parser.add_argument(
        "--retain",
        action="store",
        help="The number of builds to be kept",
        dest="retain",
        type=int,
        default=None,
    )
    args = parser.parse_args()

    logging.basicConfig(
        format="%(asctime)s %(levelname)-8s %(message)s",
        level=logging.INFO,
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    with db().cursor() as cursor:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS builds (
                id SERIAL PRIMARY KEY NOT NULL,
                name TEXT NOT NULL,
                version TEXT NOT NULL,
                date TEXT NOT NULL,
                device TEXT NOT NULL,
                size BIGINT NOT NULL,
                available_upstream BOOLEAN NOT NULL DEFAULT FALSE,
                UNIQUE (name),
                UNIQUE (version, date, device)
            );
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS build_hashes (
                id SERIAL PRIMARY KEY NOT NULL,
                build_id INTEGER NOT NULL,
                type TEXT NOT NULL,
                value TEXT NOT NULL,
                UNIQUE (build_id, type),
                FOREIGN KEY (build_id) REFERENCES builds (id) ON DELETE CASCADE
            );
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS build_sources (
                id SERIAL PRIMARY KEY NOT NULL,
                build_id INTEGER NOT NULL,
                type TEXT NOT NULL,
                value TEXT NOT NULL,
                FOREIGN KEY (build_id) REFERENCES builds (id) ON DELETE CASCADE
            );
            """
        )
        db().commit()

    if args.device:
        devices = [args.device]
    elif args.list:
        logging.info("Fetching device list from '%s'...", args.list)

        r = requests.get(args.list)

        if r.status_code != 200:
            logging.error(
                "Got status code %d while fetching devices from '%s', exiting...",
                r.status_code,
                args.list,
            )
            return 1

        devices = []

        for line in r.text.splitlines():
            line = line.strip()

            # Skip comments
            if line.startswith("#"):
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

        stats.gauge("upstream_devices", len(devices))
        logging.info("Found %d devices.", len(devices))
    else:
        logging.error("Need either a device selection or a list of devices, exiting...")
        return 1

    if not os.path.isdir(args.output):
        os.makedirs(args.output)

    with db().cursor() as cursor:
        cursor.execute(
            """
            SELECT DISTINCT device FROM builds WHERE available_upstream IS TRUE;
            """
        )
        devices_for_refresh = [e[0] for e in cursor.fetchall()]

    for device in set(devices + devices_for_refresh):
        url = f"{args.updater}/api/v1/{device}/{args.channel}/unused"

        r = requests.get(url)

        if r.status_code != 200:
            stats.incr("device_fetch_failed")
            logging.warning(
                "Got status code %d while requesting '%s', skipping...",
                r.status_code,
                url,
            )
            continue

        data = r.json()["response"]
        remaining_number_of_builds = {}
        processed_builds = []

        with db().cursor() as cursor, stats.timer("refresh_upstream_state"):
            cursor.execute(
                """
                UPDATE builds SET available_upstream = FALSE WHERE device = %s;
                """,
                (device,),
            )
            cursor.executemany(
                """
                UPDATE builds SET available_upstream = TRUE WHERE name = %s;
                """,
                [(entry["filename"],) for entry in data],
            )
            db().commit()

        if device not in devices:
            continue

        for entry in sorted(data, key=lambda x: x["datetime"], reverse=True):
            if entry["version"] not in remaining_number_of_builds:
                remaining_number_of_builds[entry["version"]] = (
                    0 if args.retain is None else args.retain
                )

            if (
                args.retain is not None
                and remaining_number_of_builds[entry["version"]] <= 0
            ):
                break

            processed_builds.append(entry)
            remaining_number_of_builds[entry["version"]] -= 1

        for entry in processed_builds:
            filepath = os.path.join(
                args.output, device, entry["version"], entry["filename"]
            )

            if not os.path.isdir(filepath_dirname := os.path.dirname(filepath)):
                os.makedirs(filepath_dirname)

            if os.path.isfile(filepath):
                logging.debug("File '%s' exists, skipping download.", filepath)
                continue

            logging.info("Downloading '%s' to '%s'...", entry["url"], filepath)

            tempfilepath = filepath + ".part"

            hash_time = 0
            md5_sum = hashlib.md5()
            sha1_sum = hashlib.sha1()
            sha256_sum = hashlib.sha256()
            sha512_sum = hashlib.sha512()

            file_chunks = []

            with requests.get(entry["url"], stream=True) as download_request:
                download_request.raise_for_status()

                with open(tempfilepath, 'wb') as download_file:
                    for download_chunk in download_request.iter_content(chunk_size=16384):
                        download_file.write(download_chunk)
                        stats.incr("downloaded_builds_size", len(download_chunk))

                        hash_chunk_start = time.time()
                        md5_sum.update(download_chunk)
                        sha1_sum.update(download_chunk)
                        sha256_sum.update(download_chunk)
                        sha512_sum.update(download_chunk)
                        hash_time += int((time.time() - hash_chunk_start) * 1000)

                        file_chunks.append(download_chunk)

            file_buffer = b"".join(file_chunks)
            del file_chunks

            stats.timing("hash_calculation", hash_time)

            filesize = os.path.getsize(tempfilepath)
            if filesize != int(entry["size"]):
                logging.warning(
                    "File '%s' has wrong file size (expected: %d, actual: %d)",
                    filepath,
                    int(entry["size"]),
                    filesize,
                )
                stats.incr("download_failed_wrong_size")
                os.remove(tempfilepath)
                continue

            signed_file = update_verifier.SignedFile(file_buffer)
            try:
                with stats.timer("signature_verification"):
                    signed_file.verify(args.key)
            except (
                update_verifier.SignatureError,
                ValueError,
                TypeError,
                OSError,
            ) as e:
                logging.warning("File '%s' failed the signature check: %s", filepath, e)
                stats.incr("download_failed_wrong_signature")
                os.remove(tempfilepath)
                continue

            stats.incr("downloaded_builds")

            with db().cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO builds (name, version, date, device, size, available_upstream) VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT DO NOTHING
                    RETURNING id;
                    """,
                    (
                        entry["filename"],
                        entry["version"],
                        datetime.datetime.utcfromtimestamp(entry["datetime"]).strftime(
                            "%Y%m%d"
                        ),
                        device,
                        filesize,
                        True,
                    ),
                )
                if cursor.rowcount == 0:
                    continue
                new_id = cursor.fetchone()[0]
                db().commit()

            if tempfilepath != filepath:
                os.rename(tempfilepath, filepath)

            relative_path = os.path.relpath(filepath, args.output)

            with db().cursor() as cursor:
                cursor.executemany(
                    """
                    INSERT INTO build_hashes (build_id, type, value) VALUES (%s, %s, %s)
                    ON CONFLICT DO NOTHING;
                    """,
                    [
                        (new_id, "md5", md5_sum.hexdigest()),
                        (new_id, "sha1", sha1_sum.hexdigest()),
                        (new_id, "sha256", sha256_sum.hexdigest()),
                        (new_id, "sha512", sha512_sum.hexdigest()),
                    ],
                )
                cursor.execute(
                    """
                    INSERT INTO build_sources (build_id, type, value) VALUES (%s, %s, %s);
                    """,
                    (new_id, "local", relative_path),
                )
                db().commit()

        # If the number of kept builds is unlimited, we are done now
        if args.retain is None:
            continue

        for version in set([e["version"] for e in processed_builds]):
            versiondir = os.path.join(args.output, device, version)
            local_builds = set(os.listdir(versiondir))

            # Builds that were just downloaded are already accounted for
            local_builds = local_builds - set([e["filename"] for e in processed_builds])

            # Traverse the remaining builds starting from the newest and remove any that do not fit
            for filename in sorted(local_builds, reverse=True):
                if not filename.endswith(".zip"):
                    logging.info("Found non-zip file '%s' while removing builds", filename)
                    continue

                if remaining_number_of_builds[version] > 0:
                    remaining_number_of_builds[version] -= 1
                    continue

                filepath = os.path.join(versiondir, filename)
                relative_path = os.path.relpath(filepath, args.output)
                logging.info("Removing file '%s'", filepath)
                with db().cursor() as cursor:
                    cursor.execute(
                        "DELETE FROM build_sources WHERE type = 'local' AND value = %s",
                        (relative_path,),
                    )
                    db().commit()
                os.remove(filepath)
                stats.incr("deleted_builds")


if __name__ == "__main__":
    sys.exit(main())
