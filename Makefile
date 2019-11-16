DOCKER_IMG = chi1-docker-registry.simulprod.com/roblox/neteng-collector
DOCKER_TAG = 0.1.21-1.0.5

PWD = $(shell pwd)

build:
	docker build -t $(DOCKER_IMG):$(DOCKER_TAG) .

push:
	docker push $(DOCKER_IMG):$(DOCKER_TAG)

clean:
	docker rmi $(DOCKER_IMG):$(DOCKER_TAG)

sh:
	docker run -t -i $(DOCKER_IMG):$(DOCKER_TAG) sh

test:
	python -m pytest
