#!/usr/bin/env python

# Copyright: (c) 2017, Damien Garros
# Inspired from Ahmed AbouZaid work <http://aabouzaid.com/>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

import os
import sys
import yaml
import argparse

try:
    import requests
    from requests.packages.urllib3.exceptions import InsecureRequestWarning
    requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
    
except ImportError:
    sys.exit('requests package is required for this inventory script.')

try:
    import json
except ImportError:
    import simplejson as json


# Script.
def cli_arguments():
    """
    Script cli arguments.
    """

    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("-c", "--config-file",
                        default=os.getenv("NETBOX_CONFIG_FILE", "netbox.yml"),
                        help="""Path for script's configuration. Also "NETBOX_CONFIG_FILE"
                                could be used as env var to set conf file path.""")
    arguments = parser.parse_args()
    return arguments


# Utils.
def open_yaml_file(yaml_file):
    """Open YAML file.

    Args:
        yaml_file: Relative or absolute path to YAML file.

    Returns:
        Content of YAML the file.
    """

    # Load content of YAML file.
    try:
        with open(yaml_file, 'r') as config_yaml_file:
            try:
                yaml_file_content = yaml.safe_load(config_yaml_file)
            except yaml.YAMLError as yaml_error:
                sys.exit(yaml_error)
    except IOError as io_error:
        sys.exit("Cannot open YAML file.\n%s" % io_error)
    return yaml_file_content


