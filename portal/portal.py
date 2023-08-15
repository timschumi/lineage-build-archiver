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
from boto3.s3.transfer import TransferConfig
import botocore
import botocore.exceptions
import flask
import json
import logging
import os
import psycopg
import statsd
import threading
import typing

logging.basicConfig(
    format="%(asctime)s %(levelname)-8s %(message)s",
    level=logging.INFO,
    datefmt="%Y-%m-%d %H:%M:%S",
)

app = flask.Flask(__name__, static_url_path="", static_folder="static")

SITEMAP_PREFIX = os.environ.get("SITEMAP_PREFIX")
SITEMAP_EXTRA = os.environ.get("SITEMAP_EXTRA")
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
S3_MAX_CONCURRENCY = os.environ.get("S3_MAX_CONCURRENCY")

STATSD_HOST = os.environ.get("STATSD_HOST")
STATSD_PORT = os.environ.get("STATSD_PORT")

stats = statsd.StatsClient(STATSD_HOST, STATSD_PORT, prefix="portal")


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


b2 = boto3.resource(
    service_name="s3",
    endpoint_url=S3_ENDPOINT,
    aws_access_key_id=S3_ACCESS_KEY_ID,
    aws_secret_access_key=S3_ACCESS_KEY,
    config=botocore.config.Config(signature_version="s3v4"),
)
b2_bucket = b2.Bucket(S3_BUCKET)
b2_config_settings = {}
if S3_MAX_CONCURRENCY is not None:
    b2_config_settings["max_concurrency"] = int(S3_MAX_CONCURRENCY)
b2_config = boto3.s3.transfer.TransferConfig(**b2_config_settings)

upload_queue = {}
upload_task = None
upload_queue_failed = {}


def upload_queue_task():
    while True:
        stats.gauge("upload_queue_length", len(upload_queue))

        if len(upload_queue) == 0:
            break

        (build_id, build_info) = next(iter(upload_queue.items()))

        def update_progress(chunk):
            build_info["progress"] += chunk
            return

        url = S3_DOWNLOAD_URL.format(bucket=S3_BUCKET, file=build_info["name"])

        logging.info("Starting upload of '%s' to '%s'", build_info["path"], url)

        try:
            b2_bucket.upload_file(
                os.path.join(STORAGE_ROOT, build_info["path"]),
                build_info["name"],
                Callback=update_progress,
                Config=b2_config,
            )
        except botocore.exceptions.ConnectionClosedError:
            logging.info("Failed upload of '%s' to '%s'", build_info["path"], url)
            stats.incr("rejected_build_uploads")
            build_info["error"] = "S3 closed the connection. Storage quota reached?"
            upload_queue_failed[build_id] = build_info
            del upload_queue[build_id]
            continue

        logging.info("Done with upload of '%s' to '%s'", build_info["path"], url)

        with db().cursor() as cursor:
            cursor.execute(
                "INSERT INTO build_source_online (build, location) VALUES (%s, %s);",
                (build_id, url),
            )

            db().commit()

        stats.incr("uploaded_builds")
        del upload_queue[build_id]


@app.route("/api/builds", methods=["GET"])
def api_builds_list():
    builds = []

    stats.incr("api_build_list_accesses")
    with db().cursor() as cursor, stats.timer("api_build_list_generation"):
        cursor.execute(
            """
        SELECT build.id,
               build.name
        FROM build
        LEFT OUTER JOIN build_source_online ON build.id = build_source_online.build
        LEFT OUTER JOIN build_source_local ON build.id = build_source_local.build
        WHERE build_source_online.location IS NOT NULL OR build_source_local.location IS NOT NULL
          AND NOT EXISTS (SELECT id FROM build AS build2 WHERE build2.device = build.device AND build2.version = build.version AND build2.available_upstream IS TRUE)
        ORDER BY build.date DESC
        """
        )
        for e in cursor.fetchall():
            builds.append(
                {
                    "id": e[0],
                    "filename": e[1],
                }
            )

    return flask.jsonify(builds), 200


