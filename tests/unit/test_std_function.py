import unittest
import yaml
import sys
import logging
import pprint
from os import path
from metric_collector.cli import shard_host_list

here = path.abspath(path.dirname(__file__))

pp = pprint.PrettyPrinter(indent=4)

def gen_fake_host_list(size):

  hosts = {}

  for i in range(0, size):
    hosts['host-{:03}'.format(i)] = i

  return hosts

class Test_Validate_Main_Block(unittest.TestCase):
 
  def test_shard_host_list_equal(self):

    hosts = shard_host_list(1,3,gen_fake_host_list(9))
    self.assertEqual(sorted(hosts.keys()), ['host-000', 'host-003', 'host-006'])
    self.assertEqual(len(hosts), 3)

  def test_shard_host_list_unequal(self):

    hosts = shard_host_list(3,3,gen_fake_host_list(10))
    self.assertEqual(sorted(hosts.keys()), ['host-002', 'host-005', 'host-008'])
    self.assertEqual(len(hosts), 3)

    hosts = shard_host_list(1,3,gen_fake_host_list(10))
    self.assertEqual(sorted(hosts.keys()), ['host-000', 'host-003', 'host-006', 'host-009'])
    self.assertEqual(len(hosts), 4)