# -*- coding: utf-8 -*-
"""
@author: Steinn Ymir Agustsson
"""
import sys, os
import configparser

settings = configparser.ConfigParser() # TODO: find a smarter way
if os.path.isfile(os.path.join(os.path.dirname(__file__), 'SETTINGS.ini')):
    settings.read(os.path.join(os.path.dirname(__file__), 'SETTINGS.ini'))
else:
    settings.read(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'SETTINGS.ini'))

# importing stuff from PAH modules
import sys
sys.path.append(settings['paths']['PAH_MODULE_DIR'])
from camp.pah.beamtimedaqaccess import BeamtimeDaqAccess, H5FileDataAccess, H5FileManager

# Below are the redefined classes belonging to PAH that should correct the 
# problems induced by adding the macrobunchID information to the data.


def main():
    settings = configparser.ConfigParser()
    settings.read('SETTINGS.ini')
    path = settings['paths']['DATA_RAW_DIR']
    daqAccess = BeamtimeDaqAccess.create(path)
    dldPosXName = "/uncategorised/FLASH1_USER2/FLASH.FEL/HEXTOF.DAQ/DLD1:0/dset"
    dldPosY, otherStuff = daqAccess.allValuesOfRun(dldPosXName, 19135)


class BeamtimeDaqAccess(BeamtimeDaqAccess):
    """Overwriting original class to apply local corrections to PAH code.

    """

    def __init__(self, fileAccess):
        super(BeamtimeDaqAccess, self).__init__(fileAccess)

    @staticmethod
    def create(rootDirectoryOfH5Files):
        """ Creates a BeamtimeDaqAccess object for the given root directory - API

        **Parameter**
            rootDirectoryOfH5Files (str): The root directory of the HDF files. The root
                    directory contains sub directories for different FLASH DAQ streams.

        **Return**
            BeamtimeDaqAccess: The ready to use beamtime DAQ access object.

        **Raise**
            AssertionError: If the given rootDirectoryOfH5Files does not exist.
        """
        
        fileAccess = H5FileDataAccess(H5FileManager(rootDirectoryOfH5Files))
        return BeamtimeDaqAccess(fileAccess)


class H5FileDataAccess(H5FileDataAccess):
    """ Wrapper class for correcting PAH code for defining valid channels to read from.
    """

    def __init__(self, h5FileManager):
        super(H5FileDataAccess, self).__init__(h5FileManager)
        # super(self).__init__(h5FileManager)

    def isValidChannel(self, channelName):
        """ Define the valid channels in HDF5 data.

        Add the timing section of the hdf5 dataset as valid channel, as the
        timing channel was not considered a valid channel in the original
        PAH code.

        Returns:
            (bool): True: channel is valid, False: channel not valid.
        """
        return channelName in self.allChannelNames() \
               or channelName.startswith('/uncategorised/') \
               or channelName.startswith('/FL2/') \
               or channelName.startswith('/FL1/Timing/')  # <-- add timing section


class H5FileManager(H5FileManager):
    """ Wrapper for pointing to original class in  PAH module.
    """

    def __init__(self, rootDirectoryOfH5Files):
        super(H5FileManager, self).__init__(rootDirectoryOfH5Files)


if __name__ == '__main__':
    main()
