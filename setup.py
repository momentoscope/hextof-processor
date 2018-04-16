# -*- coding: utf-8 -*-
"""

@author: Steinn Ymir Agustsson
"""


from distutils.core import setup
from Cython.Build import cythonize
import numpy
import os

setup(
    ext_modules=cythonize(os.path.join("processor","cscripts","DldFlashProcessorCy.pyx")),
    include_dirs=[numpy.get_include()]
)
print('Cythonized: DldFlashProcessorCy.pyx')