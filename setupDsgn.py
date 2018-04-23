# -*- coding: utf-8 -*-
"""

@author: Davide Curcio
"""
from distutils.core import setup, Extension

import sys
import os

XPSdoniachs = Extension('pkg.XPSdoniachs_ext',
                        sources=[os.path.join('pythonFitting','XPSdoniachs_ext','XPSdoniachs_ext.cpp')],
                        libraries=['boost_system'])

setup(name='XPSdoniachs',
      version='0.1',
      description='XPSdoniachs',
      packages=['pkg'],
      ext_modules=[XPSdoniachs])
