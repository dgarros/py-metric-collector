

PWD = $(shell pwd)

# build:
# 	docker build -t juniper/open-nti-input-netconf .
#
# run:
# 	docker run -t -i -v $(PWD):/data juniper/open-nti /usr/bin/python /data/netconf-collector.py -s

# telegraf:
# 	docker run -t -i -v $(PWD):/data juniper/open-nti telegraf -debug -config /data/telegraf.toml

test:
	python -m pytest
