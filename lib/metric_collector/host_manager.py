
import re
import logging

class HostManager(object):
    """
    Manage the list of hosts
    Help identify what credential & commands needs to be used for each device
    """
    def __init__(self, credentials, commands, log='info'):

        self.commands = {}
        self.credentials = {}

        ### -------------------------------------------------------------
        ### Check data format
        ### -------------------------------------------------------------
        if not isinstance(credentials, dict):
            raise Exception("credential must be a dictionnary")
        elif not isinstance(commands, dict):
            raise Exception("commands must be a dictionnary")
            
        ### -------------------------------------------------------------
        ### Define Logging
        ### -------------------------------------------------------------
        self.log = logging.getLogger( 'host-manager')

        if log.lower() == 'debug':
            self.log.setLevel(logging.DEBUG)
        elif log.lower() == 'warn':
            self.log.setLevel(logging.WARN)
        elif log.lower() == 'error':
            self.log.setLevel(logging.ERROR)
        else:
            self.log.setLevel(logging.INFO)

        ### -------------------------------------------------------------    
        ### Check commands provided
        ### -------------------------------------------------------------
        for command_grp, command_set in commands.items():

            if not isinstance(command_set, dict):
                self.log.warn('command: format for %s not supported, skipping' % command_grp)
                continue
            
            tags = []
            command_list = []

            if 'tags' not in command_set:
                self.log.warn('command: unable to find tags for %s, skipping' % command_grp)
                continue
            elif 'netconf' not in command_set and 'commands' not in command_set:
                self.log.warn('command: unable to find the list of commands for %s, skipping' % command_grp)
                continue

            ### Extract the tag information
            if isinstance(command_set['tags'], str):
                tags = command_set['tags'].split()
            elif isinstance(command_set['tags'], list):
                tags = command_set['tags']
            else:
                self.log.warn('command: format for %s tags is not supported, skipping' % command_grp)
                continue

            ### Extract the command information
            if 'netconf' in command_set:
                if isinstance(command_set['netconf'], list):
                    command_list = command_list + command_set['netconf']
                elif isinstance(command_set['netconf'], str):
                   command_list = command_list + command_set["netconf"].strip().split("\n")
            
            if 'commands' in command_set:
                if isinstance(command_set['commands'], list):
                    command_list = command_list + command_set['commands']
                elif isinstance(command_set['commands'], str):
                    command_list = command_list + command_set["commands"].strip().split("\n")

            if 'interval' in command_set:
                interval = int(command_set['interval'])
            else:
                # default = 2 min
                interval = 120

            self.commands[command_grp] = {
                'tags': tags,
                'commands': command_list,
                'interval_secs': interval
            }

        ### -------------------------------------------------------------    
        ### Check credential provided
        ### -------------------------------------------------------------
        for credential_grp in credentials:
            
            credential = {  'username': None,
                            'password': None,
                            'port': 22,
                            'method': None,
                            'key_file': None,
                            'tags': [] }

            if not isinstance(credentials[credential_grp], dict):
                self.log.warn('credential: format for %s not supported, skipping' % credential_grp)
                continue

            ### Tags
            if 'tags' not in credentials[credential_grp]:
                self.log.warn('credential: tags is missing for %s, not supported, skipping' % credential_grp)
                continue
            elif isinstance(credentials[credential_grp]['tags'], list):
                credential['tags'] = credentials[credential_grp]['tags']
            elif isinstance(credentials[credential_grp]['tags'], str):
                credential['tags'] = credentials[credential_grp]['tags'].split()
            else:
                self.log.warn('credential: unable to parse tags for %s, not supported, skipping' % credential_grp)
                continue

            ### Username
            if 'username' not in credentials[credential_grp]:
                self.log.warn('credential: username is missing for %s, not supported, skipping' % credential_grp)
                continue
            else:
                credential['username'] = credentials[credential_grp]['username']

            ### Method
            if 'method' not in credentials[credential_grp]:
                credential['method'] = 'password'
            elif credentials[credential_grp]['method'] not in ['password', 'key', 'vault']:
                self.log.warn('credential: method %s for %s not supported, skipping' % (credentials[credential_grp]['method'], credential_grp))
                continue
            else:
                credential['method'] = credentials[credential_grp]['method']

            if credential['method'] == 'password' and 'password' not in credentials[credential_grp]:
                self.log.warn('credential: unable to find the password for %s, skipping' % (credential_grp))
                continue
            elif 'password' in credentials[credential_grp]:
                credential['password'] = credentials[credential_grp]["password"]
            

            if credential['method'] == 'key' and 'key_file' not in credentials[credential_grp]:
                self.log.warn('credential: unable to find the key_file for %s, skipping' % (credential_grp))
                continue
            elif 'key_file' in credentials[credential_grp]:
                credential['key_file'] = credentials[credential_grp]["key_file"]


            ## Port
            if 'port' in credentials[credential_grp]:
                credential['port'] = credentials[credential_grp]['port']

            self.credentials[credential_grp] = credential


    def update_hosts(self, inventory):
        self.hosts = {}
        if not isinstance(inventory, dict):
            raise Exception("inventory must be a dictionnary of host")
        ### -------------------------------------------------------------
        ### Check list of hosts provided
        ### -------------------------------------------------------------
        for host in inventory.keys():
            if isinstance(inventory[host], dict):

                ## TODO check if the dictionnary contain at least tags and address
                if 'tags' not in inventory[host]:
                    self.log.warn('host: tags are missing for %s, not supported, skipping' % host)
                    continue
                elif 'address' not in inventory[host]:
                    self.log.warn('host: address is missing for %s, not supported, skipping' % host)
                    continue

                self.hosts[host] = inventory[host]

                if 'context' not in self.hosts[host]:
                    self.hosts[host]['context'] = []

            elif isinstance(inventory[host], str):

                tags = inventory[host].split()
                self.hosts[host] = {
                    'tags': tags,
                    'address': host,
                    'context': []
                }

            else:
                self.log.warn('host: format for %s not spported, skipping' % host)


    def get_target_hosts(self, tags=[]):
        """
        Return a list of host name matching a list of tags
        """

        if not isinstance(tags, list) or tags == []:
            return []

        target_hosts = {}
        for tag in tags:
            self.log.debug('will find matching host for %s' % tag)

            for host in sorted(self.hosts.keys()):       
                
                self.log.debug('will check if %s is matching %s' % (host, tag))
                for hosts_tag in self.hosts[host]['tags']:
                    if re.search(tag, hosts_tag, re.IGNORECASE):
                        target_hosts[host] = 1

        return sorted(target_hosts.keys())


    def get_target_commands(self, host, tags=['.*']):
        """
        Return the list of commands matching for a given target and a given list of tags
        """

        if host not in self.hosts:
            return None

        host_tags = self.hosts[host]['tags']

        groups_matched = []

        ## First do a pass based on host tag and identify all group_command that matches
        for group_command, command in self.commands.items():
            for host_tag in host_tags:
                for command_tag in command['tags']:
                    if re.search(host_tag, command_tag, re.IGNORECASE):
                        groups_matched.append(group_command)

        ## Second do a pass on command tag on the list of group_command that passed the previous check
        final = set()
        for group_command in groups_matched:
            for tag in tags:
                for command_tag in self.commands[group_command]['tags']:
                    if re.search(tag, command_tag, re.IGNORECASE):
                        final.add(group_command)

        return [self.commands[group] for group in final]


    def get_credentials(self, host):

        if host not in self.hosts:
            return None

        for credential in sorted(self.credentials.keys()):
            for host_tag in self.hosts[host]['tags']:
                for credential_tag in self.credentials[credential]['tags']:
                    self.log.debug('will check if %s is matching %s' % (host_tag,credential_tag))
                    if re.search(host_tag, credential_tag, re.IGNORECASE):
                        return self.credentials[credential]

        return None
                       

    def get_context(self, host):

        if host not in self.hosts:
            return None

        return self.hosts[host]['context']


    def get_address(self, host):
        if host not in self.hosts:
            return None

        return self.hosts[host]['address']


    def get_device_type(self, host):
        return self.hosts[host].get('device_type', 'juniper')
