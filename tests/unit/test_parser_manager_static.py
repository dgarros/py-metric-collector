import unittest
import yaml
import sys
import logging
import pprint
from os import path
from metric_collector import parser_manager

here = path.abspath(path.dirname(__file__))

pp = pprint.PrettyPrinter(indent=4)

class Test_Validate_Main_Block(unittest.TestCase):
  logger = logging.getLogger()
  logger.setLevel(logging.CRITICAL)

  def test_import_parser_namager(self):
    self.assertTrue(1)

  def test_str_2_int_wrong_input(self):

    pm = parser_manager.ParserManager()
    self.assertEqual( pm.str_2_int('notanint'), None )
    self.assertEqual( pm.str_2_int('Undefined'), None )

  def test_str_2_int(self):

    pm = parser_manager.ParserManager()
    self.assertEqual( pm.str_2_int('100Gbps'), 100000000000 )
    self.assertEqual( pm.str_2_int('100gbps'), 100000000000 )
    self.assertEqual( pm.str_2_int('100G'), 100000000000 )

  def test_cleanup_tag(self):

    pm = parser_manager.ParserManager()
    self.assertEqual( pm.cleanup_tag('my tag'), 'my_tag' )
    self.assertEqual( pm.cleanup_tag('my tag=true'), 'my_tag_true' )
