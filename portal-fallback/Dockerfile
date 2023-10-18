FROM docker.io/python:3-bullseye

WORKDIR /usr/src/app

COPY . .
RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 8080

CMD gunicorn -b 0.0.0.0:8080 -w 1 portal:app
