# -*- coding: utf-8 -*-
"""

@author: Davide Curcio
"""
from distutils.core import setup, Extension
import os

XPSdoniachs = Extension('pkg.XPSdoniachs_ext',
                        sources=[os.path.join('pythonFitting','XPSdoniachs_ext','XPSdoniachs_ext.cpp')],
                        library_dirs=["/usr/local/Cellar/boost-python3/1.67.0/lib/"],
                        libraries=["boost_python36"])

setup(name='XPSdoniachs',
      packages=['pkg'],
      ext_modules=[XPSdoniachs])
