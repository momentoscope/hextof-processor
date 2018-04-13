# -*- coding: utf-8 -*-
"""

@author: Steinn Ymir Agustsson
"""


from distutils.core import setup
from Cython.Build import cythonize
import numpy

setup(
    ext_modules=cythonize("processor\cscripts\DldFlashProcessorCy.pyx"),
    include_dirs = [numpy.get_include()]
)
print('Cythonized: DldFlashProcessorCy.pyx')