@app.route("/api/builds/<int:build_id>", methods=["GET"])
def api_builds_get(build_id):
    stats.incr("api_build_accesses")
    with db().cursor() as cursor, stats.timer("api_build_generation"):
        cursor.execute(
            """
        SELECT build.id,
               build.name,
               build.size,
               build_hash_md5.hash AS md5,
               build_hash_sha1.hash AS sha1,
               build_hash_sha256.hash AS sha256,
               build_hash_sha512.hash AS sha512,
               build_source_online.location AS url,
               build_source_local.location AS path
        FROM build
        LEFT OUTER JOIN build_hash_md5 ON build.id = build_hash_md5.build
        LEFT OUTER JOIN build_hash_sha1 ON build.id = build_hash_sha1.build
        LEFT OUTER JOIN build_hash_sha256 ON build.id = build_hash_sha256.build
        LEFT OUTER JOIN build_hash_sha512 ON build.id = build_hash_sha512.build
        LEFT OUTER JOIN build_source_online ON build.id = build_source_online.build
        LEFT OUTER JOIN build_source_local ON build.id = build_source_local.build
        WHERE build.id = %s
        """,
            (build_id,),
        )

        if cursor.rowcount < 1:
            return flask.jsonify({"message": "Build ID not found"}), 404

        e = cursor.fetchone()
        return (
            flask.jsonify(
                {
                    "id": e[0],
                    "filename": e[1],
                    "filesize": e[2],
                    "md5": e[3],
                    "sha1": e[4],
                    "sha256": e[5],
                    "sha512": e[6],
                    "url": e[7],
                    "path": e[8],
                }
            ),
            200,
        )


@app.route("/api/uploads", methods=["GET"])
def api_uploads_list():
    stats.incr("api_upload_list_accesses")
    return flask.jsonify([e for e in upload_queue.values()]), 200


@app.route("/api/uploads", methods=["POST"])
def api_uploads_new():
    global upload_task

    stats.incr("api_new_upload_accesses")
    request = json.loads(flask.request.data)
    build_id = request["id"]

    if type(build_id) != int:
        return flask.jsonify({"message": "Invalid build ID type"}), 400

    if build_id < 0:
        return flask.jsonify({"message": "Build ID out of range"}), 400

    if build_id in upload_queue:
        return flask.jsonify({}), 201

    with db().cursor() as cursor:
        cursor.execute("SELECT name, size FROM build WHERE id = %s;", (build_id,))

        if cursor.rowcount < 1:
            return flask.jsonify({"message": "Build ID is unknown"}), 400

        (build_name, build_size) = cursor.fetchone()

        cursor.execute(
            "SELECT location FROM build_source_local WHERE build = %s;",
            (build_id,),
        )

        if cursor.rowcount < 1:
            return flask.jsonify({"message": "Build is not available"}), 400

        (build_path,) = cursor.fetchone()

        cursor.execute(
            "SELECT * FROM build_source_online WHERE build = %s;",
            (build_id,),
        )

        if cursor.rowcount > 0:
            return flask.jsonify({}), 201

    stats.incr("upload_requests")
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


@app.route("/api/uploads/<int:build_id>", methods=["GET"])
def api_uploads_get(build_id):
    stats.incr("api_upload_accesses")

    if build_id in upload_queue:
        return flask.jsonify(upload_queue[build_id]), 200

    if build_id in upload_queue_failed:
        return flask.jsonify(upload_queue_failed[build_id]), 200

    return flask.jsonify({"message": "Build ID not in upload queue"}), 404


@app.route("/api/statistics")
def api_statistics():
    stats.incr("statistics_accesses")

    with db().cursor() as cursor, stats.timer("statistics_collection"):
        cursor.execute("SELECT COUNT(*), SUM(size), AVG(size) FROM build;")
        (build_count_known, build_size_known, build_size_average) = cursor.fetchone()

        cursor.execute(
            """
        SELECT COUNT(*), SUM(size) FROM build
        WHERE EXISTS (
            SELECT location FROM build_source_local
            WHERE build.id = build_source_local.build
        ) OR EXISTS (
            SELECT location FROM build_source_online
            WHERE build.id = build_source_online.build
        );
        """
        )
        (build_count_stored, build_size_stored) = cursor.fetchone()

        cursor.execute("SELECT COUNT(DISTINCT device) FROM build;")
        (device_count,) = cursor.fetchone()

        cursor.execute(
            """
            SELECT COUNT(*) FROM (
                SELECT DISTINCT device, version FROM build
            ) AS count;
        """
        )
        (device_version_count,) = cursor.fetchone()

        db().commit()

    stats.gauge("build_count_known", build_count_known)
    stats.gauge("build_size_known", build_size_known)
    stats.gauge("build_count_stored", build_count_stored)
    stats.gauge("build_size_stored", build_size_stored)
    stats.gauge("device_count", device_count)
    stats.gauge("device_version_count", device_version_count)

    statistics = {
        "build_count_known": build_count_known,
        "build_size_known": build_size_known,
        "build_count_stored": build_count_stored,
        "build_size_stored": build_size_stored,
        "build_size_average": build_size_average,
        "device_count": device_count,
        "device_version_count": device_version_count,
    }

    return flask.jsonify(statistics), 200


