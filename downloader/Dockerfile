FROM docker.io/python:3-bullseye

WORKDIR /usr/src/app

COPY . .
RUN pip install --no-cache-dir -r requirements.txt

ENV DOWNLOAD_ARGS=""
ENV PRUNE_ARGS=""
ENV STORAGE_ROOT=/builds
VOLUME /builds

CMD [ "./entrypoint.sh" ]
