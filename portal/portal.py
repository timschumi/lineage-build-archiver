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

import boto3
import botocore
import flask
import humanize
import json
import logging
import os
import psycopg
import threading

import template

logging.basicConfig(
    format="%(asctime)s %(levelname)-8s %(message)s",
    level=logging.INFO,
    datefmt="%Y-%m-%d %H:%M:%S",
)

app = flask.Flask(__name__,
                  static_url_path='',
                  static_folder='static')

STORAGE_ROOT = os.environ.get("STORAGE_ROOT")

POSTGRES_HOST = os.environ.get("POSTGRES_HOST")
POSTGRES_USER = os.environ.get("POSTGRES_USER")
POSTGRES_PASSWORD = os.environ.get("POSTGRES_PASSWORD")
POSTGRES_DATABASE = os.environ.get("POSTGRES_DATABASE")

S3_DOWNLOAD_URL = os.environ.get("S3_DOWNLOAD_URL")
S3_ENDPOINT = os.environ.get("S3_ENDPOINT")
S3_BUCKET = os.environ.get("S3_BUCKET")
S3_ACCESS_KEY_ID = os.environ.get("S3_ACCESS_KEY_ID")
S3_ACCESS_KEY = os.environ.get("S3_ACCESS_KEY")

db = psycopg.connect(
    f"host={POSTGRES_HOST}"
    f" user={POSTGRES_USER}"
    f" password={POSTGRES_PASSWORD}"
    f" dbname={POSTGRES_DATABASE}"
)

b2 = boto3.resource(
    service_name="s3",
    endpoint_url=S3_ENDPOINT,
    aws_access_key_id=S3_ACCESS_KEY_ID,
    aws_secret_access_key=S3_ACCESS_KEY,
    config=botocore.config.Config(signature_version="s3v4"),
)
b2_bucket = b2.Bucket(S3_BUCKET)

upload_queue = {}
upload_task = None


def upload_queue_task():
    while True:
        if len(upload_queue) == 0:
            break

        (build_id, build_info) = next(iter(upload_queue.items()))

        def update_progress(chunk):
            build_info["progress"] += chunk
            return

        url = S3_DOWNLOAD_URL.format(bucket=S3_BUCKET, file=build_info["name"])

        logging.info("Starting upload of '%s' to '%s'", build_info["path"], url)

        b2_bucket.upload_file(
            os.path.join(STORAGE_ROOT, build_info["path"]),
            build_info["name"],
            Callback=update_progress,
        )

        logging.info("Done with upload of '%s' to '%s'", build_info["path"], url)

        with db.cursor() as cursor:
            cursor.execute(
                "INSERT INTO build_sources (build_id, type, value) VALUES (%s, 'online', %s);",
                (build_id, url),
            )
            
            db.commit()

        del upload_queue[build_id]


@app.route("/api/builds", methods=["GET"])
def api_builds_list():
    builds = []

    with db.cursor() as cursor:
        cursor.execute(
            """
        SELECT builds.id,
               builds.name,
               builds.size,
               build_hashes.value AS sha256,
               source_online.value AS local,
               source_local.value AS url
        FROM builds
        JOIN build_hashes ON builds.id = build_hashes.build_id AND build_hashes.type = 'sha256'
        LEFT OUTER JOIN build_sources source_online ON builds.id = source_online.build_id AND source_online.type = 'online'
        LEFT OUTER JOIN build_sources source_local ON builds.id = source_local.build_id AND source_local.type = 'local'
        ORDER BY
          CASE
            WHEN source_online IS NOT NULL THEN 2
            WHEN source_local IS NOT NULL THEN 1
            ELSE 0
          END DESC, builds.date DESC
        """
        )
        for e in cursor.fetchall():
            builds.append({
                "id": e[0],
                "filename": e[1],
                "filesize": e[2],
                "sha256": e[3],
                "url": e[4],
                "local": e[5],
            })

    return flask.jsonify(builds), 200


@app.route("/api/uploads", methods=["POST"])
def api_uploads_new():
    global upload_task

    request = json.loads(flask.request.data)
    build_id = request["id"]

    if type(build_id) != int:
        return flask.jsonify({"message": "Invalid build ID type"}), 400

    if build_id < 0:
        return flask.jsonify({"message": "Build ID out of range"}), 400

    if build_id in upload_queue:
        return flask.jsonify({"message": "Build already in upload queue"}), 400

    with db.cursor() as cursor:
        cursor.execute("SELECT name, size FROM builds WHERE id = %s;", (build_id,))

        if cursor.rowcount < 1:
            return flask.jsonify({"message": "Build ID is unknown"}), 400

        (build_name, build_size) = cursor.fetchone()

        cursor.execute(
            "SELECT value FROM build_sources WHERE build_id = %s AND type = 'local';",
            (build_id,),
        )

        if cursor.rowcount < 1:
            return flask.jsonify({"message": "Build is not available"}), 400

        (build_path,) = cursor.fetchone()

        cursor.execute(
            "SELECT * FROM build_sources WHERE build_id = %s AND type = 'online';",
            (build_id,),
        )

        if cursor.rowcount > 0:
            return flask.jsonify({"message": "Build is already uploaded"}), 400

    upload_queue[build_id] = {
        "id": build_id,
        "name": build_name,
        "path": build_path,
        "size": build_size,
        "progress": 0,
    }

    if upload_task is None or not upload_task.is_alive():
        upload_task = threading.Thread(target=upload_queue_task)
        upload_task.start()

    return flask.jsonify({}), 201


@app.route("/")
def overview() -> str:
    with db.cursor() as cursor:
        cursor.execute("SELECT COUNT(*), SUM(size), AVG(size) FROM builds;")
        (build_count_known, build_size_known, build_size_average) = cursor.fetchone()

        cursor.execute(
            """
        SELECT COUNT(*), SUM(size) FROM builds
        WHERE EXISTS (
            SELECT value FROM build_sources
            WHERE builds.id = build_sources.build_id
        );
        """
        )
        (build_count_stored, build_size_stored) = cursor.fetchone()

        cursor.execute("SELECT COUNT(DISTINCT device) FROM builds;")
        (device_count,) = cursor.fetchone()

        cursor.execute(
            """
            SELECT COUNT(*) FROM (
                SELECT DISTINCT device, version FROM builds
            ) AS count;
        """
        )
        (device_version_count,) = cursor.fetchone()

        db.commit()

    context = {
        "humanize": humanize,
        "build_count_known": build_count_known,
        "build_size_known": build_size_known,
        "build_count_stored": build_count_stored,
        "build_size_stored": build_size_stored,
        "build_size_average": build_size_average,
        "device_count": device_count,
        "device_version_count": device_version_count,
    }

    return template.fill("overview", context)


if __name__ == "__main__":
    app.run(debug=False)