@app.route("/")
def overview():
    stats.incr("overview_accesses")
    with stats.timer("overview_serve"):
        return app.send_static_file("overview.html")


@app.route("/build/<int:build_id>", methods=["GET"])
def build_overview(build_id):
    stats.incr("build_overview_accesses")
    with stats.timer("build_overview_serve"):
        return app.send_static_file("build_overview.html")


def generate_digest_file(digest_type):
    def generate():
        stats.incr(f"{digest_type}sums_accesses")

        with db().cursor() as cursor, stats.timer(f"{digest_type}sums_retrieval"):
            cursor.execute(
                f"""
            SELECT build_hash_{digest_type}.hash AS md5,
                   build.name
            FROM build
            JOIN build_hash_{digest_type} ON build.id = build_hash_{digest_type}.build
            ORDER BY build.name ASC
            """
            )

            while row := cursor.fetchone():
                yield f"{row[0]}  {row[1]}\n"

    with stats.timer(f"{digest_type}sums_serve"):
        response = flask.make_response(generate(), 200)
        response.headers["Content-Type"] = "text/plain; charset=utf-8"
        return response


@app.route("/MD5SUMS")
def md5sums():
    return generate_digest_file("md5")


@app.route("/SHA1SUMS")
def sha1sums():
    return generate_digest_file("sha1")


@app.route("/SHA256SUMS")
def sha256sums():
    return generate_digest_file("sha256")


@app.route("/SHA512SUMS")
def sha512sums():
    return generate_digest_file("sha512")


def get_sitemap_sites(limit=None, page=0, **kwargs):
    # Page 0 is a special page where we dump static and extra pages.
    if page == 0:
        yield ""
        yield "MD5SUMS"
        yield "SHA1SUMS"
        yield "SHA256SUMS"
        yield "SHA512SUMS"

        if SITEMAP_EXTRA is not None:
            for site in SITEMAP_EXTRA.split(','):
                site = site.strip()

                if len(site) == 0:
                    continue

                yield site

        return

    query = "SELECT id FROM build WHERE build.available_upstream IS FALSE ORDER BY id ASC"

    if limit:
        query += f" LIMIT {int(limit)} OFFSET {(int(page) - 1) * int(limit)}"

    with db().cursor() as cursor:
        cursor.execute(query)

        while row := cursor.fetchone():
            yield f"build/{row[0]}"


@app.route("/sitemap.txt")
def sitemap_txt():
    kwargs = flask.request.args

    def generate():
        stats.incr("sitemap_txt_accesses")

        with stats.timer("sitemap_txt_generate"):
            for site in get_sitemap_sites(**kwargs):
                yield f"{SITEMAP_PREFIX}/{site}\n"

    response = flask.make_response(generate(), 200)
    response.headers["Content-Type"] = "text/plain; charset=utf-8"
    return response


@app.route("/sitemap.html")
def sitemap_html():
    kwargs = flask.request.args

    def generate():
        stats.incr("sitemap_html_accesses")

        yield "<!DOCTYPE html>\n"
        yield "<html>\n"
        yield "  <body>\n"

        with stats.timer("sitemap_html_generate"):
            for site in get_sitemap_sites(**kwargs):
                yield f"    <a href='/{site}'>/{site}</a>\n"

        yield "  </body>\n"
        yield "</html>\n"

    response = flask.make_response(generate(), 200)
    return response


if __name__ == "__main__":
    app.run(debug=False)
