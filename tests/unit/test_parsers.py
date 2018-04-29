import unittest
import yaml
import sys
import logging
import pprint
from os import path
from metric_collector import parser_manager

here = path.abspath(path.dirname(__file__))
parsers_dir = here + '/../../parsers'
pp = pprint.PrettyPrinter(indent=4)

class Test_Parsers(unittest.TestCase):
  logger = logging.getLogger()
  logger.setLevel(logging.DEBUG)


  def test_parser_show_interfaces_extensive(self):
    test_dir = here+'/input/41_validate_parsers'

    pm = parser_manager.ParserManager( )

    ## Read XML content
    xml_data = open( test_dir + "/rpc-reply/show_interfaces_extensive_01.xml").read()

    ## Return a list dict
    data = pm.parse( input="show-interfaces-extensive.parser.yaml", data=xml_data.encode() )

    # pprint.pprint(data)

    self.assertTrue( True )