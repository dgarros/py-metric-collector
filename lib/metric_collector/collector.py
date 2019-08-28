import logging
import itertools
import requests
import time
import os
from metric_collector import netconf_collector
from metric_collector import json_collector
from metric_collector import utils

logger = logging.getLogger('collector')
global_measurement_prefix = 'metric_collector'

class Collector:

    def __init__(self, hosts_manager, parser_manager, output_type, output_addr, collect_facts=True):
        self.hosts_manager = hosts_manager
        self.parser_manager = parser_manager
        self.output_type = output_type
        self.output_addr = output_addr
        self.collect_facts = collect_facts

    def collect(self, worker_name, hosts=None, host_cmds=None, cmd_tags=None):
        if not hosts and not host_cmds:
            logger.error('Collector: Nothing to collect')
            return
        if hosts:
            host_cmds = {}
            tags = cmd_tags or ['.*']
            for host in hosts:
                cmds = self.hosts_manager.get_target_commands(host, tags=tags) 
                target_cmds = []
                for c in cmds:
                    target_cmds += c['commands']
                host_cmds[host] = target_cmds
               
        for host, target_commands in host_cmds.items():
            values = []
            credential = self.hosts_manager.get_credentials(host)

            host_reachable = False

            logger.info('Collector starting for: %s', host)
            host_address = self.hosts_manager.get_address(host)
            host_context = self.hosts_manager.get_context(host)
            device_type = self.hosts_manager.get_device_type(host)

            if device_type == 'juniper':
                dev = netconf_collector.NetconfCollector(
                        host=host, address=host_address, credential=credential,
                        parsers=self.parser_manager, context=host_context, collect_facts=self.collect_facts)
            elif device_type in ['arista', 'f5']:
                dev = json_collector.JsonCollector(
                    host=host, address=host_address, credential=credential,
                    parsers=self.parser_manager, context=host_context)
            dev.connect()

            if dev.is_connected():
                dev.collect_facts()
                host_reachable = True

            else:
                logger.error('Unable to connect to %s, skipping', host)
                host_reachable = False

            time_execution = 0
            cmd_successful = 0
            cmd_error = 0

            if host_reachable:
                time_start = time.time()

                ### Execute commands on the device
                for command in target_commands:
                    try:
                        logger.info('[%s] Collecting > %s' % (host,command))
                        data = dev.collect(command)  # returns a generator
                        if data:
                            values.append(data)
                            cmd_successful += 1

                    except Exception as err:
                        cmd_error += 1
                        logger.error('An issue happened while collecting %s on %s > %s ' % (host,command, err))
                        logger.error(traceback.format_exc())

                ### Save collector statistics
                time_end = time.time()
                time_execution = time_end - time_start

            host_time_datapoint = [{
                'measurement': global_measurement_prefix + '_host_collector_stats',
                'tags': {
                    'device': dev.hostname,
                    'worker_name': worker_name
                },
                'fields': {
                    'execution_time_sec': "%.4f" % time_execution,
                    'nbr_commands':  cmd_successful + cmd_error,
                    'nbr_successful_commands':  cmd_successful,
                    'nbr_error_commands':  cmd_error,
                    'reacheable': int(host_reachable),
                    'unreacheable': int(not host_reachable)
                },
                'timestamp': time.time_ns(),
            }]

            host_time_datapoint[0]['tags'].update(dev.context)
            
            if os.environ.get('NOMAD_JOB_NAME'):
                host_time_datapoint[0]['tags']['nomad_job_name'] = os.environ['NOMAD_JOB_NAME']
            if os.environ.get('NOMAD_ALLOC_INDEX'):
                host_time_datapoint[0]['tags']['nomad_alloc_index'] = os.environ['NOMAD_ALLOC_INDEX']
            if os.environ.get('NOMAD_ALLOC_ID'):
                host_time_datapoint[0]['tags']['nomad_alloc_id'] = os.environ['NOMAD_ALLOC_ID']

            values.append((n for n in host_time_datapoint))
            values = itertools.chain(*values)

            ### Send results to the right output
            try:
                if self.output_type == 'stdout':
                    utils.print_format_influxdb(values)
                elif self.output_type == 'http':
                    utils.post_format_influxdb(values, self.output_addr)
                else:
                    logger.warn('Collector: Output format unknown: {}'.format(self.output_type))
            except Exception as ex:
                logger.exception("Hit exception trying to post to influx")

            if host_reachable:
                dev.close()
