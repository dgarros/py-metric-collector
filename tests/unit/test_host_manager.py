import unittest
import yaml
import sys
import logging
import pprint
from os import path
from metric_collector.host_manager import HostManager

here = path.abspath(path.dirname(__file__))

pp = pprint.PrettyPrinter(indent=4)

cred_pwd_01 = { 'lab_credentials': {
                      'username': 'user1',
                      'password': 'pwd1',
                      'method': 'password',
                      'tags': 'site1'
                    }
              }
    
cred_pwd_02 = { 'lab_credentials': {
                      'username': 'user1',
                      'password': 'pwd1',
                      'port': 843,
                      'method': 'password',
                      'tags': 'router1'
                    }
              }

inventory_1 = {
  '10.10.0.1': 'switch site1 lab',
  '20.20.0.20': 'router site1 lab'
}

inventory_2 = {
  'switch1': {
    'tags': [ 'switch', 'site1', 'lab'],
    'address': '30.30.0.3',
    'context': [
      { 'site': 'site1' },
      { 'role': 'switch' }
    ]
  },
  'router1': {
    'tags': [ 'router', 'site1', 'lab'],
    'address': '40.40.0.4',
    'context': [
      { 'site': 'site1' },
      { 'role': 'router' }
    ]
  }
}

commands_1 = {
  'test1_commands': {
    'netconf':[ 'show version', 'show cpu' ],
    'tags': ['router', 'test1']
  },
  'test2_commands': {
    'netconf':[ 'show test2' ],
    'tags': ['site1', 'test2', '1m']
  },
  'test3_commands': {
    'netconf':[ 'show test3' ],
    'tags': ['switch', 'test3', '5m']
  },
}

class Test_Validate_Main_Block(unittest.TestCase):
 
  def test_import_host_manager(self):

    hm = HostManager( inventory=inventory_2,
                      credentials=cred_pwd_01,
                      commands=commands_1 )

    self.assertTrue(1)


  def test_get_target_hosts_new_format(self):

    hm = HostManager( inventory=inventory_2,
                      credentials=cred_pwd_01,
                      commands=commands_1 )

    self.assertEqual(hm.get_target_hosts(), [])
    self.assertEqual(hm.get_target_hosts([".*"]), ['router1', 'switch1' ])
    self.assertEqual(hm.get_target_hosts(['router']), [ 'router1'])
  
  def test_get_target_hosts_old_format(self):

    hm = HostManager( inventory=inventory_1,
                      credentials=cred_pwd_01,
                      commands=commands_1 )

    self.assertEqual(hm.get_target_hosts(), [])
    self.assertEqual(hm.get_target_hosts([".*"]), ['10.10.0.1', '20.20.0.20' ])
    self.assertEqual(hm.get_target_hosts(['router']), ['20.20.0.20'])
  

  def test_get_target_commands_new_format(self):

    hm = HostManager( inventory=inventory_2,
                      credentials=cred_pwd_01,
                      commands=commands_1 )

    self.assertEqual(hm.get_target_commands('router1'), 
                    ['show cpu', 'show test2', 'show version'])

    self.assertEqual(hm.get_target_commands('switch1'), 
                    ['show test2', 'show test3'])
  
  def test_get_target_commands_command_tag(self):

      hm = HostManager( inventory=inventory_2,
                        credentials=cred_pwd_01,
                        commands=commands_1 )

      self.assertEqual(hm.get_target_commands('switch1',tags=['1m']), 
                      ['show test2'])

      self.assertEqual(hm.get_target_commands('switch1',tags=['5m']), 
                      ['show test3'])

  def test_get_credentials_default_port(self):

      hm = HostManager( inventory=inventory_2,
                        credentials=cred_pwd_01,
                        commands=commands_1 )

      self.assertEqual(hm.get_credentials('router1'), { 'key_file': None, 
                                                        'method': 'password', 
                                                        'password': 'pwd1',
                                                        'port': 22,
                                                        'tags': ['site1'],
                                                        'username': 'user1'})

  def test_get_credentials_not_default_port(self):

      hm = HostManager( inventory=inventory_2,
                        credentials=cred_pwd_02,
                        commands=commands_1 )

      self.assertEqual(hm.get_credentials('router1'), { 'key_file': None, 
                                                        'method': 'password', 
                                                        'password': 'pwd1',
                                                        'port': 843,
                                                        'tags': ['router1'],
                                                        'username': 'user1'})
        
  def test_get_context(self):

      hm = HostManager( inventory=inventory_2,
                        credentials=cred_pwd_02,
                        commands=commands_1 )

      expected_list = [
        { 'site': 'site1' },
        { 'role': 'router' }
      ]

      self.assertEqual(hm.get_context('router1'), expected_list)
        