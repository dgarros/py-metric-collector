import logging
import queue
import threading
import time
import os
from metric_collector import host_manager, parser_manager, collector, utils

logger = logging.getLogger('scheduler')

class Scheduler:

    def __init__(self, creds_conf, cmds_conf, parsers_dir, output_type, output_addr,
                 max_worker_threads=1, use_threads=True, num_threads_per_worker=10,
                 collector_timeout=30):
        self.workers = {}
        self.working = set()
        self.host_mgr = host_manager.HostManager(credentials=creds_conf, commands=cmds_conf)
        self.parser_mgr = parser_manager.ParserManager(parser_dirs=parsers_dir)
        self.collector = collector.Collector(self.host_mgr, self.parser_mgr, output_type, output_addr,
            timeout=collector_timeout)
        self.max_worker_threads = max_worker_threads
        self.output_type = output_type
        self.output_addr = output_addr
        self.use_threads = use_threads
        self.num_threads_per_worker = num_threads_per_worker
        # default worker that is started if there are no hosts to schedule
        self.default_worker = Worker(
            120, self.collector, self.output_type, self.output_addr,
            self.use_threads, self.num_threads_per_worker)
        self.default_worker.set_name('Default-120sec')

    def _get_worker(self, interval, refresh=False):
        ''' Returns a worker thread for a given interval. If max_worker_threads is
            reached, then it cycles through the existing workers
        '''
        interval_workers = self.workers.get(interval, [])
        if refresh and interval_workers and not isinstance(interval_workers, list):
            return next(interval_workers)
        if len(interval_workers) == self.max_worker_threads:
            if isinstance(interval_workers, list):
                interval_workers = utils.Cycle(interval_workers)
                self.workers[interval] = interval_workers
            return next(interval_workers)
        new_worker = Worker(interval, self.collector, self.output_type, self.output_addr,
                            self.use_threads, self.num_threads_per_worker)
        new_worker.set_name('Worker-{}sec-{}'.format(interval, len(interval_workers) + 1))
        interval_workers.append(new_worker)
        self.workers[interval] = interval_workers
        return new_worker

    def _get_hostcmds(self, hosts, cmd_tags):
        ''' Group all the hosts by the intervals/commands to be run on them '''
        hostcmds = {}
        for host in hosts:
            target_commands = self.host_mgr.get_target_commands(host, tags=cmd_tags)
            for cmd in target_commands:
                cmds_per_interval = hostcmds.setdefault(host, {}).setdefault(cmd['interval_secs'], [])
                cmds_per_interval += cmd['commands']
        return hostcmds

    def init_workers(self):
        for worker in self.working:
            worker.init()

    def add_hosts(self, hosts_conf, host_tags=None, cmd_tags=None, refresh=False):
        '''  Create worker threads per interval and round-robin the hosts amongst them '''
        if not hosts_conf:
            logger.error('Scheduler: No hosts')
            return
        self.init_workers()
        # update host manager
        self.host_mgr.update_hosts(hosts_conf)
        hosts = self.host_mgr.get_target_hosts(tags=host_tags or ['.*'])
        logger.debug('The following hosts are being selected: %s', hosts)
        tags = cmd_tags or ['.*']
        hostcmds = self._get_hostcmds(hosts, tags)
        if not hostcmds:
            logger.error('Scheduler: No commands found to collect')
            return
        for host, interval_cmds in hostcmds.items():
            for interval, cmds in interval_cmds.items():
                next_worker = self._get_worker(interval, refresh=refresh)
                next_worker.add_host(host, cmds)
                self.working.add(next_worker)
        if refresh:
            # start any new threads since last cycle
            self.start()

    def start(self):
        ''' Start all worker threads and block until done '''
        if len(self.working) == 0:
            self.working.add(self.default_worker)
        started = []
        for worker in self.working:
            if not worker.isAlive():
                worker.start()
                started.append(worker)
        for interval, workers in self.workers.items():
            if isinstance(workers, list):
                self.workers[interval] = utils.Cycle(workers)
        for worker in started:
            worker.join()

    def stop(self):
        ''' Stop all running worker threads '''
        logging.info("Scheduler: Stopping all running workers")
        for w in self.working:
            w.stop()
        self.workers = {}
        self.working = set()


