FROM python:3.7.0-alpine3.8
LABEL maintainer="dgarros@gmail.com"


RUN mkdir /source
WORKDIR /source
USER root

RUN apk add --no-cache build-base python3-dev py-lxml \
    libxslt-dev libxml2-dev libffi-dev openssl-dev \
    ca-certificates openssl

COPY . /source
RUN pip install -r /source/requirements.txt

RUN python setup.py develop

ENTRYPOINT ["/usr/local/bin/metric-collector"]
