#!/usr/bin/env python

import sys
import uuid

from setuptools import setup, find_packages
try: # for pip >= 10
    from pip._internal.req import parse_requirements
except ImportError: # for pip <= 9.0.3
    from pip.req import parse_requirements
    
__author__ = 'Damien Garros <dgarros@gmail.com>'

requirements_data = parse_requirements('requirements.txt', session=uuid.uuid1())
requirements = [str(package.req) for package in requirements_data]

version = '0.0.1'
long_description = "Python Collector for Metrics data over Netconf (junos)"

params = {
    'name': 'py-metric-collector',
    'version': version,
    'package_dir': {'': 'lib'},
    'packages': ["metric_collector"],
    'scripts': [
        'bin/metric-collector'
    ],
    'url': 'https://github.com/xxx',
    'license': 'Apache License, Version 2.0',
    'author': 'Damien Garros',
    'author_email': 'dgarros@gmail.com',
    'description': 'Collect timeserie information over netconf',
    'install_requires': requirements,
    'classifiers': [
        'Topic :: Utilities',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'Intended Audience :: Information Technology',
        'Intended Audience :: System Administrators',
        'License :: OSI Approved :: Apache Software License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
    ],
    'keywords': 'netconf timeserie tsdb'
}

setup(**params)
