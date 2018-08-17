FROM python:3.7
LABEL maintainer="dgarros@gmail.com"

RUN mkdir /source
WORKDIR /source
USER root

COPY . /source
RUN pip install -r /source/requirements.txt

RUN python setup.py develop

RUN apt-get -y update
RUN apt-get -y install vim

ENTRYPOINT ["/usr/local/bin/metric-collector"]
