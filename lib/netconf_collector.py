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

  def __init__( self, host=None, credential={}, test=False, timeout=60, retry=5, use_hostname=True, parsers=None ):
    self.__is_connected = False
    self.__is_test = test
    self.__use_hostname = use_hostname
    self.__timeout = timeout
    self.__retry = retry

    self.host = host
    self.hostname = host
    self.__credential = credential

    self.pyez = None
    self.datapoints = []
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
      except Exception, e:
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

    # Collect Facts about the device
    logger.info('[%s]: Collection Facts on device', self.hostname)
    self.pyez.facts_refresh()

    if self.pyez.facts['version']:
      self.facts['version'] = self.pyez.facts['version']
    else:
      self.facts['version'] = 'unknown'

    self.facts['product-model'] = self.pyez.facts['model']

    ## Based on parameter defined in config file
    if self.__use_hostname:
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
      # Remember... all rpc must have format=xml at execution time,
      command_result = self.pyez.rpc.cli(command, format="xml")
    except RpcError as err:
      rpc_error = err.__repr__()
      logger.error("Error found on <%s> executing command: %s, error: %s:", self.hostname, command ,rpc_error)
      return False

    return etree.tostring(command_result)

  def collect( self, command=None):

    raw_data = self.execute_command(command=command)
    datapoints = self.parsers.parse(input=command, data=raw_data)
    
    if datapoints is not None:

    ## For now, generate_measurement from command
      measurement = command.replace(' ','_')
      measurement = measurement.replace('show_','')

      to_return = []
      for datapoint in datapoints:
        datapoint['measurement'] = measurement
        datapoint['tags'].update(self.facts)
        to_return.append(datapoint)

      return to_return
    else:
      logger.debug ('Not parser found for command',command)
      return None
