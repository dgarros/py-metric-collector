import unittest
import yaml
import sys
import logging
import pprint
from os import path
from lib import parser_manager

here = path.abspath(path.dirname(__file__))
parsers_dir = here + '/../../parsers'
pp = pprint.PrettyPrinter(indent=4)

class Test_Parsers(unittest.TestCase):
  logger = logging.getLogger()
  logger.setLevel(logging.DEBUG)

  def test_parser_show_bgp_neighbor(self):
    test_dir = here+'/input/41_validate_parsers'

    pm = parser_manager.ParserManager( parser_dir=parsers_dir )

    ## Read XML content
    xml_data = open( test_dir + "/rpc-reply/show_bgp_neighbor/command.xml").read()

    ## Return a list dict
    data = pm.parse( input="show-bgp-neighbor.yaml", data=xml_data )

    import pprint

    pprint.pprint(data)

    self.assertTrue( False )