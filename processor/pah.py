# -*- coding: utf-8 -*-
"""
@author: Steinn Ymir Agustsson
"""
import sys, os
import configparser

os.chdir(os.path.abspath(os.path.dirname(__file__))) # TODO: find a smarter way
if not os.path.isfile('SETTINGS.ini'):
    os.chdir('../')
settings = configparser.ConfigParser()
settings.read('SETTINGS.ini')
PAH_MODULE_DIR = settings['paths']['PAH_MODULE_DIR']

sys.path.append(PAH_MODULE_DIR)  # appends the path where PAH is located, taken from SETTINGS.ini
from camp.pah.beamtimedaqaccess import BeamtimeDaqAccess, H5FileDataAccess, H5FileManager

""" 
below are the redefined classes belonging to PAH that should correct the 
problems induced by adding the macrobunchID information to the data.
"""


def main():
    settings = configparser.ConfigParser()
    settings.read('SETTINGS.ini')
    path = settings['paths']['DATA_RAW_DIR']
    daqAccess = BeamtimeDaqAccess.create(path)
    dldPosXName = "/uncategorised/FLASH1_USER2/FLASH.FEL/HEXTOF.DAQ/DLD1:0/dset"
    dldPosY, otherStuff = daqAccess.allValuesOfRun(dldPosXName, 19135)


class BeamtimeDaqAccess(BeamtimeDaqAccess):
    """overwriting original class to apply local corrections to PAH code.

    """

    def __init__(self, fileAccess):
        super(BeamtimeDaqAccess, self).__init__(fileAccess)

    @staticmethod
    def create(rootDirectoryOfH5Files):
        """ Creates a BeamtimeDaqAccess object for the given root directory - API

        Parameters:
            rootDirectoryOfH5Files (str): The root directory of the HDF files. The root
                    directory contains sub directories for different FLASH DAQ streams.

        Returns:
            BeamtimeDaqAccess: The ready to use beamtime DAQ access object.

        Raises:
            AssertionError: If the given rootDirectoryOfH5Files does not exist.
        """
        fileAccess = H5FileDataAccess(H5FileManager(rootDirectoryOfH5Files))
        return BeamtimeDaqAccess(fileAccess)


class H5FileDataAccess(H5FileDataAccess):
    """ wrapper for correcting PAH code for defining valid channels to read from."""

    def __init__(self, h5FileManager):
        super(H5FileDataAccess, self).__init__(h5FileManager)
        # super(self).__init__(h5FileManager)

    def isValidChannel(self, channelName):
        """ define which are valid channels in HDF5 data.

        Add the timing section of the hdf5 dataset as valid channel, as the
        timing channel was not considered a valid channel in the original
        PAH code.

        Returns:
            (bool): True: channel is valid, False: channel not valid.
        """
        return channelName in self.allChannelNames() \
               or channelName.startswith('/uncategorised/') \
               or channelName.startswith('/FL2/') \
               or channelName.startswith('/Timing/')  # <-- add timing section


class H5FileManager(H5FileManager):
    """ wrapper for pointing to original class in  PAH module."""

    def __init__(self, rootDirectoryOfH5Files):
        super(H5FileManager, self).__init__(rootDirectoryOfH5Files)


if __name__ == '__main__':
    main()