class Worker(threading.Thread):
    ''' Worker is responsible for running a set of commands per host at regular intervals
        and dumping to output
    '''

    def __init__(self, interval, collector, output_type, output_addr, use_threads, num_collector_threads):
        super().__init__()
        self.setDaemon(True)
        self.interval = interval
        self.collector = collector
        self.output_type = output_type
        self.output_addr = output_addr
        self.num_collector_threads = num_collector_threads
        self.use_threads = use_threads
        self.hostcmds = {}
        self._run = True
        self._lock = threading.Lock()

    def set_name(self, name):
        self.name = name

    def stop(self):
        self._run = False

    def add_host(self, host, cmds):
        with self._lock:
            commands = self.hostcmds.setdefault(host, [])
            commands += cmds

    def init(self):
        with self._lock:
            self.hostcmds = {}

    def run(self):
        ''' Main run loop '''
        while True:
            if not self._run:
                return
            self._lock.acquire()
            logger.info('{}: Starting collection for {} hosts'.format(
                self.name, len(self.hostcmds)))
            hosts = list(self.hostcmds.keys())
            time_start = time.time()
            if self.use_threads:
                target_hosts_lists = [
                    hosts[x: x + int(len(hosts) / self.num_collector_threads + 1)]
                        for x in range(
                            0, len(hosts), int(len(hosts) / self.num_collector_threads + 1)
                        )
                ]       
                jobs = []
                for i, target_hosts_list in enumerate(target_hosts_lists, 1):
                    logger.info('{}: Collector Thread-{} scheduled with following hosts: {}'.format(
                        self.name, i, target_hosts_list))
                    hostcmds = {}
                    for host in target_hosts_list:
                        hostcmds[host] = self.hostcmds[host]
                    job = threading.Thread(target=self.collector.collect,
                                           args=(self.name,),
                                           kwargs={"host_cmds": hostcmds})
                    job.start()
                    jobs.append(job)

                # Ensure all of the threads have finished
                for j in jobs:
                    j.join()

            else:
                # Execute everythings in the main thread
                self.collector.collect(self.name, host_cmds=self.hostcmds)

            time_end = time.time()
            time_execution = time_end - time_start
            worker_datapoint = [
                {
                    'measurement': collector.global_measurement_prefix + '_worker_stats',
                    'tags': {'worker_name': self.name},
                    'fields': {
                        'execution_time_sec': "%.4f" % time_execution,
                        'nbr_devices': len(self.hostcmds),
                        'nbr_threads': self.num_collector_threads
                    },
                    'timestamp': time.time_ns(),

                }
            ]
            if os.environ.get('NOMAD_JOB_NAME'):
                worker_datapoint[0]['tags']['nomad_job_name'] = os.environ['NOMAD_JOB_NAME']
            if os.environ.get('NOMAD_ALLOC_INDEX'):
                worker_datapoint[0]['tags']['nomad_alloc_index'] = os.environ['NOMAD_ALLOC_INDEX']
            if os.environ.get('NOMAD_ALLOC_ID'):
                worker_datapoint[0]['tags']['nomad_alloc_id'] = os.environ['NOMAD_ALLOC_ID']


            ### Send results to the right output
            try:
                if self.output_type == 'stdout':
                    utils.print_format_influxdb(worker_datapoint)
                elif self.output_type == 'http':
                    utils.post_format_influxdb(worker_datapoint, self.output_addr)
                else:
                    logger.warn('{}: Output format unknown: {}'.format(self.name, self.output_type))
            except Exception as ex:
                logger.exception("Hit exception trying to post to influx")

            logger.info('Worker {} took {} seconds to run'.format(self.name, time_execution))
            self._lock.release()
            # sleep until next interval
            time.sleep(self.interval)
