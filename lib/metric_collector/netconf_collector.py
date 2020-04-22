import logging
import pprint
# from pyez_mock import mocked_device, rpc_reply_dict
from jnpr.junos import *
from jnpr.junos import Device
from jnpr.junos.exception import *
from jnpr.junos.utils.start_shell import StartShell
from lxml import etree
import time

logger = logging.getLogger('netconf_collector')

pp = pprint.PrettyPrinter(indent=4)

class NetconfCollector():

  def __init__(self, 
        host=None, 
        address=None, 
        credential={}, 
        test=False, 
        timeout=15, 
        retry=3, 
        use_hostname=True, 
        parsers=None, 
        context=None,
        collect_facts=True):

    self.__is_connected = False
    self.__is_test = test
    self.__use_hostname = use_hostname
    self.__timeout = timeout
    self.__retry = retry
    self.__collect_facts = collect_facts

    self.host = address
    self.hostname = host
    if context:
        self.context = {k: v for i in context for k, v in i.items()}
    else:
        self.context = None
    self.__credential = credential

    self.pyez = None
    self.facts = {}

    self.parsers = parsers

  def __add_datapoints(self):

      return True

  def connect(self):

    logger.info('Connecting to host: %s', self.hostname)

    ## TODO Cleanup
    # target_commands = get_target_commands(host)
    # timestamp_tracking={}
    # timestamp_tracking['collector_start'] = int(datetime.today().strftime('%s'))

    # Establish connection to hosts

    if self.__is_test:
       #Open an emulated Junos device instead of connecting to the real one
    #    _rpc_reply_dict = rpc_reply_dict()
    #    _rpc_reply_dict['dir'] = BASE_DIR_INPUT
       #
    #    self.pyez = mocked_device(_rpc_reply_dict)
    #    # First collect all kpi in datapoints {} then at the end we insert them into DB (performance improvement)
      self.__is_connected = True
      return self.__is_connected

    ## Define connection parameter
    if self.__credential['method'] in "key":
        self.pyez = Device( user=self.__credential['username'],
                      host=self.host,
                      ssh_private_key_file=self.__credential['key_file'],
                      gather_facts=False,
                      auto_probe=True,
                      port=self.__credential['port'] )

    elif self.__credential['method'] in "enc_key":
        self.pyez = Device( user=self.__credential['username'],
                      host=self.host,
                      ssh_private_key_file=self.__credential['key_file'],
                      password=self.__credential['password'],
                      gather_facts=False,
                      auto_probe=True,
                      port=self.__credential['port'])

    else: # Default is
        self.pyez = Device( user=self.__credential['username'],
                      host=self.host,
                      password=self.__credential['password'],
                      gather_facts=False,
                      auto_probe=True,
                      port=self.__credential['port'])

    ## Try to open connection
    for i in range(1, self.__retry+1):
      try:
            self.pyez.open()
            self.pyez.timeout = self.__timeout
            self.__is_connected = True
            break
      except Exception as e:
          if i < self.__retry:
            logger.error('[%s]: Connection failed %s time(s), retrying....', self.hostname, i)
            time.sleep(1)
            continue
          else:
            logging.exception(e)
            self.__is_connected = False  # Notify about the specific problem with the host BUT we need to continue with our list

  def collect_facts(self):

    if not self.__is_connected:
      return

    # Collect Facts about the device (if enabled)
    if self.__collect_facts:
      logger.info('[%s]: Collection Facts on device', self.hostname)
      self.pyez.facts_refresh()

      if self.pyez.facts['version']:
        self.facts['version'] = self.pyez.facts['version']
      else:
        self.facts['version'] = 'unknown'

      self.facts['product-model'] = self.pyez.facts['model']

      ## Based on parameter defined in config file
      if self.__use_hostname and self.pyez.facts['hostname'] != self.hostname:
        hostname = self.pyez.facts['hostname']
        logger.info('[%s]: Host will now be referenced as : %s', self.hostname, hostname)
        self.hostname = hostname
      else:
        logger.info('[%s]: Host will be referenced as : %s', self.hostname, self.hostname)


    self.facts['device']=self.hostname

    return True

  def execute_command(self,command=None):

    try:
      logger.debug('[%s]: execute : %s', self.hostname, command)
      # the data returned is already in etree format
      command_result = self.pyez.rpc.cli(command, format="xml")
    except RpcError as err:
      rpc_error = err.__repr__()
      logger.error("Error found on <%s> executing command: %s, error: %s:", self.hostname, command ,rpc_error)
      return None

    return command_result

  def collect(self, command=None):

    # find the command to execute from the parser directly
    parser = self.parsers.get_parser_for(command)
    data = self.execute_command(parser['data']['parser']['command'])
    
    if data is None:
        return None
    if parser['data']['parser']['type'] == 'textfsm':
        data = etree.tostring(data)
    datapoints = self.parsers.parse(input=command, data=data)
    
    if datapoints is not None:

      measurement = self.parsers.get_measurement_name(input=command)

      timestamp = time.time_ns()
      for datapoint in datapoints:
        if not datapoint['fields']:
            continue
        if datapoint['measurement'] == None:
          datapoint['measurement'] = measurement
        datapoint['tags'].update(self.facts)
        if self.context:
          datapoint['tags'].update(self.context)
        datapoint['timestamp'] = timestamp
        yield datapoint

    else:
      logger.warn('No parser found for command > %s',command)
      return None

  def is_connected(self):
    return self.__is_connected

  def close(self):
    if self.__is_connected:
      self.pyez.close()
