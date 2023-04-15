#!/usr/bin/env python3

"""
Copyright (C) 2023 Tim Schumacher

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
import botocore.exceptions
import flask
import flask_caching
import json
import logging
import os
import threading
import typing

logging.basicConfig(
    format="%(asctime)s %(levelname)-8s %(message)s",
    level=logging.INFO,
    datefmt="%Y-%m-%d %H:%M:%S",
)

app = flask.Flask(__name__, static_url_path="", static_folder="static")
app_cache = flask_caching.Cache(app, config={"CACHE_TYPE": "SimpleCache"})

S3_DOWNLOAD_URL = os.environ.get("S3_DOWNLOAD_URL")
S3_ENDPOINT = os.environ.get("S3_ENDPOINT")
S3_BUCKET = os.environ.get("S3_BUCKET")
S3_ACCESS_KEY_ID = os.environ.get("S3_ACCESS_KEY_ID")
S3_ACCESS_KEY = os.environ.get("S3_ACCESS_KEY")

b2 = boto3.resource(
    service_name="s3",
    endpoint_url=S3_ENDPOINT,
    aws_access_key_id=S3_ACCESS_KEY_ID,
    aws_secret_access_key=S3_ACCESS_KEY,
    config=botocore.config.Config(signature_version="s3v4"),
)
b2_bucket = b2.Bucket(S3_BUCKET)


@app.route("/api/builds", methods=["GET"])
@app_cache.cached(timeout=3600)
def api_builds_list():
    builds = []

    for f in reversed(list(b2_bucket.objects.all())):
        if not f.key.endswith(".zip"):
            continue

        builds.append(
            {
                "filename": f.key,
                "filesize": f.size,
                "url": S3_DOWNLOAD_URL.format(bucket=S3_BUCKET, file=f.key),
            }
        )

    return flask.jsonify(builds), 200


@app.route("/")
def overview() -> str:
    with open("template/overview.tpl", "r") as file:
        return file.read()


if __name__ == "__main__":
    app.run(debug=False)
