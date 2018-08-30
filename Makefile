

PWD = $(shell pwd)

build:
	docker build -t dgarros/metric-collector .

clean:
	docker rmi dgarros/metric-collector

sh:
	docker run -t -i dgarros/metric-collector sh

test:
	python -m pytest
