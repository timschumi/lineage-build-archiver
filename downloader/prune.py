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
import logging
import os
import psycopg
import sys
import typing

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
        "--dry-run",
        action="store_true",
        dest="dry_run",
        default=False,
    )
    parser.add_argument(
        "--retain",
        action="store",
        help="The number of builds to keep",
        dest="retain",
        type=int,
        default=None,
    )
    args = parser.parse_args()

    if args.retain is None:
        logging.fatal("At least one option for filtering builds has to be passed")
        return 1

    logging.basicConfig(
        format="%(asctime)s %(levelname)-8s %(message)s",
        level=logging.INFO,
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    removed_count = 0
    removed_size = 0

    with db().cursor() as cursor:
        cursor.execute(
            "SELECT DISTINCT device, version FROM build ORDER BY device ASC, version ASC"
        )
        combinations = cursor.fetchall()

    for device, version in combinations:
        with db().cursor() as cursor:
            cursor.execute(
                """
            SELECT build_source_local.id, build_source_local.location, build.size FROM build
            JOIN build_source_local ON build.id = build_source_local.build
            WHERE build.device = %s AND build.version = %s
            ORDER BY build.date ASC
            """,
                (device, version),
            )
            builds = cursor.fetchall()

        if args.retain is not None:
            if len(builds) <= args.retain:
                continue

            del builds[-args.retain:]

        for i, location, size in builds:
            logging.info("Removing build '%s'", location)
            removed_count += 1
            removed_size += size

            if args.dry_run:
                continue

            full_path = os.path.join(STORAGE_ROOT, location)
            with db().cursor() as cursor:
                cursor.execute("DELETE FROM build_source_local WHERE id = %s", (i,))
                db().commit()
            os.remove(full_path)

    logging.info(
        "Removed %s builds with a combined size of %s MiB",
        removed_count,
        int(removed_size / 1024 / 1024),
    )


if __name__ == "__main__":
    sys.exit(main())
