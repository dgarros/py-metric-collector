import os
import unittest
import sys
import logging
import pprint
import requests_mock
import yaml 
import copy
from os import path

sys.path.append("inventory")
from netbox import NetboxAsInventory

here = path.abspath(path.dirname(__file__))

FIXTURE_DIR = "input/61_netbox_inventory/"

config_01 = {
            'netbox': {
                'main': {
                    'api_url': 'http://mock/api/dcim/devices/'
                },
                'filters': {
                    'juniper': [
                            { 'site': ['aa', 'bb', 'cc'] },
                            { 'manufacturer': 'juniper' } 
                        ]
                },
                'tags': {
                    'default': ['device_role', 'site'],
                },
                'context': {
                    'general': {
                        'platform': 'platform',
                        'site': 'site'
                    }
                }
            }
        }

class Test_Inventory_Netbox(unittest.TestCase):
    
    @requests_mock.mock()
    def test_init(self, m):

        config = copy.deepcopy(config_01)

        test01_1 = load_fixture("inv_01")
        m.get(
            "http://mock/api/dcim/devices/?%s" % test01_1["params"],
            json=test01_1["response"],
        )

        expected_response = {
            'device1': {'address': '1.2.3.4',
              'context': [{'platform': 'Junos'}, {'site': 'aa'}],
              'device_type': 'juniper',
              'tags': ['top-of-rack', 'aa']},
            'device2': {'address': '4.3.2.1',
              'context': [{'platform': 'Junos'}, {'site': 'bb'}],
              'device_type': 'juniper',
              'tags': ['top-of-rack', 'bb']}
        }

        netbox = NetboxAsInventory(config)
        ansible_inventory = netbox.generate_inventory()

        self.assertDictEqual(ansible_inventory, expected_response)

    @requests_mock.mock()
    def test_custom_field_tag(self, m):
        config = copy.deepcopy(config_01)
        config['netbox']['tags']['custom'] = ['custom_a']

        test01_1 = load_fixture("inv_01")
        m.get(
            "http://mock/api/dcim/devices/?%s" % test01_1["params"],
            json=test01_1["response"],
        )

        expected_response = {
            'device1': {'address': '1.2.3.4',
              'context': [{'platform': 'Junos'}, {'site': 'aa'}],
              'device_type': 'juniper',
              'tags': ['top-of-rack', 'aa', 'mycustom-field-a1']},
            'device2': {'address': '4.3.2.1',
              'context': [{'platform': 'Junos'}, {'site': 'bb'}],
              'device_type': 'juniper',
              'tags': ['top-of-rack', 'bb', 'mycustom-field-a2']}
        }

        netbox = NetboxAsInventory(config)
        ansible_inventory = netbox.generate_inventory()

        self.assertDictEqual(ansible_inventory, expected_response)


    @requests_mock.mock()
    def test_custom_field_tag_null_value(self, m):
        config = copy.deepcopy(config_01)
        config['netbox']['tags']['custom'] = ['custom_b']

        test01_1 = load_fixture("inv_01")
        m.get(
            "http://mock/api/dcim/devices/?%s" % test01_1["params"],
            json=test01_1["response"],
        )

        expected_response = {
            'device1': {'address': '1.2.3.4',
              'context': [{'platform': 'Junos'}, {'site': 'aa'}],
              'device_type': 'juniper',
              'tags': ['top-of-rack', 'aa', 'mycustom-field-b1']},
            'device2': {'address': '4.3.2.1',
              'context': [{'platform': 'Junos'}, {'site': 'bb'}],
              'device_type': 'juniper',
              'tags': ['top-of-rack', 'bb']}
        }

        netbox = NetboxAsInventory(config)
        ansible_inventory = netbox.generate_inventory()

        self.assertDictEqual(ansible_inventory, expected_response)


def load_fixture(name):

    return yaml.load(open(here + "/" + FIXTURE_DIR + name + ".json"))
