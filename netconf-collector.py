#!/usr/bin/env python
# coding: utf-8
# Authors: efrain@juniper.net psagrera@juniper.net
# Version 2.0  20160124

from datetime import datetime # In order to retreive time and timespan
from datetime import timedelta # In order to retreive time and timespan

from lxml import etree  # Used for xml manipulation
from pprint import pformat
from pprint import pprint
import argparse   # Used for argument parsing
import json
import logging
import logging.handlers
import os  # For exec to work
import pprint
import re # For regular expression usage
import requests
import string
import string  # For split multiline script into multiple lines
import StringIO   # Used for file read/write
import sys  # For exec to work
import threading
import time
# import xmltodict
import yaml
import copy

from lib import parser_manager
from lib import netconf_collector

logging.getLogger("paramiko").setLevel(logging.INFO)
logging.getLogger("ncclient").setLevel(logging.WARNING) # In order to remove http request from ssh/paramiko
logging.getLogger("requests").setLevel(logging.INFO)
logging.getLogger("urllib3").setLevel(logging.WARNING)  # In order to remove http request from InfluxDBClient

####################################################################################
####################################################################################
# Defining the classes and procedures used later on the script
####################################################################################
####################################################################################

def get_target_hosts():
    my_target_hosts = {}
    for host in sorted(hosts.keys()):
        for tag in tag_list:
            for hosts_tag in hosts[host].split():
                if re.search(tag, hosts_tag, re.IGNORECASE):
                    my_target_hosts[host] = 1
    return my_target_hosts.keys()

def get_target_commands(my_host):
  my_host_tags = hosts[my_host]
  my_target_commands = {}
  for group_command in sorted(general_commands.keys()):
    for my_host_tag in my_host_tags.strip().split():
      for command_tag in general_commands[group_command]["tags"].split():
        if re.search(my_host_tag, command_tag, re.IGNORECASE):
          if "netconf" in general_commands[group_command].keys():
            cmd_list = []
            if isinstance(general_commands[group_command]["netconf"], str):
              cmd_list = general_commands[group_command]["netconf"].strip().split("\n")
            else:
              cmd_list = general_commands[group_command]["netconf"]

            for cmd in cmd_list:
              my_target_commands[cmd] = 1

  return my_target_commands.keys()

def get_credentials(my_host):
    my_host_tags = hosts[my_host]
    my_target_credentials = {'username': None,
                             'password': None,
                             'port': 830,
                             'method': None,
                             'key_file': None }

    for credential in sorted(credentials.keys()):
        for my_host_tag in my_host_tags.strip().split():
            for credential_tag in credentials[credential]["tags"].split():
                if re.search(my_host_tag, credential_tag, re.IGNORECASE):

                    if not ("username" in credentials[credential].keys()):
                        logger.error("Missing username information")
                        sys.exit(0)
                    else:
                        my_target_credentials['username'] = credentials[credential]["username"]

                    ## Port
                    if ("port" in credentials[credential].keys()):
                        my_target_credentials['port'] = credentials[credential]["port"]

                    if ("method" in credentials[credential].keys()):
                        my_target_credentials['method'] = credentials[credential]["method"]


                        if (credentials[credential]["method"] == "key"):
                            if not ("key_file" in credentials[credential].keys()):
                                logger.error("Missing key_file information")
                                sys.exit(0)

                            my_target_credentials['key_file'] = credentials[credential]["key_file"]
                            return my_target_credentials

                        elif (credentials[credential]["method"] == "enc_key"):
                            if not ("key_file" in credentials[credential].keys()):
                                logger.error("Missing key_file information")
                                sys.exit(0)

                            if not ("password" in credentials[credential].keys()):
                                logger.error("Missing password information")
                                sys.exit(0)

                            my_target_credentials['password'] = credentials[credential]["password"]
                            my_target_credentials['key_file'] = credentials[credential]["key_file"]

                            return my_target_credentials

                        elif (credentials[credential]["method"] == "password"):
                            my_target_credentials['password'] = credentials[credential]["password"]
                            my_target_credentials['key_file'] = credentials[credential]["key_file"]

                            return my_target_credentials

                        else:
                            logger.error("Unknown authentication method found")
                            sys.exit(0)
                    else:
                        if not ("password" in credentials[credential].keys()):
                            logger.error("Missing password information")
                            sys.exit(0)
                        my_target_credentials['password'] = credentials[credential]["password"]

                        return my_target_credentials

