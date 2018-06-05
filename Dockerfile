FROM python:3.6.5
LABEL maintainer="dgarros@gmail.com"

RUN mkdir /source
WORKDIR /source
USER root

COPY . /source
RUN pip install -r /source/requirements.txt

RUN python setup.py develop


