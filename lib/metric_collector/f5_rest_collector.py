import logging
import time
# need to monkey patch this as this prevents the code from running in threads
import f5.bigip as bigip
bigip.HAS_SIGNAL = False

logger = logging.getLogger('f5_rest_collector')


class F5Collector(object):

    def __init__(self, host, address, credential, port=443, timeout=15, retry=3, parsers=None,
                 context=None):
        self.hostname = host
        self.host = address
        self.credential = credential
        self.__port = port
        self.__timeout = timeout
        self.__retry = retry
        self.__is_connected = False
        self.parsers = parsers
        if context:
            self.context = {k: v for i in context for k, v in i.items()}
        else:
            self.context = None
        self.facts = {}

    def connect(self):
        logger.info('Connecting to host: %s at %s', self.hostname, self.host)

        use_token = False
        user = self.credential.get('username')
        passwd = self.credential.get('password')
        if self.credential['method'] == 'vault':
            user, passwd = self._get_credentials_from_vault()
        if self.credential.get('use_token', 'false').lower() == 'true':
            use_token = True
        if not user or not passwd:
            logger.error('Invalid or no credentials specified')
            return
        for retry in range(self.__retry):
            try:
                self.mgmt = bigip.ManagementRoot(
                    self.host, user, passwd,
                    port=self.__port, timeout=self.__timeout, token=use_token)
                self.__is_connected = True
                break
            except Exception as ex:
                logger.debug('Failed to connect on %d: %s,  retrying', retry, str(ex))
                time.sleep(2)
                continue
        if not self.is_connected():
            logger.error('Failed to connect to %s at %s', self.hostname, self.host)
            return

    def collect_facts(self):
        logger.info('[%s]: Collecting Facts on device', self.hostname)

        self.facts['tmos_version'] = self.mgmt.tmos_version
        if self.hostname:
            self.facts['device'] = self.hostname
        else:
            self.facts['device'] = self.mgmt.hostname

        # TODO(Mayuresh) Collect any other relevant facts here

    def execute_query(self, query, timeout=None):

        base_url = 'https://{}/'.format(self.host)
        try:
            query = base_url + query
            logger.debug('[%s]: execute : %s', self.hostname, query)
            timeout = timeout or self.__timeout
            result = self.mgmt.icrs.get(query, timeout=timeout)
            return result.json()
        except Exception as ex:
            logger.error('Failed to execute query: %s on %s: %s', query, self.hostname, str(ex))
            return

    def collect(self, command, timeout=None):

        # find the command/query to execute
        logger.debug('[%s]: parsing : %s', self.hostname, command)
        parser = self.parsers.get_parser_for(command)
        try:
            raw_data = self.execute_query(parser['data']['parser']['query'], timeout=timeout)
        except TypeError as e:
            logger.error('Parser returned no data. Message: {}'.format(e))
            raw_data = None
        if not raw_data:
            return None
        datapoints = self.parsers.parse(command, raw_data)

        if datapoints is not None:
            measurement = self.parsers.get_measurement_name(input=command)
            timestamp = time.time_ns()
            for datapoint in datapoints:
                if not datapoint['fields']:
                    continue
                if datapoint['measurement'] is None:
                    datapoint['measurement'] = measurement
                datapoint['tags'].update(self.facts)
                if self.context:
                    datapoint['tags'].update(self.context)
                datapoint['timestamp'] = timestamp
                yield datapoint

        else:
            logger.warn('No parser found for command > %s', command)
            return None

    def is_connected(self):
        return self.__is_connected

    def close(self):
        # rest connection is not stateful so nothing to close
        return
