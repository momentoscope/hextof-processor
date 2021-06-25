# -*- coding: utf-8 -*-

import os
from datetime import datetime,timedelta
from configparser import ConfigParser
import dask
import dask.dataframe
import dask.multiprocessing
from dask.diagnostics import ProgressBar
import numpy as np
from numpy.lib.function_base import iterable
from processor import DldProcessor
from processor.utilities import misc
from processor.pah import BeamtimeDaqAccess
import json

_VERBOSE = False

# Try to load the Cython version of the microbunch assignment code
# If fails, load a vanilla python equivalent (Steinn Y. Agustsson)
try:
    import processor.cscripts.DldFlashProcessorCy as DldFlashProcessorCy

    if _VERBOSE:
        print('loaded cython module')
except ImportError as e:
    print('Failed loading Cython script. Using Python version instead. TODO: FIX IT!!#n Error msg: {}'.format(e))
    import processor.cscripts.DldFlashProcessorNotCy as DldFlashProcessorCy

assignToMircobunch = DldFlashProcessorCy.assignToMircobunch


class DldFlashProcessor(DldProcessor.DldProcessor):
    """  
    The class reads an existing run and allows to generated binned multidimensional arrays,
    which can be used directly or saved as HDF5 dataframes.
    
    This class reads an existing run and generates a hdf5 file containing the dask dataframes.
    It is intended to be used with data generated from August 31, 2017 to September 19, 2017.
    Version 4 enables read out of macrobunch ID. For evaluation the start ID is set to zero.
    
    **Version 5**
    
    * introduces overwriting of PAH classes for correct handling of macrobunchID
    * introduces writeRunToMultipleParquet function, for parquet file generation on machines with low ram
    * changed variables to class variables for easier implementation on different machines
    * added some print functions with information about the run that is being imported.

    Had to change the delay stage channel, as the old one (.../ENC.DELAY) stored groups of ~ 10 times the same value
    (is probably read out with 10 Hz. The new channel is the column (index!) one of .../ENC.
    This change makes the treatment of problematic runs obsolete.


    **Attributes**\n
    runNumber: int
        number of the run from which data is taken.
    pulseIdInterval: (int, int) tuple
        macrobunch ID corresponding to the interval of data read from the given run.
    dd: dask dataframe
        dataframe containing chosen channel information from the given run
    dd_microbunch: dask dataframe
        dataframe containing chosen channel information from the given run.
    """

    def __init__(self, runNumber=None, pulseIdInterval=None, settings=None):

        super().__init__(settings)

        self.runNumber = runNumber
        self.pulseIdInterval = pulseIdInterval

    def readData(self, runNumber=None, pulseIdInterval=None, path=None):
        """Read data by run number or macrobunch pulseID interval.

        Useful for scans that would otherwise hit the machine's memory limit.

        **Parameters**\n
        runNumber: int | None (default to ``self.runNumber``)
            number of the run from which to read data. If None, requires pulseIdInterval.
        pulseIdInterval: (int, int) | None (default to ``self.pulseIdInterval``)
            first and last macrobunches of selected data range. If None, the whole run
            defined by runNumber will be taken.
        path: str | None (default to ``self.DATA_RAW_DIR``)
            path to location where raw HDF5 files are stored.

        This is a union of the readRun and readInterval methods defined in previous versions.
        """

        # Update instance attributes based on input parameters
        if runNumber is None:
            runNumber = self.runNumber
        else:
            self.runNumber = runNumber

        if pulseIdInterval is None:
            pulseIdInterval = self.pulseIdInterval
        else:
            self.pulseIdInterval = pulseIdInterval

        if (pulseIdInterval is None) and (runNumber is None):
            raise ValueError('Need either runNumber or pulseIdInterval to know what data to read.')

        if path is not None:
            try:
                daqAccess = BeamtimeDaqAccess.create(path)
            except:
                self.path_to_run = misc.get_path_to_run(runNumber, path)
                daqAccess = BeamtimeDaqAccess.create(self.path_to_run)
        else:
            path = self.DATA_RAW_DIR
            self.path_to_run = misc.get_path_to_run(runNumber, path)
            daqAccess = BeamtimeDaqAccess.create(self.path_to_run)

        self.daqAddresses = []
        self.pulseIdInterval = self.getIds(runNumber, path)
        # Parse the settings file in the DAQ channels section for the list of
        # h5 addresses to read from raw and add to the dataframe.
        print('loading data...')

        for name, entry in self.settings['DAQ channels'].items():
            name = misc.camelCaseIt(name)
            val = str(entry)
            if daqAccess.isChannelAvailable(val, self.pulseIdInterval):
                self.daqAddresses.append(name)
                if _VERBOSE:
                    print('assigning address: {}: {}'.format(name.ljust(20), val))
                setattr(self, name, val)
            else:
                # if _VERBOSE:
                print('skipping address missing from data: {}: {}'.format(name.ljust(20), val))

        # TODO: get the available pulse id from PAH
        if pulseIdInterval is None:
            print('Reading DAQ data from run {}... Please wait...'.format(runNumber))

            for address_name in self.daqAddresses:
                if _VERBOSE:
                    print('reading address: {}'.format(address_name))
                try:
                    attrVal = getattr(self, address_name)
                    values, otherStuff = daqAccess.allValuesOfRun(attrVal, runNumber)
                except AssertionError:
                    print('Assertion error: {}'.format(address_name, attrVal, values, otherStuff))

                setattr(self, address_name, values)
                if address_name == 'macroBunchPulseId':  # catch the value of the first macrobunchID
                    pulseIdInterval = (otherStuff[0], otherStuff[-1])
                    self.pulseIdInterval = pulseIdInterval
                    macroBunchPulseId_correction = pulseIdInterval[0]

                if address_name == 'timeStamp':  # catch the time stamps
                    startEndTime = (values[0, 0], values[-1, 0])
                    self.startEndTime = startEndTime

            numOfMacrobunches = pulseIdInterval[1] - pulseIdInterval[0]



        else:
            print('reading DAQ data from interval {}'.format(pulseIdInterval))
            self.pulseIdInterval = pulseIdInterval
            for address_name in self.daqAddresses:
                if _VERBOSE:
                    print('reading address: {}'.format(address_name))
                values = daqAccess.valuesOfInterval(getattr(self, address_name), pulseIdInterval)
                setattr(self, address_name, values)
                if address_name == 'timeStamp':  # catch the time stamps
                    startEndTime = (values[0, 0], values[-1, 0])
                    self.startEndTime = startEndTime
            numOfMacrobunches = pulseIdInterval[1] - pulseIdInterval[0]
            macroBunchPulseId_correction = pulseIdInterval[0]

        # necessary corrections for specific channels:
        try:
            self.delayStage = self.delayStage[:, 1]
        except:
            try:
                self.delayStage = self.delayStage[:, 0]
                print('1030nm Laser')
            except:
                print('no delay stage')
        if self.CORRECT_MB_ID:
            self.macroBunchPulseId -= macroBunchPulseId_correction
        self.dldMicrobunchId -= self.UBID_OFFSET

        if _VERBOSE:
            print('Counting electrons...')

        electronsToCount = self.dldPosX.copy().flatten()
        electronsToCount = np.nan_to_num(electronsToCount)
        electronsToCount = electronsToCount[electronsToCount > 0]
        electronsToCount = electronsToCount[electronsToCount < 10000]
        self.numOfElectrons = len(electronsToCount)
        self.electronsPerMacrobunch = int(self.numOfElectrons / numOfMacrobunches)

        self.runInfo = {
            'runNumber': self.runNumber,
            'pulseIdInterval': self.pulseIdInterval,
            'numberOfMacrobunches': numOfMacrobunches,
            'numberOfElectrons': self.numOfElectrons,
            'electronsPerMacrobunch': self.electronsPerMacrobunch,
        }
        try:
            self.runInfo['timestampStart'] = int(self.startEndTime[0])
            self.runInfo['timestampStop'] = int(self.startEndTime[1])
            self.runInfo['timestampDuration'] = int(self.startEndTime[1] - self.startEndTime[0])
            self.runInfo['timeStart'] = datetime.utcfromtimestamp(self.startEndTime[0]).strftime('%Y-%m-%d %H:%M:%S')
            self.runInfo['timeStop'] = datetime.utcfromtimestamp(self.startEndTime[1]).strftime('%Y-%m-%d %H:%M:%S')
            self.runInfo['timeDuration'] = str(timedelta(seconds=int(self.startEndTime[1] - self.startEndTime[0])))
        except:
            self.runInfo['timestampStart'] = None
            self.runInfo['timestampStop'] = None
            self.runInfo['timestampDuration'] = None
            self.runInfo['timeStart'] = None
            self.runInfo['timeStop'] = None
            self.runInfo['timeDuration'] = None

        self.printRunOverview()

        # Old Print style
        # print('Run {0} contains {1:,} Macrobunches, from {2:,} to {3:,}' \
        #       .format(runNumber, numOfMacrobunches, pulseIdInterval[0], pulseIdInterval[1]))
        # try:
        #     print("start time: {}, end time: {}, total time: {}"
        #           .format(datetime.utcfromtimestamp(startEndTime[0]).strftime('%Y-%m-%d %H:%M:%S'),
        #                   datetime.utcfromtimestamp(startEndTime[1]).strftime('%Y-%m-%d %H:%M:%S'),
        #                   datetime.utcfromtimestamp(startEndTime[1] - startEndTime[0]).strftime('%H:%M:%S')))
        # except:
        #     pass
        #
        # print("Number of electrons: {0:,}; {1:,} e/Mb ".format(self.numOfElectrons, self.electronsPerMacrobunch))
        if not bool(self.metadata):
            self.metadata = self.update_metadata()

        print("Creating dataframes... Please wait...")
        with ProgressBar():
            self.createDataframePerElectron()
            print('Electron dataframe created.')
            self.createDataframePerMicrobunch()
            print('Microbunch dataframe created.')
            print('Reading Complete.')

    def readData_old(self, runNumber=None, pulseIdInterval=None, path=None):
        """Read data by run number or macrobunch pulseID interval.

        Useful for scans that would otherwise hit the machine's memory limit.

        **Parameters**\n
        runNumber: int | None (default to ``self.runNumber``)
            number of the run from which to read data. If None, requires pulseIdInterval.
        pulseIdInterval: (int, int) | None (default to ``self.pulseIdInterval``)
            first and last macrobunches of selected data range. If None, the whole run
            defined by runNumber will be taken.
        path: str | None (default to ``self.DATA_RAW_DIR``)
            path to location where raw HDF5 files are stored.

        This is a union of the readRun and readInterval methods defined in previous versions.
        """

        # Update instance attributes based on input parameters
        if runNumber is None:
            runNumber = self.runNumber
        else:
            self.runNumber = runNumber

        if pulseIdInterval is None:
            pulseIdInterval = self.pulseIdInterval
        else:
            self.pulseIdInterval = pulseIdInterval

        if (pulseIdInterval is None) and (runNumber is None):
            raise ValueError('Need either runNumber or pulseIdInterval to know what data to read.')

        print('searching for data...')
        if path is not None:
            try:
                daqAccess = BeamtimeDaqAccess.create(path)
            except:
                self.path_to_run = misc.get_path_to_run(runNumber, path)
                daqAccess = BeamtimeDaqAccess.create(self.path_to_run)
        else:
            path = self.DATA_RAW_DIR
            self.path_to_run = misc.get_path_to_run(runNumber, path)
            daqAccess = BeamtimeDaqAccess.create(self.path_to_run)

        self.daqAddresses = []
        # Parse the settings file in the DAQ channels section for the list of
        # h5 addresses to read from raw and add to the dataframe.
        for name, entry in self.settings['DAQ channels'].items():
            name = misc.camelCaseIt(name)
            val = str(entry)
            if daqAccess.isChannelAvailable(val, self.getIds(runNumber, path)):
                self.daqAddresses.append(name)
                if _VERBOSE:
                    print('assigning address: {}: {}'.format(name.ljust(20), val))
                setattr(self, name, val)
            else:
                # if _VERBOSE:
                print('skipping address missing from data: {}: {}'.format(name.ljust(20), val))

        # TODO: get the available pulse id from PAH
        if pulseIdInterval is None:
            print('Reading DAQ data from run {}... Please wait...'.format(runNumber))

            for address_name in self.daqAddresses:
                if _VERBOSE:
                    print('reading address: {}'.format(address_name))
                try:
                    attrVal = getattr(self, address_name)
                    values, otherStuff = daqAccess.allValuesOfRun(attrVal, runNumber)
                except AssertionError:
                    print('Assertion error: {}'.format(address_name, attrVal, values, otherStuff))

                setattr(self, address_name, values)
                if address_name == 'macroBunchPulseId':  # catch the value of the first macrobunchID
                    pulseIdInterval = (otherStuff[0], otherStuff[-1])
                    self.pulseIdInterval = pulseIdInterval
                    macroBunchPulseId_correction = pulseIdInterval[0]

                if address_name == 'timeStamp':  # catch the time stamps
                    startEndTime = (values[0, 0], values[-1, 0])
                    self.startEndTime = startEndTime

            numOfMacrobunches = pulseIdInterval[1] - pulseIdInterval[0]
            print('Run {0} contains {1:,} Macrobunches, from {2:,} to {3:,}' \
                  .format(runNumber, numOfMacrobunches, pulseIdInterval[0], pulseIdInterval[1]))
            try:
                print("start time: {}, end time: {}, total time: {}"
                      .format(datetime.utcfromtimestamp(startEndTime[0]).strftime('%Y-%m-%d %H:%M:%S'),
                              datetime.utcfromtimestamp(startEndTime[1]).strftime('%Y-%m-%d %H:%M:%S'),
                              datetime.utcfromtimestamp(startEndTime[1] - startEndTime[0]).strftime('%H:%M:%S')))
            except:
                pass
        else:
            print('reading DAQ data from interval {}'.format(pulseIdInterval))
            self.pulseIdInterval = pulseIdInterval
            for address_name in self.daqAddresses:
                if _VERBOSE:
                    print('reading address: {}'.format(address_name))
                setattr(self, address_name, daqAccess.valuesOfInterval(getattr(self, address_name), pulseIdInterval))
            numOfMacrobunches = pulseIdInterval[1] - pulseIdInterval[0]
            macroBunchPulseId_correction = pulseIdInterval[0]

        # necessary corrections for specific channels:
        self.delayStage = self.delayStage[:, 1]
        self.macroBunchPulseId -= macroBunchPulseId_correction
        self.dldMicrobunchId -= self.UBID_OFFSET

        if _VERBOSE:
            print('Counting electrons...')

        electronsToCount = self.dldPosX.copy().flatten()
        electronsToCount = np.nan_to_num(electronsToCount)
        electronsToCount = electronsToCount[electronsToCount > 0]
        electronsToCount = electronsToCount[electronsToCount < 10000]
        self.numOfElectrons = len(electronsToCount)
        self.electronsPerMacrobunch = int(self.numOfElectrons / numOfMacrobunches)
        print("Number of electrons: {0:,}; {1:,} e/Mb ".format(self.numOfElectrons, self.electronsPerMacrobunch))

        print("Creating dataframes... Please wait...")
        pbar = ProgressBar()
        with pbar:
            self.createDataframePerElectron()
            print('Electron dataframe created.')
            self.createDataframePerMicrobunch()
            print('Microbunch dataframe created.')

    def createDataframePerElectronRange(self, mbIndexStart, mbIndexEnd):
        """ Create a numpy array indexed by photoelectron events for a given range,
        [start, end), of electron macrobunch IDs.
        
        **Parameters**\n
        mbIndexStart: int
            The starting (inclusive) macrobunch ID.
        mbIndexEnd: int
            The ending (non-inclusive) macrobunch ID.
        
        **Return**\n
        da: numpy array
            Indexed photoelectron events.
        """
        # the chunk size here is too large in order to do the chunking by the loop around it.

        # Here all the columns to be stored in the dd dataframe are created from the raw h5 file
        # Each columns requires an ad hoc treatment, so they all need to be done individually
        arrayCols = []  # TODO: find less ad hoc solution
        colNames = []

        if 'dldPosX' in self.daqAddresses:
            daX = self.dldPosX[mbIndexStart:mbIndexEnd, :].flatten()
            arrayCols.append(daX)
            colNames.append('dldPosX')

        if 'dldPosY' in self.daqAddresses:
            daY = self.dldPosY[mbIndexStart:mbIndexEnd, :].flatten()
            arrayCols.append(daY)
            colNames.append('dldPosY')

        if 'dldTime' in self.daqAddresses:
            daTime = self.dldTime[mbIndexStart:mbIndexEnd, :].flatten()
            arrayCols.append(daTime)
            colNames.append('dldTime')

        if 'dldAux0' in self.daqAddresses:
            dldAuxChannels = {'sampleBias': 0,
                              'tofVoltage': 1,
                              'extractorVoltage': 2,
                              'extractorCurrent': 3,
                              'cryoTemperature': 4,
                              'sampleTemperature': 5,
                              'dldTimeBinSize': 15,
                              }

            for name, chan in dldAuxChannels.items():
                da = np.zeros_like(self.dldMicrobunchId[mbIndexStart:mbIndexEnd, :])
                da[:, :] = (self.dldAux0[mbIndexStart:mbIndexEnd, chan])[:, None]
                da = da.flatten()
                arrayCols.append(da)
                colNames.append(name)
            # daSampleBias = np.zeros_like(self.dldMicrobunchId[mbIndexStart:mbIndexEnd, :])
            # daSampleBias[:, :] = (self.dldAux0[mbIndexStart:mbIndexEnd, 0])[:, None]
            # daSampleBias = daSampleBias.flatten()
            # arrayCols.append(daSampleBias)
            # colNames.append('sampleBias')
            #
            # daTofVoltage = np.zeros_like(self.dldMicrobunchId[mbIndexStart:mbIndexEnd, :])
            # daTofVoltage[:, :] = (self.dldAux0[mbIndexStart:mbIndexEnd, 1])[:, None]
            # daTofVoltage = daTofVoltage.flatten()
            # arrayCols.append(daTofVoltage)
            # colNames.append('tofVoltage')
            #
            # daExtractorVoltage = np.zeros_like(self.dldMicrobunchId[mbIndexStart:mbIndexEnd, :])
            # daExtractorVoltage[:, :] = (self.dldAux0[mbIndexStart:mbIndexEnd, 2])[:, None]
            # daExtractorVoltage = daExtractorVoltage.flatten()
            # arrayCols.append(daExtractorVoltage)
            # colNames.append('extractorVoltage')

        if 'delayStage' in self.daqAddresses:
            delayStageArray = np.zeros_like(self.dldMicrobunchId[mbIndexStart:mbIndexEnd, :])
            delayStageArray[:, :] = (self.delayStage[mbIndexStart:mbIndexEnd])[:, None]
            daDelaystage = delayStageArray.flatten()
            arrayCols.append(daDelaystage)
            colNames.append('delayStage')

        if 'streakCam' in self.daqAddresses:
            streakCamArray = np.zeros_like(self.dldMicrobunchId[mbIndexStart:mbIndexEnd, :])
            streakCamArray[:, :] = (self.streakCam[mbIndexStart:mbIndexEnd, 0])[:, None]
            daStreakCam = streakCamArray.flatten()
            arrayCols.append(daStreakCam)
            colNames.append('streakCamera')

        if 'bam' in self.daqAddresses:
            bamArray = assignToMircobunch(
                self.dldMicrobunchId[mbIndexStart:mbIndexEnd, :].astype(np.float64),
                self.bam[mbIndexStart:mbIndexEnd, :].astype(np.float64))
            daBam = bamArray.flatten()
            arrayCols.append(daBam)
            colNames.append('bam')

        if 'dldMicrobunchId' in self.daqAddresses:
            daMicrobunchId = self.dldMicrobunchId[mbIndexStart:mbIndexEnd, :].flatten()
            arrayCols.append(daMicrobunchId)
            colNames.append('dldMicrobunchId')

        if 'dldDetectorId' in self.daqAddresses:
            dldDetectorId = (self.dldDetectorId[mbIndexStart:mbIndexEnd, :].copy()).astype(int) % 2
            daDetectorId = dldDetectorId.flatten()
            arrayCols.append(daDetectorId)
            colNames.append('dldDetectorId')

        if 'dldSectorId' in self.daqAddresses:
            dldSectorId = (self.dldSectorId[mbIndexStart:mbIndexEnd, :].copy()).astype(int) % np.power(2,self.DLD_ID_BITS)
            daSectorId = dldSectorId.flatten()
            arrayCols.append(daSectorId)
            colNames.append('dldSectorId')

        if 'bunchCharge' in self.daqAddresses:
            bunchChargeArray = assignToMircobunch(
                self.dldMicrobunchId[mbIndexStart:mbIndexEnd, :].astype(np.float64),
                self.bunchCharge[mbIndexStart:mbIndexEnd, :].astype(np.float64))
            daBunchCharge = bunchChargeArray.flatten()
            arrayCols.append(daBunchCharge)
            colNames.append('bunchCharge')

        if 'opticalDiode' in self.daqAddresses:
            opticalDiodeArray = assignToMircobunch(
                self.dldMicrobunchId[mbIndexStart:mbIndexEnd, :].astype(np.float64),
                self.opticalDiode[mbIndexStart:mbIndexEnd, :].astype(np.float64))
            daOpticalDiode = opticalDiodeArray.flatten()
            arrayCols.append(daOpticalDiode)
            colNames.append('opticalDiode')

        if 'gmdTunnel' in self.daqAddresses:
            gmdTunnelArray = assignToMircobunch(
                self.dldMicrobunchId[mbIndexStart:mbIndexEnd, :].astype(np.float64),
                self.gmdTunnel[mbIndexStart:mbIndexEnd, :].astype(np.float64))
            daGmdTunnel = gmdTunnelArray.flatten()
            arrayCols.append(daGmdTunnel)
            colNames.append('gmdTunnel')

        if 'gmdBda' in self.daqAddresses:
            gmdBdaArray = assignToMircobunch(
                self.dldMicrobunchId[mbIndexStart:mbIndexEnd, :].astype(np.float64),
                self.gmdBda[mbIndexStart:mbIndexEnd, :].astype(np.float64))
            daGmdBda = gmdBdaArray.flatten()
            arrayCols.append(daGmdBda)
            colNames.append('gmdBda')

        if 'monochromatorActEnergy' in self.daqAddresses:
            monochromatorChannels = {'delta1': 0,
                              'delta2': 1,
                              'mirrorAngle': 2,
                              'gratingAngle': 3,
                              }

            alpha = 2 * self.monochromatorActEnergy[mbIndexStart:mbIndexEnd,monochromatorChannels['delta1']] + 90 -\
                    self.monochromatorActEnergy[mbIndexStart:mbIndexEnd,monochromatorChannels['delta2']]
            beta = -1 * self.monochromatorActEnergy[mbIndexStart:mbIndexEnd,monochromatorChannels['delta2']] - 86
            GratingDensity = 200
            DiffrOrder = 1

            da = np.zeros_like(self.dldMicrobunchId[mbIndexStart:mbIndexEnd, :])
            da[:, :] = np.array(1239.84/ ((np.sin(beta / 180 * np.pi)+np.sin(alpha / 180 * np.pi)) * 1e9 / (DiffrOrder * GratingDensity * 1000)))[:,None]
            # for name, chan in monochromatorChannels.items():
            da = da.flatten()

            arrayCols.append(da)
            colNames.append('monochromatorActEnergy')



        if 'monochromatorPhotonEnergy' in self.daqAddresses:
            monochromatorPhotonEnergyArray = assignToMircobunch(
                self.dldMicrobunchId[mbIndexStart:mbIndexEnd, :].astype(np.float64),
                self.monochromatorPhotonEnergy[mbIndexStart:mbIndexEnd, :].astype(np.float64))
            daMonochromatorPhotonEnergy = monochromatorPhotonEnergyArray.flatten()
            # daMonochromatorPhotonEnergy = np.zeros_like(self.dldMicrobunchId[mbIndexStart:mbIndexEnd, :])
            # daMonochromatorPhotonEnergy[:, :] = (self.monochromatorPhotonEnergy[mbIndexStart:mbIndexEnd])[:, None]
            # daMonochromatorPhotonEnergy = daMonochromatorPhotonEnergy.flatten()
            # handle nans # TODO: This channel should become a static value
            nan = np.float64(np.nanmean(self.monochromatorPhotonEnergy))
            daMonochromatorPhotonEnergy = np.nan_to_num(daMonochromatorPhotonEnergy,nan=nan)
            arrayCols.append(daMonochromatorPhotonEnergy)
            colNames.append('monochromatorPhotonEnergy')

        if 'i0Monitor' in self.daqAddresses:
            def I0BunchTrain2Pulses():
                """
                Cut, reshape and average the ADC signal of the I0 monitor. 
                Preliminary procedure: migth be optimized and tunend in to the DAQ 
                """
                i0Cutted = np.array(
                    np.split(-self.i0Monitor[:, self.I0ID_OFFSET:self.I0ID_OFFSET + 108 * self.I0ID_N], self.I0ID_N,
                             axis=1))
                i0BG = i0Cutted[:, :, self.I0_MEAN_LOW:self.I0_MEAN_HIGH].mean(2)
                return np.nansum(i0Cutted[:, :, self.I0_SUM_LOW:self.I0_SUM_HIGH] - i0BG[:, :, None], 2).T

            i0Data = I0BunchTrain2Pulses()

            i0Array = assignToMircobunch(
                self.dldMicrobunchId[mbIndexStart:mbIndexEnd, :].astype(np.float64),
                i0Data[mbIndexStart:mbIndexEnd, :].astype(np.float64))
            daI0 = i0Array.flatten()
            arrayCols.append(daI0)
            colNames.append('i0Monitor')

        # convert the laser polarization motor position to the electron format
        if 'pumpPol' in self.daqAddresses:
            pumpPolArray = np.zeros_like(self.dldMicrobunchId[mbIndexStart:mbIndexEnd, :])
            pumpPolArray[:, :] = (self.pumpPol[mbIndexStart:mbIndexEnd, 0])[:, None]
            daPumpPol = pumpPolArray.flatten()
            arrayCols.append(daPumpPol)
            colNames.append('pumpPol')

        # convert the MacroBunchPulseId to the electron format. No check because this surely exists
        if 'macroBunchPulseId' in self.daqAddresses:
            macroBunchPulseIdArray = np.zeros_like(self.dldMicrobunchId[mbIndexStart:mbIndexEnd, :])
            macroBunchPulseIdArray[:, :] = (self.macroBunchPulseId[mbIndexStart:mbIndexEnd, 0])[:, None]
            daMacroBunchPulseId = macroBunchPulseIdArray.flatten()
            arrayCols.append(daMacroBunchPulseId)
            colNames.append('macroBunchPulseId')

        # convert the timeStamp to the electron format. No check because this surely exists
        if 'timeStamp' in self.daqAddresses:
            timeStampArray = np.zeros_like(self.dldMicrobunchId[mbIndexStart:mbIndexEnd, :])
            timeStampArray[:, :] = (self.timeStamp[mbIndexStart:mbIndexEnd, 0])[:, None]
            daTimeStamp = timeStampArray.flatten()
            arrayCols.append(daTimeStamp)
            colNames.append('timeStamp')

        # the Aux channel: aux0:
        # aux0Arr= assignToMircobunch(self.dldMicrobunchId[mbIndexStart:mbIndexEnd, :].astype(np.float64), self.dldAux[mbIndexStart:mbIndexEnd, 0].astype(np.float64))
        # daAux0 = dask.array.from_array(aux0Arr.flatten(), chunks=(chunks))

        # the Aux channel: aux1:
        # aux1Arr= assignToMircobunch(self.dldMicrobunchId[mbIndexStart:mbIndexEnd, :].astype(np.float64), self.dldAux[mbIndexStart:mbIndexEnd, 1].astype(np.float64))
        # daAux1 = dask.array.from_array(aux0Arr.flatten(), chunks=(chunks))

        # added macroBunchPulseId at last position
        # da = dask.array.stack([daX, daY, daTime, daDelaystage, daBam, daMicrobunchId,
        #                       daDetectorId, daSectorId, daBunchCharge, daOpticalDiode,
        #                       daGmdTunnel, daMacroBunchPulseId])
        da = np.stack(arrayCols)
        if len(self.ddColNames) != len(colNames):
            self.ddColNames = colNames
        return da

    def createDataframePerElectron(self):
        """ Create a dataframe indexed by photoelectron events from the read arrays
        (either from the test file or the run number). The method needs no input parameters.
        """

        # self.dldTime=self.dldTime*self.dldTimeStep
        if _VERBOSE:
            print('creating electron dataframe...')

        maxIndex = self.dldTime.shape[0]

        if self.SINGLE_CORE_DATAFRAME_CREATION:
            n_cores = 1  # creating dataframes with multiple cores takes much longer...
        else:
            n_cores = self.N_CORES

        chunkSize = min(self.CHUNK_SIZE, maxIndex / n_cores)  # ensure minimum one chunk per core.
        numOfPartitions = int(maxIndex / chunkSize) + 1
        daList = []
        self.ddColNames = []
        for i in range(0, numOfPartitions):
            indexFrom = int(i * chunkSize)
            indexTo = int(min(indexFrom + chunkSize, maxIndex))
            result = dask.delayed(self.createDataframePerElectronRange)(indexFrom, indexTo)
            daList.append(result)
        # self.dd = self.createDataframePerElectronRange(0, maxIndex)

        # Create the electron-indexed dataframe
        self.daListResult = dask.compute(*daList)

        a = np.concatenate(self.daListResult, axis=1)
        da = dask.array.from_array(a.T, chunks=self.CHUNK_SIZE)

        # cols = ('dldPosX', 'dldPosY', 'dldTime', 'delayStage', 'bam', 'dldMicrobunchId', 'dldDetectorId', 'dldSectorId', 'bunchCharge',
        #         'opticalDiode', 'gmdTunnel', 'gmdBda', 'i0Monitor', 'pumpPol', 'timeStamp', 'macroBunchPulseId')
        #
        # cols = tuple(x for x in cols if x in self.daqAddresses)

        cols = self.ddColNames

        self.dd = dask.dataframe.from_array(da, columns=cols)
        # needed as negative values are used to mark bad data
        self.dd = self.dd[self.dd['dldMicrobunchId'] > -1]
        # I propose leaving it like this, since energy calibration depends on microscope parameters and photon energy;
        # CHANGED: default is as before, but if attribute TOF_IN_NS is set to true, it leaves the delay in steps.
        # Changed again. there is aliasing if binning in ns, physical binning needs to happen in tof_steps
        # if self.TOF_IN_NS:
        #     self.dd['dldTime'] = self.dd['dldTime'] * self.TOF_STEP_TO_NS

    def createDataframePerMicrobunch(self):
        """ Create a dataframe indexed by the microbunch ID. The method needs no input parameters.
        """

        if _VERBOSE:
            print('creating microbunch dataframe...')

        arrayCols = []
        ddMicrobunchesColnames = []
        numOfMicrobunches = self.bam.shape[1]
        lengthToPad = numOfMicrobunches - self.opticalDiode.shape[1]

        if 'delayStage' in self.daqAddresses:
            delayStageArray = np.zeros_like(self.bam)
            delayStageArray[:, :] = (self.delayStage[:])[:, None]
            daDelayStage = dask.array.from_array(delayStageArray.flatten(), chunks=self.CHUNK_SIZE)
            arrayCols.append(daDelayStage)
            ddMicrobunchesColnames.append('delayStage')

        if 'streakCam' in self.daqAddresses:
            streakCamArray = np.zeros_like(self.bam)
            streakCamArray[:, :] = (self.streakCam[:, 0])[:, None]
            daStreakCamArray = dask.array.from_array(streakCamArray.flatten(), chunks=self.CHUNK_SIZE)
            arrayCols.append(daStreakCamArray)
            ddMicrobunchesColnames.append('streakCamera')

        if 'bam' in self.daqAddresses:
            daBam = dask.array.from_array(self.bam.flatten(), chunks=(self.CHUNK_SIZE))
            arrayCols.append(daBam)
            ddMicrobunchesColnames.append('bam')

        # if 'dldAux0' in self.daqAddresses:
        #     dldAux0 = self.dldAux0[:, 0]
        #     aux0 = np.ones(self.bam.shape) * dldAux0[:, None]
        #     daAux0 = dask.array.from_array(aux0.flatten(), chunks=(self.CHUNK_SIZE))
        #     arrayCols.append(daAux0)
        #     ddMicrobunchesColnames.append('delayStage')
        #
        # if 'dldAux1' in self.daqAddresses:
        #     dldAux1 = self.dldAux1[:, 1]
        #     aux1 = np.ones(self.bam.shape) * dldAux1[:, None]
        #     daAux1 = dask.array.from_array(aux1.flatten(), chunks=(self.CHUNK_SIZE))
        #     arrayCols.append(daAux1)
        #     ddMicrobunchesColnames.append('delayStage')

        if 'bunchCharge' in self.daqAddresses:
            daBunchCharge = dask.array.from_array(self.bunchCharge[:, 0:numOfMicrobunches].flatten(),
                                                  chunks=(self.CHUNK_SIZE))
            arrayCols.append(daBunchCharge)
            ddMicrobunchesColnames.append('bunchCharge')

        if 'opticalDiode' in self.daqAddresses:
            try:
                paddedOpticalDiode = np.pad(self.opticalDiode, ((0, 0), (0, lengthToPad)), 'constant',
                                            constant_values=(0, 0))
                daOpticalDiode = dask.array.from_array(paddedOpticalDiode.flatten(), chunks=self.CHUNK_SIZE)
            except:
                print('fix optical diode DAQ: Length: ' + str(self.opticalDiode.shape[1]))
                daOpticalDiode = dask.array.from_array(self.opticalDiode[:, 0:numOfMicrobunches].flatten(),
                                                       chunks=self.CHUNK_SIZE)
            arrayCols.append(daOpticalDiode)
            ddMicrobunchesColnames.append('opticalDiode')

        if 'i0Monitor' in self.daqAddresses:
            def I0BunchTrain2Pulses():
                """
                Cut, reshape and average the ADC signal of the I0 monitor. 
                Preliminary procedure: migth be optimized and tunend in to the DAQ 
                """
                i0Cutted = np.array(np.split(-self.i0Monitor[:, 967:54967], 500, axis=1))
                i0BG = i0Cutted[:, :, :39].mean(2)
                return np.nansum(i0Cutted[:, :, 39:90] - i0BG[:, :, None], 2).T

            i0Data = I0BunchTrain2Pulses()
            try:
                paddedI0 = np.pad(i0Data, ((0, 0), (0, numOfMicrobunches - i0Data.shape[1])), 'constant',
                                  constant_values=(0, 0))
                daI0 = dask.array.from_array(paddedI0.flatten(), chunks=self.CHUNK_SIZE)
            except:
                print('fix i0 Monitor DAQ: Length: ' + str(i0Data.shape[1]))
                daI0 = dask.array.from_array(i0Data[:, 0:numOfMicrobunches].flatten(),
                                             chunks=self.CHUNK_SIZE)
            arrayCols.append(daI0)
            ddMicrobunchesColnames.append('i0Monitor')

        if 'pumpPol' in self.daqAddresses:
            pumpPolArray = np.zeros_like(self.bam)
            pumpPolArray[:] = (self.pumpPol[:, 0])[:, None]
            daPumpPol = dask.array.from_array(pumpPolArray.flatten(), chunks=self.CHUNK_SIZE)
            arrayCols.append(daPumpPol)
            ddMicrobunchesColnames.append('pumpPol')

        if 'macroBunchPulseId' in self.daqAddresses:
            macroBunchPulseIdArray = np.zeros_like(self.bam)
            macroBunchPulseIdArray[:, :] = (self.macroBunchPulseId[:, 0])[:, None]
            daMacroBunchPulseId = dask.array.from_array(macroBunchPulseIdArray.flatten(), chunks=(self.CHUNK_SIZE))
            arrayCols.append(daMacroBunchPulseId)
            ddMicrobunchesColnames.append('macroBunchPulseId')

        if 'timeStamp' in self.daqAddresses:
            timeStampArray = np.zeros_like(self.bam)
            timeStampArray[:, :] = (self.timeStamp[:, 0])[:, None]
            daTimeStamp = dask.array.from_array(timeStampArray.flatten(), chunks=(self.CHUNK_SIZE))
            arrayCols.append(daTimeStamp)
            ddMicrobunchesColnames.append('timeStamp')

        da = dask.array.stack(arrayCols)

        # Create the microbunch-indexed dataframe
        # cols = (
        #     'delayStage', 'bam', 'dldAux0', 'dldAux1', 'bunchCharge', 'opticalDiode',  'i0Monitor', 'pumpPol', 'macroBunchPulseId', 'timeStamp')
        # cols = tuple(x for x in cols if x in self.daqAddresses)
        cols = ddMicrobunchesColnames
        self.ddMicrobunches = dask.dataframe.from_array(da.T, columns=cols)

    def storeDataframes(self, fileName=None, path=None, format='parquet', append=False,compression="UNCOMPRESSED"):
        """ Save imported dask dataframe as a parquet or hdf5 file.

        **Parameters**\n
        fileName: str | None
            The file namestring.
        path: str | None (default to ``self.DATA_PARQUET_DIR`` or ``self.DATA_H5_DIR``)
            The path to the folder to save the format-converted data.
        format: str | 'parquet'
            The output file format, possible choices are 'parquet', 'h5' or 'hdf5'.
        append: bool | False (disable data appending as default)
            When using parquet file, allows to append the data to pre-existing files.
        """

        format = format.lower()
        assert format in ['parquet', 'h5', 'hdf5'], 'Invalid format for data input. Please select between parquet or h5'

        # Update instance attributes based on input parameters
        if path is None:
            if format == 'parquet':
                path = self.DATA_PARQUET_DIR
            elif format in ['hdf5', 'h5']:
                path = self.DATA_H5_DIR
        if not os.path.isdir(path):
            raise NotADirectoryError(f'Could not find directory {path}')

        if fileName is None:
            if self.runNumber is None:
                fileName = 'mb{}to{}'.format(self.pulseIdInterval[0], self.pulseIdInterval[-1])
            else:
                fileName = 'run{}'.format(self.runNumber)

        fileName = path + fileName  # TODO: test if naming is correct

        if format == 'parquet':
            if append:
                print(f'Appending data to existing parquet container {fileName}')
            else:
                print(f'Creating parquet container {fileName}')

            with ProgressBar():
                if 'runNumber' not in self.dd.columns: # add run number as column to the dataframe
                    if self.runNumber:
                        run = self.runNumber
                    else:
                        try:
                            run = self.metadata['runInfo']['runNumber']
                            if isinstance(run,list):
                                run = None # in case this is already an agglomerate of runs... useless to add run number
                        except KeyError:
                            run = None
                    if run is not None:
                        self.dd['runNumber'] = run
                        self.ddMicrobunches['runNumber'] = run
                if 'pulseId' not in self.dd.columns: 
                    # add the pulseId (macrobunchId) number as column to the dataframe
                    # macroBunchPulseId is there already, but its reset to 0 at the firsto one...
                    if self.pulseIdInterval:
                        pulseId = self.pulseIdInterval[0]
                    else:
                        try:
                            pulseId = self.metadata['runInfo']['pulseIdInterval'][0]
                            if isinstance(pulseId,list):
                                pulseId = None # in case this is already an agglomerate of runs... useless to add run number
                        except KeyError:
                            pulseId = None
                    if pulseId is not None:
                        self.dd['pulseId'] = self.dd['macroBunchPulseId'] + pulseId
                        self.ddMicrobunches['pulseId'] = self.ddMicrobunches['macroBunchPulseId'] + pulseId

                                                
                self.dd.to_parquet(fileName + "_el", compression=compression, \
                                   append=append, ignore_divisions=True)
                self.ddMicrobunches.to_parquet(fileName + "_mb", compression=compression, \
                                               append=append, ignore_divisions=True)
            print('Saving metadata...')
            try:
                if not bool(self.metadata):
                    self.metadata = self.update_metadata()

                if not append:
                    meta = self.metadata
                else:
                    with open(os.path.join(fileName + '_el', 'run_metadata.txt'),'r') as json_file:
                        old = json.load(json_file)
                    new = self.metadata

                    if 'part_000' not in old.keys():
                        meta={'runInfo':old['runInfo']}
                        meta[f'part_000'] = old
                    else:
                        meta = old
                    
                    last_part_number = max([int(s[5:]) for s in meta.keys() if 'part_' in s])
                    meta[f"part_{last_part_number + 1:03d}"] = new

                    i = meta['runInfo']
                    n = new['runInfo']
                    for key in n.keys():
                        if key == 'runNumber':
                            if not isinstance(i[key],list):
                                i[key] = [i[key],n[key]]
                            else:
                                i[key].append(n[key])

                        elif key == 'pulseIdInterval':
                            if not isinstance(i[key][0],list):
                                i[key] = [i[key],n[key]]
                            else:
                                i[key].append(n[key])
                    
                        elif key == 'timeStart':
                                i[key] = min(datetime.strptime(i[key], '%Y-%m-%d %H:%M:%S'),datetime.strptime(n[key], '%Y-%m-%d %H:%M:%S')).__str__()
                        
                        elif key == 'timeStop':
                                i[key] = max(datetime.strptime(i[key], '%Y-%m-%d %H:%M:%S'),datetime.strptime(n[key], '%Y-%m-%d %H:%M:%S')).__str__()

                        elif key in ['timeDuration', 'electronsPerMacrobunch']:
                            pass # skip those which need recalculation based on the summed values
                        else:
                            try:
                                i[key] += n[key]
                            except TypeError as E:
                                print(E, key)
                        i['timeDuration'] = str(timedelta(seconds=i['timestampDuration']))
                        i['electronsPerMacrobunch'] = i['numberOfElectrons']/i['numberOfMacrobunches']


                with open(os.path.join(fileName + '_el', 'run_metadata.txt'), 'w') as json_file:
                    json.dump(meta, json_file, indent=4)
            except AttributeError as E:
                print(f'failed saving metadata: {E}')

        elif format in ['hdf5', 'h5']:
            if os.path.isdir(fileName):
                print(f'Appending data to existing h5 container {fileName}')
            else:
                print(f'Creating h5 container {fileName}')
            dask.dataframe.to_hdf(self.dd, fileName, '/electrons')
            dask.dataframe.to_hdf(self.ddMicrobunches, fileName, '/microbunches')
        print('saving complete!')

    def getIds(self, runNumber=None, path=None):
        """ Returns the first and the last macrobunch IDs of a given run number.

        **Parameters**\n
        runNumber: int | None (default to ``self.runNumber``)
            The run number from which to read the macrobunch ID interval.
        path: str | None (default to ``self.DATA_RAW_DIR``)
            The path to location where raw HDF5 files are stored.
        
        **Return**\n
        pulseIdInterval: (int, int)
            The macrobunch ID range for a given run number.
        """

        if runNumber is None:
            runNumber = self.runNumber
        else:
            self.runNumber = runNumber

        if path is None:
            path = self.DATA_RAW_DIR

        if not hasattr(self, 'path_to_run'):
            self.path_to_run = misc.get_path_to_run(runNumber, path)

        try:
            from camp.pah.beamtimedaqaccess import H5FileDataAccess, H5FileManager
        except:
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

        fileAccess = H5FileDataAccess(H5FileManager(self.path_to_run))
        pulseIdInterval = fileAccess.availablePulseIdInterval(runNumber)

        return pulseIdInterval

    # ==================
    # DEPRECATED METHODS
    # ==================

    def readRun(self, runNumber=None, path=None):
        """ **[DEPRECATED]** Read a run. Generates dd and dd_micrubunches attributes
        as pd.DataFrame containing data from the given run.

        **Parameters**\n
        runNumber: int | None
            number corresponding to the rung to read data from. if None, it uses the value
            defined in the runNumber attribute.
        path: str | None
            path to location where raw HDF5 files are stored. If None, it uses the value from SETTINGS.ini.

        **Raise**\n
            Throws AttributeError if the run number is not given

        :Example:
        ::
        
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
        electronsToCount = np.nan_to_num(electronsToCount)
        electronsToCount = electronsToCount[electronsToCount > 0]
        electronsToCount = electronsToCount[electronsToCount < 10000]
        numOfElectrons = len(electronsToCount)
        print("Number of electrons: {0:,} ".format(numOfElectrons))
        print("Creating data frame: Please wait...")
        self.createDataframePerElectron()
        self.createDataframePerMicrobunch()
        print('dataframe created')

    def readInterval(self, pulseIdInterval, path=None):
        """ **[DEPRECATED]** Access to data by an macrobunch ID interval.
        Useful for scans that would otherwise hit the machine's memory limit.

        **Parameters**\n
        pulseIdInterval: (int, int)
            The starting and ending macrobunch IDs, [start, end).
        path: str | None (default to ``self.DATA_RAW_DIR``)
            The path to location where raw HDF5 files are stored.
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
        electronsToCount = np.nan_to_num(electronsToCount)
        electronsToCount = electronsToCount[electronsToCount > 0]
        electronsToCount = electronsToCount[electronsToCount < 10000]
        numOfElectrons = len(electronsToCount)
        print("Number of electrons: {0:,} ".format(numOfElectrons))
        print("Creating data frame: Please wait...")
        self.createDataframePerElectron()
        self.createDataframePerMicrobunch()
        print('dataframe created')
