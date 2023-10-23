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
import pathlib
import psycopg
import re
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
        "directory",
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
        SELECT build_source_local.id, build_source_local.location FROM build_source_local
          JOIN build_source_online ON build_source_local.build = build_source_online.build;
        """
        )
        entries = cursor.fetchall()

    if not os.path.isdir(args.directory):
        os.makedirs(args.directory)

    for entry in entries:
        with db().cursor() as cursor:
            cursor.execute("DELETE FROM build_source_local WHERE id = %s;", (entry[0],))
            db().commit()

        source = os.path.join(STORAGE_ROOT, entry[1])
        destination = os.path.join(args.directory, os.path.basename(entry[1]))

        logging.info("Exporting '%s' to '%s'", source, destination)

        os.rename(source, destination)


if __name__ == "__main__":
    sys.exit(main())