class NetboxAsInventory(object):
    """Netbox as a dynamic inventory for py-metric-collector.

    Retrieves hosts list from netbox API and returns host list as JSON

    Attributes:
        script_config_data: Content of its config which comes from YAML file.
    """

    def __init__(self, script_args, script_config_data):
        # Script arguments.
        self.config_file = script_args.config_file

        self.inventory_dict = dict()

        self.req = requests.session()
        self.verify_certs = False

        # Script configuration.
        self.script_config = script_config_data
        self.api_url = self._config(["main", "api_url"])
        self.tags = self._config(["tags"], default={})
        self.filters = self._config(["filters"], default={})
        self.context = self._config(["context"], default={})

        self.device_type = self._config(["device_type"], default='device_type/manufacturer/slug')

        # Get value based on key.
        self.key_map = {
            "default": "name",
            "general": "name",
            "custom": "value",
            "status": "label",
            "device_type": "model",
            "ip": "address"
        }

    def _get_value_by_path(self, source_dict, key_path,
                           ignore_key_error=False, default=""):
        """Get key value from nested dict by path.

        Args:
            source_dict: The dict that we look into.
            key_path: A list has the path of key. e.g. [parent_dict, child_dict, key_name].
            ignore_key_error: Ignore KeyError if the key is not found in provided path.
            default: Set default value if the key is not found in provided path.

        Returns:
            If key is found in provided path, it will be returned.
            If ignore_key_error is True, None will be returned.
            If default is defined and key is not found, default will be returned.
        """

        key_value = ""
        try:
            # Reduce key path, where it get value from nested dict.
            # a replacement for buildin reduce function.
            for key in key_path:
                if isinstance(source_dict.get(key), dict) and len(key_path) > 1:
                    source_dict = source_dict.get(key)
                    key_path = key_path[1:]
                    self._get_value_by_path(source_dict, key_path,
                                            ignore_key_error=ignore_key_error, default=default)
                else:
                    key_value = source_dict[key]

        # How to set the key value, if the key was not found.
        except KeyError as key_name:
            if default:
                key_value = default
            elif not default and ignore_key_error:
                key_value = None
            elif not key_value and not ignore_key_error:
                sys.exit("The key %s is not found. Please remember, Python is case sensitive." % key_name)
        return key_value

    def _config(self, key_path, default=""):
        """Get value from config var.

        Args:
            key_path: A list has the path of the key.
            default: Default value if the key is not found.

        Returns:
            The value of the key from config file or the default value.
        """
        config = self.script_config.setdefault("netbox", {})
        value = self._get_value_by_path(config, key_path, ignore_key_error=True, default=default)

        if value:
            key_value = value
        else:
            sys.exit("The key '%s' is not found in config file." % ".".join(key_path))

        return key_value

    def get_hosts_list(self, filters=None):
        """Retrieves hosts list from netbox API.

        Returns:
            A list of all hosts from netbox API.
        """

        if not self.api_url:
            sys.exit("Please check API URL in script configuration file.")

        api_url_params = ""

        # Add filters provided into the URL
        # Filter can be a list or a dict, if it's a dict we need to query Net box multiple times
        filter_groups = None
        if filters:
            if isinstance(filters, list):
                filter_groups = { 'default': filters}
            elif isinstance(filters, dict):
                filter_groups = filters 

        if not filter_groups:
            return self.netbox_get_devices_list()

        else:
            global_hosts_list_json = {
                'results': [],
                'count': 0
            }
            
            for grp_name, grp_filters in filter_groups.items():
                grp_api_url_params = ""

                for grp_filter in grp_filters:
                    for key,value in grp_filter.items():

                        if key == "limit" or key == "offset":
                            continue

                        if isinstance(value, list):
                            for v in value:
                                grp_api_url_params += "%s=%s&" % (key, v)
                        else:
                            grp_api_url_params += "%s=%s&" % (key, value)

                grp_hosts_list_json = self.netbox_get_devices_list(grp_api_url_params)

                global_hosts_list_json['results'] += grp_hosts_list_json['results']
                global_hosts_list_json['count'] += grp_hosts_list_json['count']

            return global_hosts_list_json


    def add_host_to_inventory(self, host_data):
        """Add a host to the inventory.

        If tags is defined in the configuration, it will try to find these tags and add them to the host
        """

        device_name = host_data.get("name")
        categories_source = {
            "default": host_data,
            "custom": host_data.get("custom_fields")
        }

        ### Check if the primary IP address is defined
        ### Skip device if not defined
        if not isinstance(host_data['primary_ip'], dict):
            return False

        ip_address = host_data['primary_ip']['address'].split('/')[0]

        self.inventory_dict[device_name] = {
            'tags': [],
            'address': ip_address,
            'context': []
        }

        if self.device_type:
            device_type = self._get_value_by_path(host_data, self.device_type.split('/'))
            self.inventory_dict[device_name]['device_type'] = device_type

        if self.tags:
            # There are 2 categories that will be used to group hosts.
            # One for default section in netbox, and another for "custom_fields" which are being defined by netbox user.
            for category in self.tags:

                # if the categfory is static, just add these tags without resolution
                if category == 'static':
                    for tag in self.tags[category]:
                        self.inventory_dict[device_name]['tags'].append(tag)
                    continue

                key_name = self.key_map[category]
                data_dict = categories_source[category]

                # The groups that will be used to group hosts in the inventory.
                for tag in self.tags[category]:
                    # Try to get group value. If the section not found in netbox, this also will print error message.
                    tag_value = self._get_value_by_path(data_dict, [tag, key_name])

                    ## Add value
                    self.inventory_dict[device_name]['tags'].append(tag_value)
        
        return True

    def get_context(self, host_data):
        """Find context data

        These vars will be used for host in the inventory.
        We can select whatever from netbox to be used as Ansible inventory vars.
        The vars are defined in script config file.

        Args:
            host_data: Dict, it has a host data which will be added to inventory.
            host_vars: Dict, it has selected fields to be used as host vars.

        Returns:
            A list
        """

        host_context_list = []

        if not self.context: 
            return False

        categories_source = {
            "ip": host_data,
            "general": host_data,
            "status": host_data.get("status"),
            "device_type": host_data.get("device_type"),
            "custom": host_data.get("custom_fields")
        }

        # Get context based on selected vars. (that should come from
        # script's config file)
        for category in self.context:
            key_name = self.key_map[category]
            data_dict = categories_source[category]

            for var_name, var_data in self.context[category].items():
                # This is because "custom_fields" has more than 1 type.
                # Values inside "custom_fields" could be a key:value or a dict.
                if isinstance(data_dict.get(var_data), dict):
                    var_value = self._get_value_by_path(data_dict, [var_data, key_name], ignore_key_error=True)
                else:
                    var_value = data_dict.get(var_data)

                if var_value:
                    host_context_list.append({var_name: var_value})

        return host_context_list

    def generate_inventory(self):
        """Generate py-metric-collector dynamic inventory

        Returns:
            A dict has inventory with hosts and their tags and context
        """

        netbox_hosts_list = self.get_hosts_list(self.filters)

        if isinstance(netbox_hosts_list, dict) and "results" in netbox_hosts_list:
            netbox_hosts_list = netbox_hosts_list["results"]

        
        if not netbox_hosts_list:
            return dict()

        for current_host in netbox_hosts_list:

            device_name = current_host.get("name")
            if not device_name: continue

            if self.add_host_to_inventory(current_host):
                dev_context = self.get_context(current_host)
                self.inventory_dict[device_name]['context'] = dev_context

        return self.inventory_dict

    def print_inventory_json(self, inventory_dict):
        """Print inventory.

        Args:
            inventory_dict: Inventory dict hosts.

        Returns:
            It prints the inventory in JSON format
        """

        print(json.dumps(inventory_dict, sort_keys=True,indent=4,))

    def netbox_get_devices_list(self, params=''):
        
        results = {
            'count': 0,
            'results': []
        }

        offset = 0
        netbox_batch_size = 1000
        keep_querying = True

        while keep_querying:
    
            paging_params = "offset=%s&limit=%s" % (offset, netbox_batch_size)

            if params == "":
                api_url_params = paging_params
            else:
                api_url_params = params + "&" + paging_params
              
            hosts_list = self.req.get(self.api_url, 
                                    params=api_url_params, 
                                    verify=self.verify_certs )

            hosts_list.raise_for_status()

            hosts_list_dict = hosts_list.json()

            results['count'] = hosts_list_dict['count']
            results['results'].extend(hosts_list_dict['results'])

            offset += netbox_batch_size
            if int(hosts_list_dict['count']) < offset:
                keep_querying = False

        return results


# Main.
def main():
    # Script vars.
    args = cli_arguments()
    config_data = open_yaml_file(args.config_file)

    # Netbox vars.
    netbox = NetboxAsInventory(args, config_data)
    ansible_inventory = netbox.generate_inventory()
    netbox.print_inventory_json(ansible_inventory)


# Run main.
if __name__ == "__main__":
    main()
