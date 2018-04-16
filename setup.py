# -*- coding: utf-8 -*-
"""

@author: Steinn Ymir Agustsson
"""


from distutils.core import setup
from Cython.Build import cythonize
import numpy
import os
import platform
if platform.system() == 'Windows':
    setup(
        ext_modules=cythonize("processor\cscripts\DldFlashProcessorCy.pyx"),
        include_dirs = [numpy.get_include()]
    )
else:
    setup(
        ext_modules=cythonize("processor/cscripts/DldFlashProcessorCy.pyx"),
        include_dirs = [numpy.get_include()]
    )
print('Cythonized: DldFlashProcessorCy.pyx')