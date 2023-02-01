# -*- coding: utf-8 -*-

from distutils.core import setup, Extension
from Cython.Build import cythonize
import numpy
from os import path

__version__ = '1.0.3'

here = path.abspath(path.dirname(__file__))

# Get the long description from the README file
with open(path.join(here, 'README.md')) as f:
    long_description = f.read()

# Get the dependencies and installs
with open(path.join(here, 'requirements.txt'), encoding='utf-8') as f:
    all_reqs = f.read().split('\n')

# Construct dependency links for registered packages
install_requires = [x.strip() for x in all_reqs if 'git+' not in x]
dependency_links = [x.strip().replace('git+', '') for x in all_reqs if x.startswith('git+')]

build_doniachs = False # TODO: make if statement to build doniachs, and add this as option in SETTINGS.ini

extensions = [
    Extension("processor.cscripts.DldFlashProcessorCy", [path.join("processor", "cscripts", "DldFlashProcessorCy.pyx")],
        include_dirs=[numpy.get_include()]),

#    Extension('XPSdoniachs.XPSdoniachs_ext',
 #                       sources=['XPSdoniachs/XPSdoniachs_ext.cpp'],
  #                      library_dirs=["/usr/local/Cellar/boost-python3/1.67.0/lib/"],
   #                     libraries=["boost_python36"])
]

setup(
    name="hextof-processor",
    version=__version__,
    description='Hextof Offline Analyzer',
    long_description_content_type='text/markdown',
    long_description=long_description,
    author='Yves Acremann, Steinn Ymir Agustsson, Davide Curcio, Rui Patrick Xian, Michael Heber, Maciej Dendzik',
    url='https://github.com/momentoscope/hextof-processor',
    download_url='https://github.com/momentoscope-kit/hextof-processor/tarball/' + __version__,
    license='GNU-GPL',
    classifiers=[
      'Programming Language :: Python :: 3',
    ],
    keywords='',
    packages=['distutils', 'distutils.command'],
    include_package_data=True,
    install_requires=install_requires,
    dependency_links=dependency_links,
    ext_modules=cythonize(extensions)
)
# print('Cythonized: DldFlashProcessorCy.pyx')
