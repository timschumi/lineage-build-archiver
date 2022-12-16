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
import hashlib
import logging
import os
import pathlib
import psycopg
import re
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "directory",
        action="store",
        help="The directory to index",
    )
    args = parser.parse_args()

    logging.basicConfig(
        format="%(asctime)s %(levelname)-8s %(message)s",
        level=logging.INFO,
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    if not os.path.isdir(args.directory):
        logging.fatal("Directory '%s' does not exist", args.directory)
        return 1

    database_connection = psycopg.connect(
        f"host={os.environ.get('POSTGRES_HOST')}"
        f" user={os.environ.get('POSTGRES_USER')}"
        f" password={os.environ.get('POSTGRES_PASSWORD')}"
        f" dbname={os.environ.get('POSTGRES_DB')}"
    )

    with database_connection.cursor() as cursor:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS builds (
                id SERIAL PRIMARY KEY NOT NULL,
                name TEXT NOT NULL,
                version TEXT NOT NULL,
                date TEXT NOT NULL,
                device TEXT NOT NULL,
                size BIGINT NOT NULL,
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
        database_connection.commit()

    info_from_name_regex = re.compile(
        r"lineage-(\d+\.\d+)-(\d+)-[A-Za-z]+-([A-Za-z0-9_]+)-signed\.zip"
    )

    for root, dirs, files in os.walk(args.directory):
        for file in files:
            full_path = os.path.join(root, file)
            relative_path = os.path.relpath(full_path, args.directory)

            info_result = info_from_name_regex.match(file)

            if not info_result:
                logging.error("Failed to match file name '%s'", file)
                continue

            file_size = os.path.getsize(full_path)

            with database_connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO builds (name, version, date, device, size) VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT DO NOTHING
                    RETURNING id;
                    """,
                    (
                        file,
                        info_result.group(1),
                        info_result.group(2),
                        info_result.group(3),
                        file_size,
                    ),
                )
                if cursor.rowcount == 0:
                    continue
                new_id = cursor.fetchone()[0]
                database_connection.commit()

            logging.info("Indexed build '%s' with ID '%d'", file, new_id)

            contents = pathlib.Path(full_path).read_bytes()
            md5_sum = hashlib.md5(contents)
            sha1_sum = hashlib.sha1(contents)
            sha256_sum = hashlib.sha256(contents)
            sha512_sum = hashlib.sha512(contents)

            with database_connection.cursor() as cursor:
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
                database_connection.commit()


if __name__ == "__main__":
    sys.exit(main())
