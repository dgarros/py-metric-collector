

PWD = $(shell pwd)

build:
	docker build -t juniper/netconf-collector .

run:
	docker run -t -i -v $(PWD):/data juniper/netconf-collector /usr/bin/python /data/netconf-collector.py -s --hosts=dev-01.yaml --commands=commands.yaml --credential=credentials.yaml

telegraf:
	docker run -t -i -v $(PWD):/data juniper/netconf-collector /usr/bin/telegraf --debug --config /data/telegraf.toml

sh:
	docker run -t -i juniper/netconf-collector sh

test:
	python -m pytest
