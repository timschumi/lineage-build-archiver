#!/usr/bin/env python3

"""
Copyright (C) 2022-2023 Tim Schumacher

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
import hashlib
import logging
import os
import pathlib
import psycopg
import re
import sys
import typing
from update_verifier import update_verifier

STORAGE_ROOT = os.environ.get("STORAGE_ROOT")

POSTGRES_HOST = os.environ.get("POSTGRES_HOST")
POSTGRES_USER = os.environ.get("POSTGRES_USER")
POSTGRES_PASSWORD = os.environ.get("POSTGRES_PASSWORD")
POSTGRES_DATABASE = os.environ.get("POSTGRES_DATABASE")


def db() -> psycopg.Connection[typing.Any]:
    if hasattr(db, "connection"):
        try:
            db.connection.cursor().execute("SELECT 1")
        except psycopg.OperationalError:
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
        "--key",
        action="store",
        help="The public key to check file signatures against",
        dest="key",
        default="update_verifier/lineageos_pubkey",
    )
    parser.add_argument(
        "files",
        nargs="+",
    )
    args = parser.parse_args()

    logging.basicConfig(
        format="%(asctime)s %(levelname)-8s %(message)s",
        level=logging.INFO,
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    for input_filepath in args.files:
        input_filename = os.path.basename(input_filepath)

        match = re.match(
            r"lineage-([0-9\.]+)-([0-9]+)-(?:.*)-(.*)-signed\.zip", input_filename
        )

        if match is None:
            logging.warning(
                "Could not match '%s' against the filename pattern, skipping.",
                input_filename,
            )
            continue

        version = match.group(1)
        date = match.group(2)
        device = match.group(3)

        filepath = os.path.join(STORAGE_ROOT, device, version, input_filename)

        if not os.path.isdir(filepath_dirname := os.path.dirname(filepath)):
            os.makedirs(filepath_dirname)

        if os.path.isfile(filepath):
            logging.warning("File '%s' elready exists, skipping.", filepath)
            continue

        signed_file = update_verifier.SignedFile(input_filepath)
        try:
            signed_file.verify(args.key)
        except (
            update_verifier.SignatureError,
            ValueError,
            TypeError,
            OSError,
        ) as e:
            logging.warning(
                "File '%s' failed the signature check: %s", input_filepath, e
            )
            continue

        logging.info("Importing file '%s' to path '%s'...", input_filepath, filepath)

        contents = pathlib.Path(input_filepath).read_bytes()
        md5_sum = hashlib.md5(contents)
        sha1_sum = hashlib.sha1(contents)
        sha256_sum = hashlib.sha256(contents)
        sha512_sum = hashlib.sha512(contents)

        filesize = os.path.getsize(input_filepath)

        with db().cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO build (name, version, date, device, size, available_upstream) VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT DO NOTHING
                RETURNING id;
                """,
                (
                    input_filename,
                    version,
                    date,
                    device,
                    filesize,
                    False,
                ),
            )
            if cursor.rowcount == 0:
                continue
            new_id = cursor.fetchone()[0]
            db().commit()

        os.rename(input_filepath, filepath)

        relative_path = os.path.relpath(filepath, STORAGE_ROOT)

        with db().cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO build_hash_md5 (build, hash) VALUES (%s, %s) ON CONFLICT DO NOTHING;
                """,
                (new_id, md5_sum.hexdigest()),
            )
            cursor.execute(
                """
                INSERT INTO build_hash_sha1 (build, hash) VALUES (%s, %s) ON CONFLICT DO NOTHING;
                """,
                (new_id, sha1_sum.hexdigest()),
            )
            cursor.execute(
                """
                INSERT INTO build_hash_sha256 (build, hash) VALUES (%s, %s) ON CONFLICT DO NOTHING;
                """,
                (new_id, sha256_sum.hexdigest()),
            )
            cursor.execute(
                """
                INSERT INTO build_hash_sha512 (build, hash) VALUES (%s, %s) ON CONFLICT DO NOTHING;
                """,
                (new_id, sha512_sum.hexdigest()),
            )
            cursor.execute(
                """
                INSERT INTO build_source_local (build, location) VALUES (%s, %s);
                """,
                (new_id, relative_path),
            )
            db().commit()


if __name__ == "__main__":
    sys.exit(main())
