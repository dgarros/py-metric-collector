import unittest
import yaml
import sys
import logging
import pprint
import json
from os import path
from metric_collector import parser_manager

here = path.abspath(path.dirname(__file__))

pp = pprint.PrettyPrinter(indent=4)

class Test_Validate_Main_Block(unittest.TestCase):
  logger = logging.getLogger()
  logger.setLevel(logging.CRITICAL)

  def test_import_parser_namager(self):
    self.assertTrue(1)

  def test_invalid_yaml(self):
    test_dir = here+'/input/01_wrong_yaml/parsers'
    pm = parser_manager.ParserManager( parser_dirs=[test_dir], default_parser_dir=False  )

    self.assertTrue( pm.get_nbr_parsers() == 0 )

  def test_no_parser_key(self):
    test_dir = here+'/input/02_no_parser_key/parsers'
    pm = parser_manager.ParserManager( parser_dirs=[test_dir], default_parser_dir=False  )

    self.assertTrue( pm.get_nbr_parsers() == 0 )

  def test_load_valid_xml_parser(self):
    test_dir = here+'/input/03_valid_xml_parser/parsers'

    pm = parser_manager.ParserManager( parser_dirs=[test_dir], default_parser_dir=False )
    name = pm.get_parser_name_for(input='show-bgp-summary.parser.yaml')

    self.assertTrue( pm.get_nbr_parsers() == 1 )
    self.assertTrue( pm.nbr_xml_parsers == 1 )
    self.assertTrue( name == "show-bgp-summary.parser.yaml" )

  def test_load_valid_regex_parser(self):
    test_dir = here+'/input/04_valid_regex_parser/parsers'

    pm = parser_manager.ParserManager( parser_dirs=[test_dir], default_parser_dir=False )
    name = pm.get_parser_name_for(input='show-system-processes-extensive.parser.yaml')

    self.assertTrue( pm.get_nbr_parsers() == 1 )
    self.assertTrue( pm.nbr_regex_parsers == 1 )
    self.assertTrue( name == "show-system-processes-extensive.parser.yaml" )

  def test_find_parser(self):
    test_dir = here+'/input/05_find_parsers/parsers'

    pm = parser_manager.ParserManager( parser_dirs=[test_dir], default_parser_dir=False )

    by_name = pm.get_parser_name_for(input='type-regex-regex-command.parser.yaml')
    # by_name_2 = pm.get_parser_name_for(input='type-regex-regex-command.parser')

    regex_by_command = pm.get_parser_name_for(input='show system processes extensive')

    xml_by_regex = pm.get_parser_name_for(input='show ospf summary')
    xml_by_regex_2 = pm.get_parser_name_for(input='show ospf summary | display xml')

    xml_by_command = pm.get_parser_name_for(input='show bgp summary')
    xml_by_command_2 = pm.get_parser_name_for(input='show bgp summary | display xml')

    assert( pm.get_nbr_parsers() == 3 )

    assert( by_name == 'type-regex-regex-command.parser.yaml' )

    # assert( by_name_2 == 'type-regex-regex-command.parser.yaml' )
    assert( regex_by_command == 'type-regex-regex-command.parser.yaml' )

    assert( xml_by_regex == 'type-xml-regex-command.parser.yaml' )
    assert( xml_by_regex_2 == 'type-xml-regex-command.parser.yaml' )

    assert( xml_by_command == 'type-xml-command.parser.yaml' )
    assert( xml_by_command_2 == 'type-xml-command.parser.yaml' )

  def test_parse_valid_xml(self):
    test_dir = here+'/input/20_xml_parser'

    pm = parser_manager.ParserManager( parser_dirs=[test_dir + "/parsers"], default_parser_dir=False )

    ## Read XML content
    xml_data = open( test_dir + "/rpc-reply/show_route_summary/command.xml").read()

    expected_dict_0 = {
        'fields': {   'active-route-count': '16',
                      'destination-count': '16',
                      'hidden-route-count': '0',
                      'holddown-route-count': '0',
                      'total-route-count': '21'},
        'measurement': None,
        'tags': {   'key': 'inet.0'}
    }
    expected_dict_1 = {
        'fields': {   'active-route-count': '2',
                      'destination-count': '2',
                      'hidden-route-count': '0',
                      'holddown-route-count': '0',
                      'total-route-count': '2'},
        'measurement': None,
        'tags': {   'key': 'inet6.0'}
    }

    data = list(pm.parse( input="show-route-summary.parser.yaml", data=xml_data.encode()))

    self.assertDictEqual( expected_dict_0, data[0] )
    self.assertDictEqual( expected_dict_1, data[1] )

    self.assertTrue( len(data) == 2 )

  # def test_parse_valid_regex(self):
  #   test_dir = here+'/input/21_regex_parser'

  #   pm = parser_manager.ParserManager( parser_dir= test_dir + "/parsers" )

  #   ## Read XML content
  #   xml_data = open( test_dir + "/rpc-reply/show_system_processes_extensive/command.xml").read()

  #   ## Return a list dict
  #   data = pm.parse( input="show-system-processes-extensive.parser.yaml", data=xml_data )

  #   # pp.pprint(data)
  #   expected_dict = {
  #       'fields': {   're.memory.rpd-CPU': 0,
  #                     're.memory.rpd-RES': 16648000,
  #                     're.memory.rpd-SIZE': 70372000,
  #                     're.memory.snmpd-CPU': 0,
  #                     're.memory.snmpd-RES': 10144000,
  #                     're.memory.snmpd-SIZE': 20804000},
  #       'measurement': None,
  #       'tags': {   }
  #   }

  #   self.assertDictEqual( expected_dict, data[0] )
  #   self.assertTrue( len(data) == 1 )

  def test_parse_valid_textfsm(self):
    test_dir = here+'/input/31_textfsm_parser'

    pm = parser_manager.ParserManager( parser_dirs=[test_dir + "/parsers"], default_parser_dir=False )

    ## Read XML content
    xml_data = open( test_dir + "/rpc-reply/show_system_processes_extensive/command_short.xml").read()

    ## Return a list dict
    data = list(pm.parse( input="show-system-processes-extensive.parser.yaml", data=xml_data.encode()))

    # pp.pprint(data)
    expected_dict_1 = {
        'fields': {'cpu': '0.59', 'memory': '112000000'},
        'measurement': 'jnpr_system_process',
        'tags': {'process': 'authd'}
      }

    expected_dict_2 = {
        'fields': {'cpu': '0.00', 'memory': '55532000'},
        'measurement': 'jnpr_system_process',
        'tags': {'process': 'pfed'}
      }

    expected_dict_3 = {
        'fields': {'cpu': '0.00', 'memory': '98872000'},
        'measurement': 'jnpr_system_process',
        'tags': {'process': 'jdhcpd'}
      }

    self.assertDictEqual( expected_dict_1, data[0] )
    self.assertDictEqual( expected_dict_2, data[1] )
    self.assertDictEqual( expected_dict_3, data[2] )
    self.assertTrue( len(data) == 4 )

  def test_parse_valid_json(self):
    test_dir = here+'/input/51_json_parser'

    pm = parser_manager.ParserManager(parser_dirs=[test_dir + "/parsers"], default_parser_dir=False)

    # Read JSON Content
    with open(test_dir + "/json-reply/f5-pools.json") as f:
        data = f.read()

    json_data = json.loads(data)

    data = pm.parse(input="f5-pools.yaml", data=json_data)

    expected_dict_1 = {'fields': {'active_member_count': 1,
             'bits_in': 0,
             'bits_out': 0,
             'current_conns': 0,
             'current_sessions': 0,
             'max_conns': 0,
             'min_active_members': 0,
             'packets_in': 0,
             'packets_out': 0,
             'total_conns': 0,
             'total_requests': 0},
  'measurement': None,
  'tags': {'partition_poolname': '/Common/RA-WEB241-443'}}

    expected_dict_2 = {'fields': {'active_member_count': 1,
             'bits_in': 0,
             'bits_out': 0,
             'current_conns': 0,
             'current_sessions': 0,
             'max_conns': 0,
             'min_active_members': 0,
             'packets_in': 0,
             'packets_out': 0,
             'total_conns': 0,
             'total_requests': 0},
  'measurement': None,
  'tags': {'partition_poolname': '/Common/matte_xff_test_pool'}} 

    expected_dict_3 = {'fields': {'active_member_count': 1,
             'bits_in': 1085496,
             'bits_out': 172672,
             'current_conns': 0,
             'current_sessions': 0,
             'max_conns': 2,
             'min_active_members': 0,
             'packets_in': 582,
             'packets_out': 527,
             'total_conns': 47,
             'total_requests': 442},
  'measurement': None,
  'tags': {'partition_poolname': '/Common/rkeller_syslog_pool'}}

    self.assertDictEqual( expected_dict_1, data[0] )
    self.assertDictEqual( expected_dict_2, data[1] )
    self.assertDictEqual( expected_dict_3, data[2] )
    self.assertTrue( len(data) == 6 )
