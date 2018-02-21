#!/usr/bin/env python

from distutils.core import setup

setup(name='splunknova',
      version='1.0.3',
      description='Python Client for Splunk Project Nova',
      author='Scott Odle',
      author_email='scott@sjodle.com',
      url='https://github.com/sodle/pysplunknova',
      download_url='https://github.com/sodle/pysplunknova/archive/1.0.3.tar.gz',
      license='GPL v3',
      packages=['splunknova'],
      install_requires=[
            'six',
            'requests'
      ]
      )
