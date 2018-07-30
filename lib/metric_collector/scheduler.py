import logging
import queue
import threading
import time
from itertools import cycle
from metric_collector import collector, utils

logger = logging.getLogger('scheduler')

class Scheduler:

    def __init__(self, shard_id, host_mgr, parser_mgr, output_type, output_addr,
                 max_worker_threads=1, use_threads=True, num_threads_per_worker=10):
        self.shard_id = shard_id
        self.workers = {}
        self.working = set()
        self.collector = collector.Collector(host_mgr, parser_mgr)
        self.host_mgr = host_mgr
        self.max_worker_threads = max_worker_threads
        self.output_type = output_type
        self.output_addr = output_addr
        self.use_threads = use_threads
        self.num_threads_per_worker = num_threads_per_worker
        # default worker that is started if there are no hosts to schedule
        self.default_worker = Worker(
            120, self.collector, self.output_type, self.output_addr,
            self.use_threads, self.num_threads_per_worker)
        self.default_worker.set_name('Default-120sec', shard_id)

    def _get_workers(self, interval):
        ''' Spin off worker threads for each type of command based on interval '''
        interval_workers = self.workers.get(interval)
        if not interval_workers:
            workers = [
                Worker(interval, self.collector, self.output_type, self.output_addr, 
                       self.use_threads, self.num_threads_per_worker)
                for _ in range(self.max_worker_threads)
            ]
            for i, w in enumerate(workers, 1):
                w.set_name('Worker-{}sec-{}'.format(interval, i), self.shard_id)
            interval_workers = cycle(workers)
            self.workers[interval] = interval_workers
        return interval_workers

    def add_hosts(self, hosts, cmd_tags=None):
        '''  Create worker threads per interval and round-robin the hosts amongst them '''
        if not hosts:
            logger.error('Scheduler: No hosts')
            return
        tags = cmd_tags or ['.*']
        for host in hosts:
            target_commands = self.host_mgr.get_target_commands(host, tags=tags) 
            if not target_commands:
                logger.error('Scheduler: No commands found for host: {}'.format(host))
            for cmd in target_commands:
                workers = self._get_workers(cmd['interval_secs'])
                next_worker = next(workers)
                next_worker.add_host(host, cmd['commands'])
                self.working.add(next_worker)

    def start(self):
        ''' Start all worker threads and block until stopped '''
        if len(self.working) == 0:
            self.working.add(self.default_worker)
        for worker in self.working:
            worker.start()
        for worker in self.working:
            worker.join()

    def stop(self):
        ''' Stop all running worker threads '''
        for worker in self.working:
            worker.stop()


class Worker(threading.Thread):
    ''' Worker is responsible for running a set of commands per host at regular intervals
        and dumping to output
    '''

    def __init__(self, interval, collector, output_type, output_addr, use_threads, num_collector_threads):
        super().__init__()
        self.interval = interval
        self.collector = collector
        self.num_collector_threads = num_collector_threads
        self.use_threads = use_threads
        self.output_type = output_type
        self.output_addr = output_addr
        self.hostcmds = {}
        self._queue = queue.Queue()
        self._run = True

    def set_name(self, name, shard_id):
        self.name = name
        self.shard_id = shard_id

    def stop(self):
        self._run = False

    def add_host(self, host, cmds):
        commands = self.hostcmds.setdefault(host, [])
        commands += cmds

    def run(self):
        ''' Main run loop '''
        while True:
            if not self._run:
                return
            logger.info('{}: Starting collection for {} hosts'.format(
                self.name, len(self.hostcmds)))
            hosts = list(self.hostcmds.keys())
            time_start = time.time()
            if self.use_threads:
                values = []
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
                                           kwargs={"host_cmds": hostcmds,
                                                   "dump_queue": self._queue})
                    job.start()
                    jobs.append(job)

                # Ensure all of the threads have finished
                for j in jobs:
                    j.join()
                    values += self._queue.get()

            else:
                # Execute everythings in the main thread
                values = self.collector.collect(self.name, host_cmds=self.hostcmds)

            time_end = time.time()
            time_execution = time_end - time_start
            global_datapoint = [
                {
                    'measurement': collector.global_measurement_prefix + '_worker_stats',
                    'tags': {'worker_name': self.name},
                    'fields': {
                        'execution_time_sec': "%.4f" % time_execution,
                        'nbr_devices': len(self.hostcmds),
                        'nbr_threads': self.num_collector_threads
                    }
                }
            ]
            if self.shard_id is not None:
                global_datapoint[0]['tags']['shard_id'] = self.shard_id
            if self.use_threads:
                global_datapoint[0]['fields']['nbr_threads'] = self.num_collector_threads

            values += global_datapoint

            ### Send results to the right output
            if self.output_type == 'stdout':
                utils.print_format_influxdb(values)
            elif self.output_type == 'http':
                utils.post_format_influxdb(values, self.output_addr)
            else:
                logger.warn('{}: Output format unknown: {}'.format(self.name, self.output_type))

            # sleep until next interval
            time.sleep(self.interval)
