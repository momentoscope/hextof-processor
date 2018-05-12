# -*- coding: utf-8 -*-
"""

@author: Steinn Ymir Agustsson
"""
from distutils.core import setup, Extension
from Cython.Build import cythonize
import numpy
import os

build_doniachs = False

extensions = [
    Extension("processor.cscripts.DldFlashProcessorCy", [os.path.join("processor", "cscripts", "DldFlashProcessorCy.pyx")],
        include_dirs=[numpy.get_include()]),

#    Extension('XPSdoniachs.XPSdoniachs_ext',
 #                       sources=['XPSdoniachs/XPSdoniachs_ext.cpp'],
  #                      library_dirs=["/usr/local/Cellar/boost-python3/1.67.0/lib/"],
   #                     libraries=["boost_python36"])
]

setup(
    name="HextofOfflineAnalyzer",
    version='0.9.0',
    description='Hextof Offline Analyzer',
    author=['Yves Acremann','Steinn Agustsson','Davide Curcio','Patrick Xian'],
    url='https://github.com/momentoscope/HextofOfflineAnalyzer/',
    packages=['distutils', 'distutils.command'],
    ext_modules=cythonize(extensions)
)
# print('Cythonized: DldFlashProcessorCy.pyx')
