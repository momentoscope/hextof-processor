# -*- coding: utf-8 -*-
"""

@author: Davide Curcio
"""
from distutils.core import setup, Extension

import sys
import os

XPSdoniachs = Extension('pkg.XPSdoniachs_ext',
                        sources=['pythonFitting/XPSdoniachs_ext/XPSdoniachs_ext.cpp'],
                        include_dirs=['/usr/local/include'],
                        library_dirs=['/usr/local/lib/boost'],
                        runtime_library_dirs=['/usr/local/lib/boost'],
                        libraries=['boost_python'])

setup(name='XPSdoniachs',
      version='0.1',
      description='XPSdoniachs',
      packages=['pkg','boost'],
      ext_modules=[XPSdoniachs])
