# -*- coding: utf-8 -*-
"""

@author: Steinn Ymir Agustsson
"""
from distutils.core import setup
from distutils.extension import Extension
from Cython.Build import cythonize
import numpy
import os


extensions = [
    Extension("processor.cscripts.DldFlashProcessorCy", [os.path.join("processor", "cscripts", "DldFlashProcessorCy.pyx")],
        include_dirs=[numpy.get_include()])
]

setup(
    name="DldFlashProcessorCy",
    ext_modules=cythonize(extensions)
)
print('Cythonized: DldFlashProcessorCy.pyx')