def print_format_influxdb(datapoints):
    """
    Print all datapoints to STDOUT in influxdb format for Telegraf to pick them up
    """

    ## Format Tags
    if datapoints is not None:
      for datapoint in datapoints:
          tags = ''
          first_tag = 1
          for tag, value in datapoint['tags'].iteritems():

              if first_tag == 1:
                  first_tag = 0
              else:
                  tags = tags + ','

              tags = tags + '{0}={1}'.format(tag,value)

          ## Format Measurement
          fields = ''
          first_field = 1
          for tag, value in datapoint['fields'].iteritems():

              if first_field == 1:
                  first_field = 0
              else:
                  fields = fields + ','

              fields = fields + '{0}={1}'.format(tag,value)

          print "{0},{1} {2}".format(datapoint['measurement'], tags, fields)

      logger.info('Printing Datapoint to STDOUT:')

################################################################################################
################################################################################################
################################################################################################

# SCRIPT STARTS HERE

################################################################################################
# Create and Parse Arguments
################################################################################################

if getattr(sys, 'frozen', False):
    # frozen
    BASE_DIR = os.path.dirname(sys.executable)
else:
    # unfrozen
    BASE_DIR = os.path.dirname(os.path.realpath(__file__))

full_parser = argparse.ArgumentParser()
full_parser.add_argument("--tag", nargs='+', help="Collect data from hosts that matches the tag")
full_parser.add_argument("-c", "--console", action='store_true', help="Console logs enabled")
full_parser.add_argument( "--test", action='store_true', help="Use emulated Junos device")
full_parser.add_argument("-s", "--start", action='store_true', help="Start collecting (default 'no')")
full_parser.add_argument("-i", "--input", default=BASE_DIR, help="Directory where to find input files")

full_parser.add_argument("--loglvl", default=20, help="Logs verbosity, 10-debug, 50 Critical")

full_parser.add_argument("--logdir", default="logs", help="Directory where to store logs")
full_parser.add_argument("--parserdir", default="parsers", help="Directory where to find parsers")
full_parser.add_argument("--timeout", default=600, help="Default Timeout for Netconf session")
full_parser.add_argument("--delay", default=3, help="Delay Between Commands")
full_parser.add_argument("--retry", default=5, help="Max retry")
full_parser.add_argument("--usehostname", default=True, help="Use hostname from device instead of IP")
full_parser.add_argument("--dbschema", default=2, help="Format of the output data")

full_parser.add_argument("--host", default=None, help="Host DNS or IP")
full_parser.add_argument("--hosts", default="hosts.yaml", help="Hosts file in yaml")
full_parser.add_argument("--commands", default="commands.yaml", help="Commands file in Yaml")
full_parser.add_argument("--credentials", default="credentials.yaml", help="Credentials file in Yaml")

full_parser.add_argument("--output", default="influxdb", help="Format of the output")

dynamic_args = vars(full_parser.parse_args())

## Change BASE_DIR_INPUT if we are in "test" mode
if dynamic_args['test']:
    BASE_DIR_INPUT = dynamic_args['input']

################################################################################
# Loading YAML Default Variables
################################################################################

db_schema = dynamic_args['dbschema']
max_connection_retries = dynamic_args['retry']
delay_between_commands = dynamic_args['delay']
logging_level = dynamic_args['loglvl']
default_junos_rpc_timeout = dynamic_args['timeout']
use_hostname = dynamic_args['usehostname']

################################################################################################
# Validate Arguments
###############################################################################################
pp = pprint.PrettyPrinter(indent=4)

tag_list = []
###  Known and fixed arguments
if dynamic_args['tag']:
    tag_list = dynamic_args['tag']
else:
    tag_list = [ ".*" ]

if not(dynamic_args['start']):
    logger.error('Missing <start> option, so nothing to do')
    sys.exit(0)

################################################################################
################################################################################
# Netconf Collector starts here start
################################################################################
################################################################################

# Setting up logging directories and files
timestamp = time.strftime("%Y-%m-%d", time.localtime(time.time()))
log_dir = BASE_DIR + "/" + dynamic_args['logdir']
logger = logging.getLogger("main")

if not os.path.exists(log_dir):
    os.makedirs(log_dir, 0755)

