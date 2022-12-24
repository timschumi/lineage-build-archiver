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

import flask
import humanize
import os
import psycopg
import re

import template

app = flask.Flask(__name__)

db = psycopg.connect(
    f"host={os.environ.get('POSTGRES_HOST')}"
    f" user={os.environ.get('POSTGRES_USER')}"
    f" password={os.environ.get('POSTGRES_PASSWORD')}"
    f" dbname={os.environ.get('POSTGRES_DATABASE')}"
)


@app.route("/")
def overview() -> str:
    with db.cursor() as cursor:
        cursor.execute("SELECT COUNT(*), SUM(size), AVG(size) FROM builds;")
        (build_count_known, build_size_known, build_size_average) = cursor.fetchone()

        cursor.execute("""
        SELECT COUNT(*), SUM(size) FROM builds
        WHERE EXISTS (
            SELECT value FROM build_sources
            WHERE builds.id = build_sources.build_id
        );
        """)
        (build_count_stored, build_size_stored) = cursor.fetchone()

        cursor.execute("SELECT COUNT(DISTINCT device) FROM builds;")
        (device_count,) = cursor.fetchone()

        cursor.execute("""
            SELECT COUNT(*) FROM (
                SELECT DISTINCT device, version FROM builds
            ) AS count;
        """)
        (device_version_count,) = cursor.fetchone()

        builds = {}

        cursor.execute("""
        SELECT builds.id, builds.name, builds.size, build_hashes.value AS sha256, build_sources.value AS url
        FROM builds
        JOIN build_hashes ON builds.id = build_hashes.build_id
        JOIN build_sources ON builds.id = build_sources.build_id
        WHERE build_hashes.type = 'sha256'
          AND build_sources.type = 'online'
        ORDER BY builds.date DESC
        """)
        for e in cursor.fetchall():
            if e[0] in builds:
                continue

            builds[e[0]] = {
                "filename": e[1],
                "filesize": e[2],
                "sha256": e[3],
                "url": e[4],
            }

        cursor.execute("""
        SELECT builds.id, builds.name, builds.size, build_hashes.value AS sha256
        FROM builds
        JOIN build_hashes ON builds.id = build_hashes.build_id
        JOIN build_sources ON builds.id = build_sources.build_id
        WHERE build_hashes.type = 'sha256'
          AND build_sources.type = 'local'
        ORDER BY builds.date DESC
        """)
        for e in cursor.fetchall():
            if e[0] in builds:
                continue

            builds[e[0]] = {
                "filename": e[1],
                "filesize": e[2],
                "sha256": e[3],
                "url": None,
            }

        cursor.execute("""
        SELECT builds.id, builds.name, builds.size, build_hashes.value AS sha256
        FROM builds
        JOIN build_hashes ON builds.id = build_hashes.build_id
        WHERE build_hashes.type = 'sha256'
        ORDER BY builds.date DESC
        """)
        for e in cursor.fetchall():
            if e[0] in builds:
                continue

            builds[e[0]] = {
                "filename": e[1],
                "filesize": e[2],
                "sha256": e[3],
            }

        db.commit()

    context = {
        "builds": builds,
        "humanize": humanize,
        "template": template,
        "build_count_known": str(build_count_known),
        "build_size_known": humanize.naturalsize(build_size_known),
        "build_count_stored": str(build_count_stored),
        "build_size_stored": humanize.naturalsize(build_size_stored),
        "build_size_average": humanize.naturalsize(build_size_average),
        "device_count": str(device_count),
        "device_version_count": str(device_version_count),
        "device_version_size_estimate": humanize.naturalsize(
            build_size_average * device_version_count
        ),
    }

    return template.fill("overview", context)


if __name__ == "__main__":
    app.run(debug=False)
