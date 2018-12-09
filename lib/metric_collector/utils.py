import logging
import requests
from itertools import chain, islice, cycle

logger = logging.getLogger('collector')


def print_format_influxdb(datapoints):
    """
    Print all datapoints to STDOUT in influxdb format for Telegraf to pick them up
    """
    for data in format_datapoints_inlineprotocol(datapoints):
        print(data)


def post_format_influxdb(datapoints, addr="http://localhost:8186/write"):
    with requests.session() as s:
        for chunk in chunks(format_datapoints_inlineprotocol(datapoints)):
            resp = s.post(addr, data='\n'.join(chunk), timeout=5)
            if resp.status_code not in [200, 201, 204]:
                logger.warning('Failed to send datapoint to influx')

    logger.info('Sending Datapoint to: %s' % addr)


def format_datapoints_inlineprotocol(datapoints):
    """
    Format all datapoints with the inlineprotocol (influxdb)
    Return a list of string formatted datapoint
    """

    ## Format Tags
    if not datapoints:
        return
    for datapoint in datapoints:
        tags = ''
        first_tag = 1
        for tag, value in datapoint['tags'].items():

            if first_tag == 1:
                first_tag = 0
            else:
                tags = tags + ','

            tags = tags + '{0}={1}'.format(tag,value)

        ## Format Measurement
        fields = ''
        first_field = 1
        for tag, value in datapoint['fields'].items():

            if first_field == 1:
                first_field = 0
            else:
                fields = fields + ','

            fields = fields + '{0}={1}'.format(tag,value)

        if datapoint['tags']:
          formatted_data = "{0},{1} {2} {3}".format(datapoint['measurement'], tags, fields, datapoint['timestamp'])
        else:
          formatted_data = "{0} {1} {2}".format(datapoint['measurement'], fields, datapoint['timestamp'])
        yield formatted_data


def chunks(iterable, size=1000):
    """ Splits an interable into n chunks. Useful for sending groups of datapoints at once """
    iterator = iter(iterable)
    for first in iterator:
        yield chain([first], islice(iterator, size - 1))


class Cycle(cycle):
    """ wraps itertools.cycle """
    def __init__(self, iterable):
        self.len = len(iterable)
        cycle.__init__(iterable)
    def __len__(self):
        return self.len
