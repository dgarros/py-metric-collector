import logging
import requests

logger = logging.getLogger('collector')

def print_format_influxdb(datapoints):
    """
    Print all datapoints to STDOUT in influxdb format for Telegraf to pick them up
    """
    for data in format_datapoints_inlineprotocol(datapoints):
        print(data)

def post_format_influxdb(datapoints, addr="http://localhost:8186/write"):
    s = requests.session()
    for datapoint in format_datapoints_inlineprotocol(datapoints):
        s.post(addr, data=datapoint)

    logger.info('Sending Datapoint to: %s' % addr)

def format_datapoints_inlineprotocol(datapoints):
    """
    Format all datapoints with the inlineprotocol (influxdb)
    Return a list of string formatted datapoint
    """

    formatted_data = []

    ## Format Tags
    if datapoints is not None:
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
            formatted_data.append("{0},{1} {2}".format(datapoint['measurement'], tags, fields))
          else:
            formatted_data.append("{0} {1}".format(datapoint['measurement'], fields))

    return formatted_data
