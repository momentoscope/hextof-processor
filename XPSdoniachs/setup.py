# -*- coding: utf-8 -*-
"""

@author: Davide Curcio
"""
from distutils.core import setup, Extension

XPSdoniachs = Extension('XPSdoniachs_ext',
                        sources=['XPSdoniachs_ext.cpp'],
                        library_dirs=["/usr/local/Cellar/boost-python3/1.67.0/lib/"],
                        libraries=["boost_python36"])

setup(name='XPSdoniachs',
      packages=['.'],
      ext_modules=[XPSdoniachs])
