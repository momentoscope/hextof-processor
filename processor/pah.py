# -*- coding: utf-8 -*-

"""
@author: Steinn Ymir Agustsson
"""

import os
import sys

try:
    from camp.pah.beamtimedaqaccess import BeamtimeDaqAccess as _BeamtimeDaqAccess, H5FileDataAccess as _H5FileDataAccess, \
    H5FileManager as _H5FileManager

except ModuleNotFoundError:
    import configparser

    settings = configparser.ConfigParser()  # TODO: find a smarter way
    if os.path.isfile(os.path.join(os.path.dirname(__file__), 'SETTINGS.ini')):
        settings.read(os.path.join(os.path.dirname(__file__), 'SETTINGS.ini'))
    else:
        settings.read(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'SETTINGS.ini'))
    sys.path.append(settings['paths']['PAH_MODULE_DIR'])

    from camp.pah.beamtimedaqaccess import BeamtimeDaqAccess as _BeamtimeDaqAccess, H5FileDataAccess as _H5FileDataAccess, \
    H5FileManager as _H5FileManager


# Below are the redefined classes belonging to PAH that should correct the
# problems induced by adding the macrobunchID information to the data.


class BeamtimeDaqAccess(_BeamtimeDaqAccess):
    """ Overwriting original class to apply local corrections to PAH code.
    """

    def __init__(self, fileAccess):
        super(BeamtimeDaqAccess, self).__init__(fileAccess)

    @staticmethod
    def create(rootDirectoryOfH5Files):
        """ Creates a BeamtimeDaqAccess object for the given root directory - API

        **Parameter**\n
        rootDirectoryOfH5Files (str): The root directory of the HDF files. The root
                directory contains sub directories for different FLASH DAQ streams.

        **Return**\n
        BeamtimeDaqAccess: The ready to use beamtime DAQ access object.

        **Raise**\n
        AssertionError: If the given rootDirectoryOfH5Files does not exist.
        """

        fileAccess = H5FileDataAccess(H5FileManager(rootDirectoryOfH5Files))
        return BeamtimeDaqAccess(fileAccess)


class H5FileDataAccess(_H5FileDataAccess):
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

        **Return**\n
        (bool): True: channel is valid, False: channel not valid.
        """
        return channelName in self.allChannelNames() \
               or channelName.startswith('/uncategorised/') \
               or channelName.startswith('/FL2/') \
               or channelName.startswith('/FL1/') \
               or channelName.startswith('/Experiment/') \
               or channelName.startswith('/Photon Diagnostic/') \
               or channelName.startswith('/Electron Diagnostic/') \
               or channelName.startswith('/Beamlines/') \
               or channelName.startswith('/Timing/')  # <--for datasets before 08-2018


class H5FileManager(_H5FileManager):
    """ Wrapper for pointing to original class in  PAH module.
    """

    def __init__(self, rootDirectoryOfH5Files):
        super(H5FileManager, self).__init__(rootDirectoryOfH5Files)
