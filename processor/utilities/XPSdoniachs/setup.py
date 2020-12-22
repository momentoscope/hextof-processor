# -*- coding: utf-8 -*-
"""

@author: Davide Curcio
"""
from distutils.core import setup, Extension

XPSdoniachs = Extension('XPSdoniachs_ext',
                        sources=['XPSdoniachs_ext.cpp'],
                        libraries=["boost_python37"])

setup(name='XPSdoniachs',
      packages=['.'],
      ext_modules=[XPSdoniachs])
