import logging
import pprint
import os
import yaml
from lxml import etree
import copy
import re
import textfsm
from io import StringIO

logger = logging.getLogger('parser_manager' )

pp = pprint.PrettyPrinter(indent=4)

## Pyez is not fully supported, need to work on that 
SUPPORTED_PARSER_TYPE = ['xml', 'textfsm', 'pyez', 'regex' ]

class ParserManager:

  def __init__( self, parser_dirs=[], default_parser_dir = '../../parsers' ):

    self.parsers = {}

    self.nbr_regex_parsers = 0
    self.nbr_xml_parsers = 0
    self.nbr_textfsm_parsers = 0
    self.nbr_pyez_parsers = 0

    if  isinstance(parser_dirs, list):
      self.__parser_dirs = parser_dirs
    else:
      self.__parser_dirs = []

    if default_parser_dir:
      current_dir = os.path.dirname(os.path.abspath(__file__))
      self.__parser_dirs.append(current_dir + "/" + default_parser_dir)

    ## Import all parsers
    self.__import_parsers__()

  def __import_parsers__( self ):

    ## Get list of all parsers in the directory
    for parser_dir in self.__parser_dirs:

      if os.path.exists(parser_dir):
        junos_parsers_files = os.listdir(parser_dir)
      else:
        logger.warning("Parser directory %s not found, skipping" % parser_dir)
        continue

      ## Load parsers and Classify them properly
      for junos_parsers_file in junos_parsers_files:
        parser = {
          "name": junos_parsers_file,
          "command": None,
          "data": None,
          "measurement": None,
          "type": 'xml'
        }

        full_junos_parsers_file = parser_dir + "/" + junos_parsers_file

        try:
          with open(full_junos_parsers_file) as f:
            parser["data"] = yaml.load(f)
        except Exception as e:
          logger.error('Error importing junos parser, yaml non valid: %s. %s', junos_parsers_file, str(e))
          continue

        if parser["data"] == {}:
          logger.error('Error importing junos parser: %s. Yaml empty', junos_parsers_file)
          continue

        ## Check if parser contain a key "parser"
        if not "parser" in parser['data'].keys():
          logger.error('Error loading junos parser: %s, parser structure is missing', parser['name'])
          continue

        # Check parser type
        if not "type" in parser["data"]["parser"].keys():
          logger.warn('Type is not defined for parser %s, default XML', parser['name'])

        elif parser["data"]["parser"]['type'] in SUPPORTED_PARSER_TYPE:
          parser['type'] = parser['data']['parser']['type']
        else:
          logger.warn('Parser type %s is not supported, %s', parser['data']['parser']['type'], parser['name'])
          continue

        ## Extract the command from the parser
        if "regex-command" in parser['data']['parser'].keys():
          parser['command'] = parser['data']['parser']['regex-command']

        elif 'command' in parser['data']['parser'].keys():
          parser['command'] = parser['data']['parser']['command']
        else:
          logger.error('Unable to find the command for parser: %s', parser['name'])
          continue

        if "measurement" in parser['data']['parser'].keys():
          parser['measurement'] = parser['data']['parser']['measurement']

        self.__add_parser__( name=parser['name'], parser=parser )

  def __find_parser__( self, input=None ):
    """
    ## First check parser by name
    ## if nothing found, keep searching by type base on order defined in SUPPORTED_PARSER_TYPE
    """

    ## Check with parser name
    for name, parser in self.parsers.items():
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

    ## Check for parsers by type
    for parser_type in SUPPORTED_PARSER_TYPE:
      
      # logger.debug('Searching parser for %s', parser_type)

      for name, parser in self.parsers.items():
        if parser['type'] != parser_type:
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

    logger.debug('Adding parser: %s [%s]' %( name, parser['type']))

    ##TODO Check if parser is valid

    ## Count numbers of parsers of each type
    if parser['type'] == 'xml':
      self.nbr_xml_parsers += 1
    elif parser['type'] == 'textfsm':
      self.nbr_textfsm_parsers += 1
    elif parser['type'] == 'regex':
      self.nbr_regex_parsers += 1
    elif parser['type'] == 'pyez':
      self.nbr_pyez_parsers += 1

    self.parsers[name] = parser

    return True

  def get_nbr_parsers( self ):
    return self.nbr_pyez_parsers + self.nbr_textfsm_parsers + self.nbr_xml_parsers + self.nbr_regex_parsers

  def get_parser_name_for( self, input=None ):

    parser = self.__find_parser__( input=input )

    if parser:
      return parser['name']
    else:
      return None


  def parse( self, input=None, data=None):

    parser = self.__find_parser__(input=input)
  
    try:
      if parser['type'] == 'xml':
        return self.__parse_xml__(parser=parser, data=data)
      elif  parser['type'] == 'textfsm':
        return self.__parse_textfsm__(parser=parser, data=data)
      elif parser['type'] == 'regex':
        return self.__parse_regex__(parser=parser, data=data)
    except TypeError as t_err:
      logger.error('Something went wrong while parsing : %s > %s' % (parser['name'], t_err))
      return []


  def get_measurement_name(self, input=None):

    parser = self.__find_parser__(input=input)
    
    if parser:
      logger.debug('Looking for a measurement name (keys): %s', parser.keys())
      if 'measurement' in parser.keys():
        return parser['measurement']

    measurement_name = parser['command']

    ## For now, generate_measurement from command
    measurement_name = measurement_name.replace(' ','_')
    measurement_name = measurement_name.replace('-','_')
    measurement_name = measurement_name.replace('show_','')

    return measurement_name


  def __parse_xml__(self, parser=None, data=None):

    datas_to_return = []

    logger.debug("will parse %s with xml" % parser['command'])
    # logger.debug("data %s" % data)
    ## Empty structure that needs to be filled and return for each input
    data_structure = {
        'measurement': None,
        'tags': {},
        'fields': {}
    }

    single_match = copy.deepcopy(data_structure)

    clean_data = re.sub(r"\sxmlns\=\".*\"", '', data.decode(), re.M)
    clean_data = re.sub(r"\sjunos\:", ' ', clean_data, re.M)
    xml_data = etree.fromstring(clean_data)

    ## NOTE, There is an assumption that all matches will be either
    # - single-value
    # - multi-value
    ## it might not work as it, if we have a mix of both

    for match in parser["data"]["parser"]["matches"]:

        if match["type"] == "single-value":
          
          logger.debug('Looking for a match: %s', match["xpath"])
          value_tmp = xml_data.xpath(match["xpath"])
          if value_tmp:
          
            if 'variable-name' in match:
              key_name = match['variable-name']
            else: 
              key_name = self.cleanup_xpath(match['xpath'])

            if isinstance(value_tmp[0], str):
              single_match['fields'][key_name] = value_tmp[0].strip()
            else:
              single_match['fields'][key_name] = value_tmp[0].text.strip()

          else:
            logger.debug('No match found: %s', match["xpath"])
            if 'default-if-missing' in match.keys():
              logger.debug('Inserting default-if-missing value: %s', match["default-if-missing"])
              value_tmp = match["default-if-missing"]

              if 'variable-name' in match.keys():
                key_tmp = match['variable-name']
              else: 
                key_tmp = self.cleanup_xpath(match['xpath'])

              single_match['fields'][key_tmp] = value_tmp

        elif match["type"] == "multi-value":

          nodes = xml_data.xpath(match["xpath"])
          for node in nodes:
            #Look for all posible keys or fields to extract and be used for variable-naming
            #key = node.xpath(match["loop"]["key"])[0].text.replace(" ","_").strip()

            keys = {}
            tmp_data = copy.deepcopy(data_structure)
            keys_tmp = copy.deepcopy(match["loop"])

            ## Assign measurement name if defined 
            if 'measurement' in match:
              tmp_data['measurement'] = match['measurement']

            if 'sub-matches' in keys_tmp.keys():
              del keys_tmp['sub-matches']

            for key_tmp in keys_tmp.keys():
              key_name = key_tmp

              key_results = node.xpath(keys_tmp[key_tmp])

              if len(key_results) == 0:
                continue
              
              if isinstance(key_results[0], str):
                tmp_data['tags'][key_name] = self.cleanup_tag(key_results[0].strip())
              else:
                tmp_data['tags'][key_name] = self.cleanup_tag(key_results[0].text.strip())

              ## Cleanup string
              tmp_data['tags'][key_name].replace(" ","_")

            for sub_match in match["loop"]["sub-matches"]:

              if node.xpath(sub_match["xpath"]):
                if "regex" in sub_match.keys():

                    if isinstance(node.xpath(sub_match["xpath"])[0], str):
                      value_tmp = node.xpath(sub_match["xpath"])[0].strip()
                    else:
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
                        logger.error('More matches found on regex than variables specified on parser: %s', regex_command)
                    else:
                      logger.debug('No matches found for regex: %s', regex)

                else:
                    if isinstance(node.xpath(sub_match["xpath"])[0], str):
                      value_tmp = node.xpath(sub_match["xpath"])[0].strip()
                    else:
                      value_tmp = node.xpath(sub_match["xpath"])[0].text.strip()

                    if 'variable-name' in sub_match.keys():
                      key_tmp = sub_match['variable-name']
                    else: 
                      key_tmp = self.cleanup_xpath(sub_match['xpath'])
                    
                    if 'transform' in sub_match.keys():
                      if sub_match['transform'] == 'str_2_int':
                        value_tmp = self.str_2_int(value_tmp)
                    
                    if value_tmp:
                      tmp_data['fields'][key_tmp] = value_tmp

              else:
                  logger.debug('No match found: %s', match["xpath"])
                  if 'default-if-missing' in sub_match.keys():
                    logger.debug('Inserting default-if-missing value: %s', sub_match["default-if-missing"])
                    value_tmp = sub_match["default-if-missing"]
                    if 'variable-name' in sub_match.keys():
                      key_tmp = sub_match['variable-name']
                    else: 
                      key_tmp = self.cleanup_xpath(sub_match['xpath'])
                    
                    tmp_data['fields'][key_tmp] = value_tmp

            datas_to_return.append(tmp_data)

    # if it's not empty, add it to the list
    if len(single_match['fields'].keys()) > 0:
      datas_to_return.append(single_match)

    return datas_to_return


  def __parse_textfsm__(self, parser=None, data=None):

    datas_to_return = []

    ## Empty structure that needs to be filled and return for each input
    data_structure = {
        'measurement': None,
        'tags': {},
        'fields': {}
    }

    if 'measurement' in parser:
      data_structure['measurement'] = parser['measurement']

    ## TODO Check if template exist
    tpl_file = StringIO(parser['data']['parser']['template'])

    # The argument 'template' is a file handle and 'raw_text_data' is a string.
    res_table = textfsm.TextFSM(tpl_file)
    res_data = res_table.ParseText(data.decode())

    headers = list(res_table.header)
    ## Extract 
    for row in res_data:
      tmp_data = copy.deepcopy(data_structure)
        
      for field in parser['data']['parser']['fields']:
        if field not in headers: 
          continue
        
        idx = headers.index(field)
        field_name = parser['data']['parser']['fields'][field]

        ## Attempt to clean data if it contains KMG info
        if 'M' in row[idx] or 'K' in row[idx] or 'G' in row[idx]:
          value = self.eval_variable_value(row[idx], type='integer')
        else:
          value = row[idx]

        tmp_data['fields'][field_name] = str(value)
        
      for tag in parser['data']['parser']['tags']:
        if tag not in headers: 
          continue
        
        idx = headers.index(tag)
        tag_name = parser['data']['parser']['tags'][tag]
        tmp_data['tags'][tag_name] = self.cleanup_tag(row[idx])
         
      datas_to_return.append(tmp_data)
  
    # pprint.pprint(datas_to_return)
    return datas_to_return


  def __parse_regex__(self, parser=None, data=None):

    datas_to_return = []

    ## Empty structure that needs to be filled and return for each input
    data_structure = {
        'measurement': None,
        'tags': {},
        'fields': {}
    }

    # logger.debug('REGEX, will try to parse %s' % data)
    logger.debug('REGEX, parser %s' % parser) 
    
    for match in parser["data"]["parser"]["matches"]:
      
      logger.debug('REGEX, matches of type %s' % match["type"]) 
    
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
                  tmp_data_structure['tags'][key_tmp] = self.cleanup_tag(value_tmp)
                else:
                  tmp_data_structure['fields'][key_tmp] = value_tmp

              else:
                logger.error('More matches found on regex than variables especified on parser: %s', parser['name'])

            datas_to_return.append(tmp_data_structure)
        else:
          logger.debug('No matches found for regex: %s', regex)
      else:
       logger.error('An unkown match-type found in parser with regex: %s', parser['name'])


    logger.debug('REGEX returned: %s', datas_to_return)
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

  @staticmethod
  def cleanup_tag( str_in ):
    """
    Cleanup a string to make sure it doesn't contain space
    """

    tmp_str = str_in
    
    forbidden_chars = [" ", "=", ","]
    for char in forbidden_chars: 
      tmp_str = tmp_str.replace(char, "_")

    return tmp_str

  @staticmethod
  def cleanup_xpath( xpath=None ):

    if xpath:
      xpath = xpath.replace("./", "")
      xpath = xpath.replace("..", "")
      xpath = xpath.replace("//", "")

      return xpath

    return None

  @staticmethod
  def cleanup_variable( name=None ):

    if name:
        return name.replace("$host.", "")

    return None

  @staticmethod
  def str_2_int(value):
    """
    Try to Convert a string into an integer
    """

    ## if the value provided is not a string 
    #   or do not contains some integers 
    #   return None
    if not isinstance(value, str):
      return None
    elif re.match('[0-9]+', value) is None:
      return None

    value =  re.sub('gbps','000000000', value, flags=re.IGNORECASE)
    value =  re.sub('mbps','000000', value, flags=re.IGNORECASE)
    value =  re.sub('kbps','000', value, flags=re.IGNORECASE)

    value =  re.sub('G','000000000', value, flags=re.IGNORECASE)
    value =  re.sub('M','000000', value, flags=re.IGNORECASE)
    value =  re.sub('K','000', value, flags=re.IGNORECASE)

    try:
      return int(value)
    except:
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
