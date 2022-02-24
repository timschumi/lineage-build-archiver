FROM docker.io/python:3

WORKDIR /usr/src/app

COPY . .
RUN pip install --no-cache-dir -r requirements.txt

ENV UPDATE_INTERVAL=1440
VOLUME /builds

ENTRYPOINT [ "./entrypoint.sh" ]
