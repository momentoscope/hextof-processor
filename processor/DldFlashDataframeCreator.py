import os
from configparser import ConfigParser

import dask
import dask.dataframe
import dask.multiprocessing
import numpy

from processor import DldProcessor, utils
from processor.pah import BeamtimeDaqAccess

_VERBOSE = False

try:
    import processor.cscripts.DldFlashProcessorCy as DldFlashProcessorCy

    if _VERBOSE: print('loaded cython module')
except ImportError as e:
    print('Failed loading Cython script. Using Python version instead. TODO: FIX IT!!#n Error msg: {}'.format(e))
    import processor.cscripts.DldFlashProcessorNotCy as DldFlashProcessorCy
assignToMircobunch = DldFlashProcessorCy.assignToMircobunch



def main():
    from datetime import datetime
    t0 = datetime.now()
    processor = DldFlashProcessor()
    processor.runNumber = 18843
    # processor.pulseIdInterval =
    processor.readData()
    processor.postProcess()

    processor.addBinning('dldTime', 620, 670, 1)
    result = processor.computeBinnedData()
    import matplotlib.pyplot as plt
    plt.plot(result)
    plt.show()
    print("Computation time: {} s".format(datetime.now() - t0))


class DldFlashProcessor(DldProcessor.DldProcessor):
    """ This class reads an existing run and allows to generated binned multidimensional arrays.
    Such arrays can be used directly or saved as HDF5 dataframes..

    This class reads an existing run and generates a hdf5 file containing the dask data frames.
    It is intended to be used with data generated from August 31, 2017 to September 19, 2017.
    Version 4 enables read out of macrobunchID. For evaluation the start ID is set to zero.
    version 5 :
    - introduces overwriting of PAH classes for correct handling of macrobunchID
    - introduces writeRunToMultipleParquet function, for parquet file generation on machines with low ram
    - changed variables to class variables for easier implementation on different machines
    - added some print functions with information about the run that is being imported.

    Had to change the delay stage channel, as the old one (.../ENC.DELAY) stored groups of ~10 times the same value
    (is probably read out with 10 Hz. The new channel is the column (index!) one of .../ENC.
    This change makes the treatment of problematic runs obsolete.



    Attributes:
        runNumber (int): number of the run from which data is taken.
        pulseIdInterval (int): macrobunch ID corresponding to the interval of data
            read from the given run.
        dd (pd.DataFrame): dataframe containing chosen channel information from
            the given run
        dd_microbunch (pd.DataFrame): dataframe containing chosen channel
            information from the given run.
    """

    def __init__(self):
        super().__init__()

        self.runNumber = None
        self.pulseIdInterval = None

    def readData(self, runNumber=None, pulseIdInterval=None, path=None):
        """Access to data by run or macrobunch pulseID interval.


        Useful for scans that would otherwise hit the machine's memory limit.

        Parameters:
            runNumber (int): number of the run from which to read data. If None, requires pulseIdInterval.
            pulseIdInterval (int,int): first and last macrobunches of selected data range. If None, the whole run
                defined by runNumber will be taken.
            path (str): path to location where raw HDF5 files are stored

        This is a union of the readRun and readInterval methods defined in previous versions.
        """
        # check inputs:
        if runNumber is None:
            runNumber = self.runNumber
        else:
            self.runNumber = runNumber
        if pulseIdInterval is None:
            pulseIdInterval = self.pulseIdInterval
        else:
            self.pulseIdInterval = pulseIdInterval

        if pulseIdInterval is None:
            if runNumber is None:
                raise ValueError('Need either runNumber or pulseIdInterval to know what data to read.')

        if path is None:
            path = self.DATA_RAW_DIR

        # parse settings and set all dataset addresses as attributes.
        settings = ConfigParser()
        if os.path.isfile(os.path.join(os.path.dirname(__file__), 'SETTINGS.ini')):
            settings.read(os.path.join(os.path.dirname(__file__), 'SETTINGS.ini'))
        else:
            settings.read(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'SETTINGS.ini'))

        section = 'DAQ address - used'
        daqAddresses = []
        for entry in settings[section]:
            name = utils.camelCaseIt(entry)
            val = str(settings[section][entry])
            daqAddresses.append(name)
            if _VERBOSE: print('assigning address: {}: {}'.format(name.ljust(20), val))
            setattr(self, name, val)

        daqAccess = BeamtimeDaqAccess.create(path)
        # TODO: get the available pulse id from PAH
        if pulseIdInterval is None:
            print('reading DAQ data from run {}...\nPlease wait...'.format(runNumber))

            for address_name in daqAddresses:
                if _VERBOSE: print('reading address: {}'.format(address_name))
                values, otherStuff = daqAccess.allValuesOfRun(getattr(self, address_name), runNumber)
                setattr(self, address_name, values)
                if address_name == 'macroBunchPulseId':  # catch the value of the first macrobunchID
                    pulseIdInterval = (otherStuff[0], otherStuff[-1])
                    macroBunchPulseId_correction = pulseIdInterval[0]
            numOfMacrobunches = pulseIdInterval[1] - pulseIdInterval[0]
            print('Run {0} contains {1:,} Macrobunches, from {2:,} to {3:,}'.format(runNumber,
                                                                                    numOfMacrobunches,
                                                                                    pulseIdInterval[0],
                                                                                    pulseIdInterval[1]))
        else:
            print('reading DAQ data from interval {}'.format(pulseIdInterval))
            self.pulseIdInterval = pulseIdInterval
            for address_name in daqAddresses:
                if _VERBOSE: print('reading address: {}'.format(address_name))
                setattr(self, address_name, daqAccess.valuesOfInterval(getattr(self, address_name), pulseIdInterval))
            numOfMacrobunches = pulseIdInterval[1] - pulseIdInterval[0]
            macroBunchPulseId_correction = pulseIdInterval[0]

        # necessary corrections for specific channels:
        self.delayStage = self.delayStage[:, 1]
        self.macroBunchPulseId -= macroBunchPulseId_correction

        if _VERBOSE: print('Counting electrons...')

        electronsToCount = self.dldPosX.copy().flatten()
        electronsToCount = numpy.nan_to_num(electronsToCount)
        electronsToCount = electronsToCount[electronsToCount > 0]
        electronsToCount = electronsToCount[electronsToCount < 10000]
        numOfElectrons = len(electronsToCount)
        electronsPerMacrobunch = int(numOfElectrons / numOfMacrobunches)
        print("Number of electrons: {0:,}; {1:,} e/Mb ".format(numOfElectrons, electronsPerMacrobunch))
        print("Creating data frame: Please wait...")
        self.createDataframePerElectron()
        self.createDataframePerMicrobunch()
        print('dataframe created')

    def createDataframePerElectronRange(self, mbIndexStart, mbIndexEnd):

        # the chunk size here is too large in order to do the chunking by the loop around it.

        daX = self.dldPosX[mbIndexStart:mbIndexEnd, :].flatten()
        daY = self.dldPosY[mbIndexStart:mbIndexEnd, :].flatten()

        dldDetectorId = (self.dldTime[mbIndexStart:mbIndexEnd, :].copy()).astype(int) % 2
        daDetectorId = dldDetectorId.flatten()

        daTime = self.dldTime[mbIndexStart:mbIndexEnd, :].flatten()

        # convert the bam data to electron format
        bamArray = assignToMircobunch(
            self.dldMicrobunchId[mbIndexStart:mbIndexEnd, :].astype(numpy.float64),
            self.bam[mbIndexStart:mbIndexEnd, :].astype(numpy.float64))
        daBam = bamArray.flatten()

        # convert the delay stage position to the electron format
        delayStageArray = numpy.zeros_like(self.dldMicrobunchId[mbIndexStart:mbIndexEnd, :])
        delayStageArray[:, :] = (self.delayStage[mbIndexStart:mbIndexEnd])[:, None]
        daDelaystage = delayStageArray.flatten()

        daMicrobunchId = self.dldMicrobunchId[mbIndexStart:mbIndexEnd, :].flatten()

        # convert the MacroBunchPulseId to the electron format
        macroBunchPulseIdArray = numpy.zeros_like(self.dldMicrobunchId[mbIndexStart:mbIndexEnd, :])
        macroBunchPulseIdArray[:, :] = (self.macroBunchPulseId[mbIndexStart:mbIndexEnd, 0])[:, None]
        daMacroBunchPulseId = macroBunchPulseIdArray.flatten()

        bunchChargeArray = assignToMircobunch(
            self.dldMicrobunchId[mbIndexStart:mbIndexEnd, :].astype(numpy.float64),
            self.bunchCharge[mbIndexStart:mbIndexEnd, :].astype(numpy.float64))
        daBunchCharge = bunchChargeArray.flatten()

        opticalDiodeArray = assignToMircobunch(
            self.dldMicrobunchId[mbIndexStart:mbIndexEnd, :].astype(numpy.float64),
            self.opticalDiode[mbIndexStart:mbIndexEnd, :].astype(numpy.float64))
        daOpticalDiode = opticalDiodeArray.flatten()

        gmdTunnelArray = assignToMircobunch(
            self.dldMicrobunchId[mbIndexStart:mbIndexEnd, :].astype(numpy.float64),
            self.gmdTunnel[mbIndexStart:mbIndexEnd, :].astype(numpy.float64))
        daGmdTunnel = gmdTunnelArray.flatten()

        gmdBdaArray = assignToMircobunch(
            self.dldMicrobunchId[mbIndexStart:mbIndexEnd, :].astype(numpy.float64),
            self.gmdBda[mbIndexStart:mbIndexEnd, :].astype(numpy.float64))
        daGmdBda = gmdBdaArray.flatten()

        # the Aux channel: aux0:
        # aux0Arr= assignToMircobunch(self.dldMicrobunchId[mbIndexStart:mbIndexEnd, :].astype(numpy.float64), self.dldAux[mbIndexStart:mbIndexEnd, 0].astype(numpy.float64))
        # daAux0 = dask.array.from_array(aux0Arr.flatten(), chunks=(chunks))

        # the Aux channel: aux1:
        # aux1Arr= assignToMircobunch(self.dldMicrobunchId[mbIndexStart:mbIndexEnd, :].astype(numpy.float64), self.dldAux[mbIndexStart:mbIndexEnd, 1].astype(numpy.float64))
        # daAux1 = dask.array.from_array(aux0Arr.flatten(), chunks=(chunks))

        # added macroBunchPulseId at last position
        # da = dask.array.stack([daX, daY, daTime, daDelaystage, daBam, daMicrobunchId,
        #                       daDetectorId, daBunchCharge, daOpticalDiode,
        #                       daGmdTunnel, daMacroBunchPulseId])
        da = numpy.stack([daX, daY, daTime, daDelaystage, daBam, daMicrobunchId,
                          daDetectorId, daBunchCharge, daOpticalDiode,
                          daGmdTunnel, daGmdBda, daMacroBunchPulseId])

        return da

    def createDataframePerElectron(self):
        """ Create a data frame from the read arrays (either from the test file or the run number)



        """

        # self.dldTime=self.dldTime*self.dldTimeStep
        if _VERBOSE: print('creating electron dataframe...')
        maxIndex = self.dldTime.shape[0]
        chunkSize = min(self.CHUNK_SIZE, maxIndex / self.N_CORES)  # ensure minimum one chunk per core.
        numOfPartitions = int(maxIndex / chunkSize) + 1
        daList = []

        for i in range(0, numOfPartitions):
            indexFrom = int(i * chunkSize)
            indexTo = int(min(indexFrom + chunkSize, maxIndex))
            result = dask.delayed(self.createDataframePerElectronRange)(indexFrom, indexTo)
            daList.append(result)
        # self.dd = self.createDataframePerElectronRange(0, maxIndex)
        # create the data frame:
        self.daListResult = dask.compute(*daList)

        a = numpy.concatenate(self.daListResult, axis=1)
        da = dask.array.from_array(a.T, chunks=self.CHUNK_SIZE)

        self.dd = dask.dataframe.from_array(da, columns=('posX', 'posY', 'dldTime', 'delayStageTime', 'bam',
                                                         'microbunchId', 'dldDetectorId',
                                                         'bunchCharge', 'opticalDiode', 'gmdTunnel', 'gmdBda',
                                                         'macroBunchPulseId'))  # TODO: choose columns from SETTINGS

        # self.dd = self.dd[self.dd['microbunchId'] > 0] # TODO: REMOVE? is it really useful?
        self.dd['dldTime'] = self.dd[
                                 'dldTime'] * self.TOF_STEP_TO_NS  # TODO: change to eV? no! this is more Dima friendly

    def createDataframePerMicrobunch(self):
        if _VERBOSE: print('creating microbunch dataframe...')

        numOfMacrobunches = self.bam.shape[0]

        # convert the delay stage position to the electron format
        delayStageArray = numpy.zeros_like(self.bam)
        delayStageArray[:, :] = (self.delayStage[:])[:, None]
        daDelayStage = dask.array.from_array(delayStageArray.flatten(), chunks=self.CHUNK_SIZE)

        # convert the MacroBunchPulseId to the electron format
        macroBunchPulseIdArray = numpy.zeros_like(self.bam)
        macroBunchPulseIdArray[:, :] = (self.macroBunchPulseId[:, 0])[:, None]
        daMacroBunchPulseId = dask.array.from_array(macroBunchPulseIdArray.flatten(), chunks=(self.CHUNK_SIZE))

        daBam = dask.array.from_array(self.bam.flatten(), chunks=(self.CHUNK_SIZE))
        numOfMicrobunches = self.bam.shape[1]

        # the Aux channel: aux0:
        dldAux0 = self.dldAux[:, 0]
        aux0 = numpy.ones(self.bam.shape) * dldAux0[:, None]
        daAux0 = dask.array.from_array(aux0.flatten(), chunks=(self.CHUNK_SIZE))
        # the Aux channel: aux1:
        dldAux1 = self.dldAux[:, 1]
        aux1 = numpy.ones(self.bam.shape) * dldAux1[:, None]
        daAux1 = dask.array.from_array(aux1.flatten(), chunks=(self.CHUNK_SIZE))

        daBunchCharge = dask.array.from_array(self.bunchCharge[:, 0:numOfMicrobunches].flatten(),
                                              chunks=(self.CHUNK_SIZE))

        lengthToPad = numOfMicrobunches - self.opticalDiode.shape[1]
        paddedOpticalDiode = numpy.pad(self.opticalDiode, ((0, 0), (0, lengthToPad)), 'constant',
                                       constant_values=(0, 0))
        daOpticalDiode = dask.array.from_array(paddedOpticalDiode.flatten(), chunks=(self.CHUNK_SIZE))

        # Added MacroBunchPulseId
        da = dask.array.stack([daDelayStage, daBam, daAux0, daAux1, daBunchCharge, daOpticalDiode, daMacroBunchPulseId])

        # create the data frame:
        self.ddMicrobunches = dask.dataframe.from_array(da.T,
                                                        columns=('delayStageTime', 'bam', 'aux0', 'aux1', 'bunchCharge',
                                                                 'opticalDiode', 'macroBunchPulseId'))

    def storeDataframes(self, fileName=None, path=None, format='parquet', append=False):
        """ Saves imported dask dataframe into a parquet or hdf5 file.

        Parameters:
            fileName (string): name of the file where to save data.
            path (str): path to the folder where to save the parquet or hdf5 files.
            format (string, optional): accepts: 'parquet' and 'hdf5'. Choose output file format.
                Default value makes a dask parquet file.
                append (bool): when using parquet file, allows to append the data to a preexisting file.
        """

        format = format.lower()
        assert format in ['parquet', 'h5', 'hdf5'], 'Invalid format for data input. Please select between parquet or h5'

        if path is None:
            if format == 'parquet':
                path = self.DATA_PARQUET_DIR
            else:
                path = self.DATA_H5_DIR
        if fileName is None:
            if self.runNumber is None:
                fileName = 'mb{}to{}'.format(self.pulseIdInterval[0], self.pulseIdInterval[1])
            else:
                fileName = 'run{}'.format(self.runNumber)
        fileName = path + fileName  # TODO: test if naming is correct

        if format == 'parquet':
            if append:
                self.dd.to_parquet(fileName + "_el", compression="UNCOMPRESSED", append=True, ignore_divisions=True)
                self.ddMicrobunches.to_parquet(fileName + "_mb", compression="UNCOMPRESSED", append=True,
                                               ignore_divisions=True)
            else:
                self.dd.to_parquet(fileName + "_el", compression="UNCOMPRESSED")
                self.ddMicrobunches.to_parquet(fileName + "_mb", compression="UNCOMPRESSED")
        elif format == 'hdf5':
            dask.dataframe.to_hdf(self.dd, fileName, '/electrons')
            dask.dataframe.to_hdf(self.ddMicrobunches, fileName, '/microbunches')

    def getIds(self, runNumber=None, path=None):
        """ Returns initial and final MBunchIDs of runNumber

        Parameters:
            runNumber (int): number of the run from which to read id interval.
            path (str): path to location where raw HDF5 files are stored
        """

        if runNumber is None:
            runNumber = self.runNumber
        else:
            self.runNumber = runNumber

        if path is None:
            path = self.DATA_RAW_DIR

        # Gets paths from settings file.
        # Checks for SETTINGS.ini in processor folder.
        # If not there, checks parent directory
        settings = ConfigParser()
        if os.path.isfile(os.path.join(os.path.dirname(__file__), 'SETTINGS.ini')):
            settings.read(os.path.join(os.path.dirname(__file__), 'SETTINGS.ini'))
        else:
            settings.read(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'SETTINGS.ini'))
        path = settings['paths']['DATA_RAW_DIR']

        # needs to import stuff from PAH modules
        import sys
        sys.path.append(settings['paths']['PAH_MODULE_DIR'])
        from camp.pah.beamtimedaqaccess import H5FileDataAccess, H5FileManager
        fileAccess = H5FileDataAccess(H5FileManager(path))
        pulseIdInterval = fileAccess.availablePulseIdInterval(runNumber)

        return pulseIdInterval



    # ==================
    # DEPRECATED METHODS
    # ==================
    def readRun(self, runNumber=None, path=None):
        """ Read a run

        Generates dd and dd_micrubunches attributes as pd.DataFrame
        containing data from the given run.

        Parameters:
            runNumber (int, optional): number corresponding to the rung to read data from. if None, it uses the value
                defined in the runNumber attribute.
            path (str): path to location where raw HDF5 files are stored. If None, it uses the value from SETTINGS.ini.

        Raises:
            AttributeError: if runNumber is not given and

        Example:
            processor = DldFlashProcessor()
            processor.readRun(19059)

        """
        print('WARNING: readRun method is obsolete. Please use readData(runNumber=xxx).')

        if path is None:  # allow for using the default path, which can be redefined as class variable.
            path = self.DATA_RAW_DIR
        if runNumber is None:
            runNumber = self.runNumber
            assert runNumber is not None, 'No run number assigned!'
        else:
            self.runNumber = runNumber
        if self.runNumber is None:
            raise AttributeError('Run number not defined. ')
        # Import the dataset
        dldPosXName = "/uncategorised/FLASH1_USER2/FLASH.FEL/HEXTOF.DAQ/DLD1:0/dset"
        dldPosYName = "/uncategorised/FLASH1_USER2/FLASH.FEL/HEXTOF.DAQ/DLD1:1/dset"
        dldTimeName = "/uncategorised/FLASH1_USER2/FLASH.FEL/HEXTOF.DAQ/DLD1:3/dset"

        dldMicrobunchIdName = "/uncategorised/FLASH1_USER2/FLASH.FEL/HEXTOF.DAQ/DLD1:2/dset"
        dldAuxName = "/uncategorised/FLASH1_USER2/FLASH.FEL/HEXTOF.DAQ/DLD1:4/dset"
        # delayStageName = "/Experiment/Pump probe laser/laser delay"
        # ENC.DELAY seems to be the wrong channel! Values appear in groups of exactly the same value
        # delayStageName = "/Experiment/Pump probe laser/delay line IK220.0/ENC.DELAY"
        # Proper channel is column with index 1 of ENC
        delayStageName = "/Experiment/Pump probe laser/delay line IK220.0/ENC"

        bamName = '/Electron Diagnostic/BAM/4DBC3/electron bunch arrival time (low charge)'
        bunchChargeName = '/Electron Diagnostic/Bunch charge/after undulator'
        macroBunchPulseIdName = '/Timing/Bunch train info/index 1.sts'
        opticalDiodeName = '/Experiment/PG/SIS8300 100MHz ADC/CH9/pulse energy/TD'
        gmdTunnelName = '/Photon Diagnostic/GMD/Pulse resolved energy/energy tunnel'
        gmdBdaName = '/Photon Diagnostic/GMD/Pulse resolved energy/energy BDA'

        # adc1Name = '/Experiment/PG/SIS8300 100MHz ADC/CH6/TD'
        # adc2Name = '/Experiment/PG/SIS8300 100MHz ADC/CH7/TD'

        daqAccess = BeamtimeDaqAccess.create(path)

        print('reading DAQ data')
        # ~ print("reading dldPosX")
        self.dldPosX, otherStuff = daqAccess.allValuesOfRun(dldPosXName, runNumber)
        print('run contains macrobunchID from {0:,} to {1:,} \n-> {2:,} total macrobunches'.format(otherStuff[0],
                                                                                                   otherStuff[1],
                                                                                                   otherStuff[1] -
                                                                                                   otherStuff[0]))
        # ~ print("reading dldPosY")
        self.dldPosY, otherStuff = daqAccess.allValuesOfRun(dldPosYName, runNumber)
        # ~ print("reading dldTime")
        self.dldTime, otherStuff = daqAccess.allValuesOfRun(dldTimeName, runNumber)
        # ~ print("reading dldMicrobunchId")
        self.dldMicrobunchId, otherStuff = daqAccess.allValuesOfRun(dldMicrobunchIdName, runNumber)
        # ~ print("reading dldAux")
        self.dldAux, otherStuff = daqAccess.allValuesOfRun(dldAuxName, runNumber)

        # ~ print("reading delayStage")
        self.delayStage, otherStuff = daqAccess.allValuesOfRun(delayStageName, runNumber)
        self.delayStage = self.delayStage[:, 1]

        # ~ print("reading BAM")
        self.bam, otherStuff = daqAccess.allValuesOfRun(bamName, runNumber)
        self.opticalDiode, otherStuff = daqAccess.allValuesOfRun(opticalDiodeName, runNumber)
        # ~ print("reading bunchCharge")
        self.bunchCharge, otherStuff = daqAccess.allValuesOfRun(bunchChargeName, runNumber)
        self.macroBunchPulseId, otherStuff = daqAccess.allValuesOfRun(macroBunchPulseIdName, runNumber)
        self.macroBunchPulseId -= otherStuff[0]
        self.gmdTunnel, otherStuff = daqAccess.allValuesOfRun(gmdTunnelName, runNumber)
        self.gmdBda, otherStuff = daqAccess.allValuesOfRun(gmdBdaName, runNumber)
        electronsToCount = self.dldPosX.copy().flatten()
        electronsToCount = numpy.nan_to_num(electronsToCount)
        electronsToCount = electronsToCount[electronsToCount > 0]
        electronsToCount = electronsToCount[electronsToCount < 10000]
        numOfElectrons = len(electronsToCount)
        print("Number of electrons: {0:,} ".format(numOfElectrons))
        print("Creating data frame: Please wait...")
        self.createDataframePerElectron()
        self.createDataframePerMicrobunch()
        print('dataframe created')

    def readInterval(self, pulseIdInterval, path=None):
        """Access to data by macrobunch pulseID intervall.

        Usefull for scans that would otherwise hit the machine's memory limit.

        Parameters:
            pulseIdInterval ():
            path (str): path to location where raw HDF5 files are stored
        """
        # allow for using the default path, which can be redefined as class variable. leaving retrocompatibility
        print('WARNING: readInterval method is obsolete. Please use readData(pulseIdInterval=xxx).')

        if path is None:
            path = self.DATA_RAW_DIR

        self.pulseIdInterval = pulseIdInterval
        # Import the dataset
        dldPosXName = "/uncategorised/FLASH1_USER2/FLASH.FEL/HEXTOF.DAQ/DLD1:0/dset"
        dldPosYName = "/uncategorised/FLASH1_USER2/FLASH.FEL/HEXTOF.DAQ/DLD1:1/dset"
        dldTimeName = "/uncategorised/FLASH1_USER2/FLASH.FEL/HEXTOF.DAQ/DLD1:3/dset"

        dldMicrobunchIdName = "/uncategorised/FLASH1_USER2/FLASH.FEL/HEXTOF.DAQ/DLD1:2/dset"
        dldAuxName = "/uncategorised/FLASH1_USER2/FLASH.FEL/HEXTOF.DAQ/DLD1:4/dset"
        # delayStageName = "/Experiment/Pump probe laser/laser delay"
        # ENC.DELAY seems to be the wrong channel! Values appear in groups of ~10 identical values
        # -> ENC.DELAY is read out with 1 Hz
        # delayStageName = "/Experiment/Pump probe laser/delay line IK220.0/ENC.DELAY"
        # Proper channel is culumn with index 1 of ENC
        delayStageName = "/Experiment/Pump probe laser/delay line IK220.0/ENC"

        bamName = '/Electron Diagnostic/BAM/4DBC3/electron bunch arrival time (low charge)'
        bunchChargeName = '/Electron Diagnostic/Bunch charge/after undulator'
        macroBunchPulseIdName = '/Timing/Bunch train info/index 1.sts'
        opticalDiodeName = '/Experiment/PG/SIS8300 100MHz ADC/CH9/pulse energy/TD'
        gmdTunnelName = '/Photon Diagnostic/GMD/Pulse resolved energy/energy tunnel'
        gmdBdaName = '/Photon Diagnostic/GMD/Pulse resolved energy/energy BDA'

        # adc1Name = '/Experiment/PG/SIS8300 100MHz ADC/CH6/TD'
        # adc2Name = '/Experiment/PG/SIS8300 100MHz ADC/CH7/TD'

        daqAccess = BeamtimeDaqAccess.create(path)

        print('reading DAQ data')
        # ~ print("reading dldPosX")
        self.dldPosX = daqAccess.valuesOfInterval(dldPosXName, pulseIdInterval)
        # ~ print("reading dldPosY")
        self.dldPosY = daqAccess.valuesOfInterval(dldPosYName, pulseIdInterval)
        # ~ print("reading dldTime")
        self.dldTime = daqAccess.valuesOfInterval(dldTimeName, pulseIdInterval)
        # ~ print("reading dldMicrobunchId")
        self.dldMicrobunchId = daqAccess.valuesOfInterval(dldMicrobunchIdName, pulseIdInterval)
        # ~ print("reading dldAux")
        self.dldAux = daqAccess.valuesOfInterval(dldAuxName, pulseIdInterval)

        # ~ print("reading delayStage")
        self.delayStage = daqAccess.valuesOfInterval(delayStageName, pulseIdInterval)
        self.delayStage = self.delayStage[:, 1]

        # ~ print("reading BAM")
        self.bam = daqAccess.valuesOfInterval(bamName, pulseIdInterval)
        self.opticalDiode = daqAccess.valuesOfInterval(opticalDiodeName, pulseIdInterval)
        # ~ print("reading bunchCharge")
        self.bunchCharge = daqAccess.valuesOfInterval(bunchChargeName, pulseIdInterval)
        self.macroBunchPulseId = daqAccess.valuesOfInterval(macroBunchPulseIdName, pulseIdInterval)
        # self.macroBunchPulseId -= self.macroBunchPulseId[self.macroBunchPulseId > 0].min()
        self.macroBunchPulseId -= pulseIdInterval[0]
        self.gmdTunnel = daqAccess.valuesOfInterval(gmdTunnelName, pulseIdInterval)
        self.gmdBda = daqAccess.valuesOfInterval(gmdBdaName, pulseIdInterval)
        electronsToCount = self.dldPosX.copy().flatten()
        electronsToCount = numpy.nan_to_num(electronsToCount)
        electronsToCount = electronsToCount[electronsToCount > 0]
        electronsToCount = electronsToCount[electronsToCount < 10000]
        numOfElectrons = len(electronsToCount)
        print("Number of electrons: {0:,} ".format(numOfElectrons))
        print("Creating data frame: Please wait...")
        self.createDataframePerElectron()
        self.createDataframePerMicrobunch()
        print('dataframe created')


if __name__ == '__main__':
    main()
