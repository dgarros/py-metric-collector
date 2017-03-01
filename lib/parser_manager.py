import logging
import pprint
import os
import yaml
from lxml import etree
import copy
import re

logger = logging.getLogger('parser_manager' )

pp = pprint.PrettyPrinter(indent=4)

class ParserManager:

  def __init__( self, parser_dir='../parsers' ):

    self.parsers = {}

    self.nbr_regex_parsers = 0
    self.nbr_xml_parsers = 0
    self.nbr_pyez_parsers = 0

    ## Check if parser_dir exist
    if not os.path.exists(parser_dir):
       logger.critical('Parser Directory is not present: %s', parser_dir)
    self.__parser_dir = parser_dir

    ## Import all parsers
    self.__import_parsers__()

  def __import_parsers__( self ):

    ## Get list of all parsers in the directory
    junos_parsers_files = os.listdir(self.__parser_dir)

    ## Load parsers and Classify them properly
    for junos_parsers_file in junos_parsers_files:
      parser = {
        "name": junos_parsers_file,
        "command": None,
        "data": None,
        "type": 'xml'
      }

      full_junos_parsers_file = self.__parser_dir + "/" + junos_parsers_file

      try:
        with open(full_junos_parsers_file) as f:
          parser["data"] = yaml.load(f)
      except Exception, e:
        logger.error('Error importing junos parser, yaml non valid: %s. %s', junos_parsers_file, str(e))
        continue

      if parser["data"] == {}:
        logger.error('Error importing junos parser: %s. Yaml empty', junos_parsers_file)
        continue

      ## Check if parser contain a key "parser"
      if not ( parser['data'].has_key("parser") ):
        logger.error('Error loading junos parser: %s, parser structure is missing', parser['name'])
        continue

      # Check parser type
      if not ( parser["data"]["parser"].has_key("type") ):
        logger.warn('Type is not defined for parser %s, default XML', parser['name'])

      elif parser["data"]["parser"]['type'] == 'xml' or parser["data"]["parser"]["type"] == 'regex':
        parser['type'] = parser['data']['parser']['type']
      else:
        logger.warn('Parser type %s is not supported, %s', parser['data']['parser']['type'], parser['name'])
        continue

      ## Extract the command from the parser
      if parser['data']['parser'].has_key( "regex-command" ):
        parser['command'] = parser['data']['parser']['regex-command']

      elif parser['data']['parser'].has_key( "command" ):
        parser['command'] = parser['data']['parser']['command']
      else:
        logger.error('Unable to find the command for parser: %s', parser['name'])
        continue

      self.__add_parser__( name=parser['name'], parser=parser )

  def __find_parser__( self, input=None ):
    """
    ## Check parser in this order
    # 0- parser name
    # 1- pyez
    # 2- xml
    # 3- regex
    """

    ## Check with parser name
    for name, parser in self.parsers.iteritems():
      if name == input:
        return parser

    ### if parser not find with name, we need to search with command

    command = ''
    command_xml = ''

    # Check if the command include "| display xml"
    # if not create a version with display xml
    display_xml_regex = r"(\s*\|\s*display\s*xml\s*)$"

    has_display_xml = re.search(display_xml_regex, input,re.MULTILINE)

    if has_display_xml:
      command = re.sub(display_xml_regex, "", input)
      command_xml = input
    else:
      command = input
      command_xml = input + " | display xml"

    ## Check for parsers pyez, xml and regex
    for type in ['pyez', 'xml', 'regex']:

      for name, parser in self.parsers.iteritems():
        if parser['type'] != type:
          continue

        # Check if command in file is regex or not
        command_is_regex = False

        ## Check if command is a regex or not
        if re.search(r"\\s[\+\*]", parser['command'],re.MULTILINE):
          command_is_regex = True
          command_re = re.compile(parser['command'])

        if command_is_regex:
          if command_re.match(command) or command_re.match(command_xml):
            return parser
        else:
          if parser['command'] == command or parser['command'] == command_xml:
            return parser

    ## if nothing has been found
    return None

  def __add_parser__( self, name=None, parser={} ):

    if not name:
      return False

    ##TODO Check if parser is valid
    ## If XML check that matches exist

    ## Count numbers of parsers of each type
    if parser['type'] == 'xml':
      self.nbr_xml_parsers += 1
    elif parser['type'] == 'regex':
      self.nbr_regex_parsers += 1
    elif parser['type'] == 'pyez':
      self.nbr_pyez_parsers += 1

    self.parsers[name] = parser

    return True

  def get_nbr_parsers( self ):
    return self.nbr_pyez_parsers + self.nbr_xml_parsers + self.nbr_regex_parsers

  def get_parser_name_for( self, input=None ):

    parser = self.__find_parser__( input=input )

    if parser:
      return parser['name']
    else:
      return None

  def get_command( self, input=None):

     ## Get parser
     ## extract Command
     ## Return Command

        format = "text"
        command_tmp = command
        if re.search("\| display xml", command, re.IGNORECASE):
            format = "xml"
            command_tmp = command.replace("| display xml","")
        elif re.search("\| count", command, re.IGNORECASE):
            format = "txt-filtered"
            command_tmp = command.split("|")[0]

  def parse( self, input=None, data=None):

    parser = self.__find_parser__(input=input)
    
    try:
      if parser['type'] == 'xml':
        return self.__parse_xml__(parser=parser, data=data)
      elif parser['type'] == 'regex':
        return self.__parse_regex__(parser=parser, data=data)
    except TypeError as t_err:
      return None    
  def __parse_xml__(self, parser=None, data=None):

    datas_to_return = []

    ## Empty structure that needs to be filled and return for each input
    data_structure = {
        'measurement': None,
        'tags': {},
        'fields': {}
    }

    ## Convert data to etree
    xml_data = etree.fromstring(data)

    ## NOTE, There is an assumption that all matches will be either
    # - single-value
    # - multi-value
    ## it might not work as it, if we have a mix of both

    for match in parser["data"]["parser"]["matches"]:
        if match["type"] == "single-value":
          logger.debug('Looking for a match: %s', match["xpath"])
          if xml_data.xpath(match["xpath"]):
            value_tmp = xml_data.xpath(match["xpath"])[0].text.strip()
            key_tmp = self.cleanup_xpath(match['xpath'])

            data_structure['fields'][key_tmp] = value_tmp

          else:
            logger.debug('No match found: %s', match["xpath"])
            if 'default-if-missing' in match.keys():
              logger.debug('Inserting default-if-missing value: %s', match["default-if-missing"])
              value_tmp = match["default-if-missing"]
              key_tmp = self.cleanup_xpath(match['xpath'])

              data_structure['fields'][key_tmp] = value_tmp

        elif match["type"] == "multi-value":
          nodes = xml_data.xpath(match["xpath"])
          for node in nodes:
            #Look for all posible keys or fields to extract and be used for variable-naming
            #key = node.xpath(match["loop"]["key"])[0].text.replace(" ","_").strip()

            keys = {}
            tmp_data = copy.deepcopy(data_structure)
            keys_tmp = copy.deepcopy(match["loop"])

            if 'sub-matches' in keys_tmp.keys():
              del keys_tmp['sub-matches']

            for key_tmp in keys_tmp.keys():
              key_name = self.cleanup_xpath(xpath=keys_tmp[key_tmp])
              tmp_data['tags'][key_name] = node.xpath(keys_tmp[key_tmp])[0].text.replace(" ","_").strip()

            ## pp.pprint(tmp_data)

            for sub_match in match["loop"]["sub-matches"]:
              logger.debug('Looking for a sub-match: %s', sub_match["xpath"])
              if node.xpath(sub_match["xpath"]):
                if "regex" in sub_match:
                    value_tmp = node.xpath(sub_match["xpath"])[0].text.strip()
                    regex = sub_match["regex"]
                    text_matches = re.search(regex,value_tmp,re.MULTILINE)
                    if text_matches:
                      if text_matches.lastindex == len(sub_match["variables"]):
                        logger.debug('We have (%s) matches with this regex %s', text_matches.lastindex,regex)
                        for i in range(0,text_matches.lastindex):
                          j=i+1
                          variable_name = self.eval_variable_name(sub_match["variables"][i]["variable-name"],host=host)
                          value_tmp = text_matches.group(j).strip()

                          # Begin function  (pero pendiente de ver si variable-type existe y su valor)
                          if "variable-type" in sub_match["variables"][i]:
                            value_tmp = self.eval_variable_value(value_tmp, type=sub_match["variables"][i]["variable-type"])
                            key_tmp = self.cleanup_xpath(sub_match["variables"][i]['xpath'])
                            tmp_data['fields'][key_tmp] = value_tmp
                      else:
                        logger.error('More matches found on regex than variables especified on parser: %s', regex_command)
                    else:
                      logger.debug('No matches found for regex: %s', regex)
                else:
                    value_tmp = node.xpath(sub_match["xpath"])[0].text.strip()
                    key_tmp = self.cleanup_xpath(sub_match['xpath'])
                    tmp_data['fields'][key_tmp] = value_tmp

              else:
                  logger.debug('No match found: %s', match["xpath"])
                  if 'default-if-missing' in sub_match.keys():
                    logger.debug('Inserting default-if-missing value: %s', sub_match["default-if-missing"])
                    value_tmp = sub_match["default-if-missing"]
                    key_tmp = self.cleanup_xpath(sub_match['variable-name']['xpath'])
                    tmp_data['fields'][key_tmp] = value_tmp

            datas_to_return.append(tmp_data)

    # if it's not empty, add it to the list
    if len(data_structure['fields'].keys()) > 0:
      datas_to_return.append(data_structure)

    # pp.pprint(data_to_return)
    return datas_to_return

  def __parse_regex__(self, parser=None, data=None):

    datas_to_return = []

    ## Empty structure that needs to be filled and return for each input
    data_structure = {
        'measurement': None,
        'tags': {},
        'fields': {}
    }

    for match in parser["data"]["parser"]["matches"]:

      if match["type"] == "single-value":
        regex = match["regex"]
        text_matches = re.search(regex,data,re.MULTILINE)
        if text_matches:

          if text_matches.lastindex == len(match["variables"]):
            logger.debug('We have (%s) matches with this regex %s', text_matches.lastindex,regex)

            tmp_data_structure = copy.deepcopy(data_structure)

            for i in range(0,text_matches.lastindex):
              j=i+1
              variable_name = self.eval_variable_name(match["variables"][i]["variable-name"])
              value_tmp = text_matches.group(j).strip()
              # Begin function  (pero pendiente de ver si variable-type existe y su valor)
              if "variable-type" in match["variables"][i]:
                value_tmp = self.eval_variable_value(value_tmp, type=match["variables"][i]["variable-type"])
                key_tmp = self.cleanup_variable(match["variables"][i]['variable-name'])

                ## Check if this is a Tags or not
                if 'tag' in match["variables"][i] and match["variables"][i]['tag']:
                  tmp_data_structure['tags'][key_tmp] = value_tmp
                else:
                  tmp_data_structure['fields'][key_tmp] = value_tmp

              else:
                logger.error('More matches found on regex than variables especified on parser: %s', regex_command)

            datas_to_return.append(tmp_data_structure)
        else:
          logger.debug('No matches found for regex: %s', regex)
      else:
       logger.error('An unkown match-type found in parser with regex: %s', regex_command)

    # pp.pprint([data_structure])
    return datas_to_return

  def eval_variable_name(self, variable,**kwargs):
    
    keys={}
    db_schema = 3

    if 'keys' in kwargs.keys():
        # This is due dict are mutable and a normal assigment does NOT copy the value, it copy the reference
        keys=copy.deepcopy(kwargs['keys'])
    if db_schema == 3:
        for key in keys.keys():
            variable = variable.replace("$"+key,"")
            variable = variable.replace("..",".")
        variable = variable.replace("$host","")
        variable = re.sub(r"^\.", "", variable)
        return variable, variable
    if db_schema == 2:
        for key in keys.keys():
            variable = variable.replace("$"+key,"")
            variable = variable.replace("..",".")
        variable = variable.replace("$host","")
        variable = re.sub(r"^\.", "", variable)
        return "jnpr.collector", variable
    else: # default db_schema (option 1) open-nti legacy
        for key in keys.keys():
            variable = variable.replace("$"+key,keys[key])
        variable = variable.replace("$host",kwargs['host'])
        # the host replacement should be move it to other place
        return variable, variable

  def eval_variable_value(self, value, **kwargs):

    if (kwargs["type"] == "integer"):
      value =  re.sub('G','000000000',value)
      value =  re.sub('M','000000',value)
      value =  re.sub('K','000',value)
      return(int(float(value)))
    elif kwargs["type"] == "string":
      return value
    else:
      logger.error('An unkown variable-type found: %s', kwargs["type"])
      return value

  def cleanup_xpath( self, xpath=None ):

    if xpath:
      xpath = xpath.replace("./", "")
      xpath = xpath.replace("//", "")

      return xpath

    return None

  def cleanup_variable( self, name=None ):

    if name:
        return name.replace("$host.", "")

    return None

 # TODO See what to do with txt-filtered & | Count
 # elif format == "txt-filtered":
 #     operations = command.split("|")[1:]
 #     result_tmp = command_result.text
 #     lines=result_tmp.strip().split('\n')
 #     for operation in operations:
 #         logger.info("Processing <%s>", operation )
 #         if re.search("count", operation, re.IGNORECASE):
 #             result = "Count: %s lines" % len(lines)
 #             logger.debug("Count result: <%s>", result )
 #             return result
 #         match = re.search("match (.*)", operation, re.IGNORECASE)
 #         if match:
 #             regex = match.group(1).strip()
 #             logger.debug("Found regex: <%s>", regex )
 #             lines_filtered = []
 #             for line in lines:
 #                 if re.search(regex, line, re.IGNORECASE):
 #                     lines_filtered.append(line)
 #             lines = lines_filtered
 #             logger.debug("Filtered result:\n%s", "\n".join(lines_filtered) )
 #         match = re.search("except (.*)", operation, re.IGNORECASE)
 #         if match:
 #             regex = match.group(1).strip()
 #             logger.debug("Found regex: <%s>", regex )
 #             lines_filtered = []
 #             for line in lines:
 #                 if re.search(regex, line, re.IGNORECASE):
 #                     pass
 #                 else:
 #                     lines_filtered.append(line)
 #             lines = lines_filtered
 #             logger.debug("Filtered result:\n%s", "\n".join(lines_filtered) )
 #     return "\n".join(lines)
