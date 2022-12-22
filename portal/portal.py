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

app = flask.Flask(__name__)

db = psycopg.connect(
    f"host={os.environ.get('POSTGRES_HOST')}"
    f" user={os.environ.get('POSTGRES_USER')}"
    f" password={os.environ.get('POSTGRES_PASSWORD')}"
    f" dbname={os.environ.get('POSTGRES_DATABASE')}"
)


@app.route("/")
def overview() -> str:
    with open("template/overview.tpl", "r") as file:
        content = file.read()

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

        builds_table = "<table id='builds_table'>\n"
        builds_table += "<tr><th>Filename</th><th>Filesize</th><th>SHA256</th><th>Status</th></tr>\n"

        seen_builds = set()

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
            builds_table += f"<tr>\n"
            builds_table += f"  <td><pre>{e[1]}</pre></td>\n"
            builds_table += f"  <td>{humanize.naturalsize(e[2])}</td>\n"
            builds_table += f"  <td><pre>{e[3]}</pre></td>\n"
            builds_table += f"  <td><a href='{e[4]}'>Download</a></td>\n"
            builds_table += f"</tr>\n"
            seen_builds.add(e[0])

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
            if e[0] in seen_builds:
                continue

            builds_table += f"<tr>\n"
            builds_table += f"  <td><pre>{e[1]}</pre></td>\n"
            builds_table += f"  <td>{humanize.naturalsize(e[2])}</td>\n"
            builds_table += f"  <td><pre>{e[3]}</pre></td>\n"
            builds_table += f"  <td>Available</td>\n"
            builds_table += f"</tr>\n"
            seen_builds.add(e[0])

        cursor.execute("""
        SELECT builds.id, builds.name, builds.size, build_hashes.value AS sha256
        FROM builds
        JOIN build_hashes ON builds.id = build_hashes.build_id
        WHERE build_hashes.type = 'sha256'
        ORDER BY builds.date DESC
        """)
        for e in cursor.fetchall():
            if e[0] in seen_builds:
                continue

            builds_table += f"<tr>\n"
            builds_table += f"  <td><pre>{e[1]}</pre></td>\n"
            builds_table += f"  <td>{humanize.naturalsize(e[2])}</td>\n"
            builds_table += f"  <td><pre>{e[3]}</pre></td>\n"
            builds_table += f"  <td>Unavailable</td>\n"
            builds_table += f"</tr>\n"
            seen_builds.add(e[0])

        builds_table += "</table>\n"

        db.commit()

    # TODO: Do this by actually parsing and replacing arbitrary expressions.
    content = re.sub(r"\{\{\s*build_count_known\s*\}\}", str(build_count_known), content)
    content = re.sub(r"\{\{\s*build_size_known\s*\}\}", humanize.naturalsize(build_size_known), content)
    content = re.sub(r"\{\{\s*build_count_stored\s*\}\}", str(build_count_stored), content)
    content = re.sub(r"\{\{\s*build_size_stored\s*\}\}", humanize.naturalsize(build_size_stored), content)
    content = re.sub(r"\{\{\s*build_size_average\s*\}\}", humanize.naturalsize(build_size_average), content)
    content = re.sub(r"\{\{\s*device_count\s*\}\}", str(device_count), content)
    content = re.sub(r"\{\{\s*device_version_count\s*\}\}", str(device_version_count), content)
    content = re.sub(r"\{\{\s*device_version_size_estimate\s*\}\}", humanize.naturalsize(build_size_average * device_version_count), content)
    content = re.sub(r"\{\{\s*builds_table\s*\}\}", builds_table, content)

    return content


if __name__ == "__main__":
    app.run(debug=False)