formatter = '%(asctime)s %(name)s %(levelname)s %(threadName)-10s:  %(message)s'
logging.basicConfig(filename=log_dir + "/"+ timestamp + '_open-nti.log',
                    level=logging_level,
                    format=formatter,
                    datefmt='%Y-%m-%d %H:%M:%S')

if dynamic_args['console']:
    logger.info("Console logs enabled")
    console = logging.StreamHandler()
    console.setLevel(logging.DEBUG)
    logging.getLogger('').addHandler(console)

###########################################################
#  LOAD all credentials in a dict
###########################################################
credentials = {}
credentials_yaml_file = ''

if os.path.isfile(dynamic_args['credentials']):
  credentials_yaml_file = dynamic_args['credentials']
else:
  credentials_yaml_file = BASE_DIR + "/"+ dynamic_args['credentials']

logger.info('Importing credentials file: %s ',credentials_yaml_file)
try:
    with open(credentials_yaml_file) as f:
        credentials = yaml.load(f)
except Exception, e:
    logger.error('Error importing credentials file: %s', credentials_yaml_file)
    sys.exit(0)

###########################################################
#  LOAD all hosts with their tags in a dict              ##
#  if 'host' is provided, use that instead of the file   ##
###########################################################
hosts = {}
if dynamic_args['host']:
  hosts[dynamic_args['host']] = ' '.join(tag_list)
else:
  hosts_yaml_file = ''
  hosts = {}

  if os.path.isfile(dynamic_args['hosts']):
    hosts_yaml_file = dynamic_args['hosts']
  else:
    hosts_yaml_file = BASE_DIR + "/"+ dynamic_args['hosts']

  logger.info('Importing host file: %s ',hosts_yaml_file)
  try:
    with open(hosts_yaml_file) as f:
      hosts = yaml.load(f)
  except Exception, e:
    logger.error('Error importing host file: %s', hosts_yaml_file)
    sys.exit(0)

###########################################################
#  LOAD all commands with their tags in a dict           ##
###########################################################
commands_yaml_file = ''
commands = []

if os.path.isfile(dynamic_args['commands']):
  commands_yaml_file = dynamic_args['commands']
else:
  commands_yaml_file = BASE_DIR + "/"+ dynamic_args['commands']

logger.info('Importing commands file: %s ',commands_yaml_file)
with open(commands_yaml_file) as f:
    try:
        for document in yaml.load_all(f):
            commands.append(document)
    except Exception, e:
        logger.error('Error importing commands file: %s', commands_yaml_file)
        sys.exit(0)

general_commands = commands[0]
###########################################################
#  LOAD all parsers                                      ##
###########################################################
parsers_manager = parser_manager.ParserManager( parser_dir = dynamic_args['parserdir'] )

if __name__ == "__main__":

  logger.debug('Getting hosts that matches the specified tags')
  #  Get all hosts that matches with the tags
  target_hosts = get_target_hosts()
  logger.debug('The following hosts are being selected: %s', target_hosts)

  use_threads = False

  if use_threads:
    target_hosts_lists = [target_hosts[x:x+len(target_hosts)/max_collector_threads+1] for x in range(0, len(target_hosts), len(target_hosts)/max_collector_threads+1)]

    jobs = []
    i=1
    for target_hosts_list in target_hosts_lists:
      logger.info('Collector Thread-%s scheduled with following hosts: %s', i, target_hosts_list)
      thread = threading.Thread(target=collector, kwargs={"host_list":target_hosts_list})
      jobs.append(thread)
      i=i+1

    # Start the threads
    for j in jobs:
      j.start()

      # Ensure all of the threads have finished
      for j in jobs:
        j.join()
  else:
    # Execute everythings in the main thread
    for host in target_hosts:
      target_commands = get_target_commands(host)
      credential = get_credentials(host)

      # pp.pprint(target_commands)
      # pp.pprint(credential)
      logger.info('Collector starting for: %s', host)
      jdev = netconf_collector.NetconfCollector(host=host, credential=credential, parsers=parsers_manager)
      jdev.connect()
      jdev.collect_facts()
      for command in target_commands:
        values = jdev.collect(command=command)
        print_format_influxdb(values)
        # values = parsers_manager.parse(input=command, data=data)
        # pp.pprint(values)
