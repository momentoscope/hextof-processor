import os

import dask
import dask.dataframe
import dask.multiprocessing
import numpy
from processor import DldProcessor

try:
    import processor.cscripts.DldFlashProcessorCy as DldFlashProcessorCy
except ImportError:
    import processor.cscripts.DldFlashProcessorNotCy as DldFlashProcessorCy

assignToMircobunch = DldFlashProcessorCy.assignToMircobunch
# from processor.cscripts import DldFlashProcessorCy
from processor.pah import BeamtimeDaqAccess


def main():
    processor = DldFlashProcessor()
    processor.runNumber = 19059
    # processor.writeRunToMultipleParquet(processor.runNumber, single_file=True)
    processor.readRun(runNumber=processor.runNumber)
    filename = 'E:/data/FLASH/parquet/19135'

    filename = processor.DATA_PARQUET_DIR + str(processor.runNumber)
    print(filename)
    processor.storeDataframes(filename, 'parquet')
    processor.readDataframesParquet(filename)

    processor.addBinning('posX', 480, 980, 10)
    processor.addBinning('posY', 480, 980, 10)
    result = processor.computeBinnedData()
    import matplotlib.pyplot as plt
    plt.imshow(result)
    plt.show()


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
        interval (int): macrobunch ID corresponding to the interval of data
            read from the given run.
        dd (pd.DataFrame): dataframe containing chosen channel information from
            the given run
        dd_microbunch (pd.DataFrame): dataframe containing chosen channel
            information from the given run.
    """

    def __init__(self):
        super().__init__()

        self.runNumber = None
        self.interval = None

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
        self.delaystage, otherStuff = daqAccess.allValuesOfRun(delayStageName, runNumber)
        self.delaystage = self.delaystage[:, 1]

        # ~ print("reading BAM")
        self.bam, otherStuff = daqAccess.allValuesOfRun(bamName, runNumber)
        self.opticalDiode, otherStuff = daqAccess.allValuesOfRun(opticalDiodeName, runNumber)
        # ~ print("reading bunchCharge")
        self.bunchCharge, otherStuff = daqAccess.allValuesOfRun(bunchChargeName, runNumber)
        self.macroBunchPulseId, otherStuff = daqAccess.allValuesOfRun(macroBunchPulseIdName, runNumber)
        self.macroBunchPulseId -= otherStuff[0]
        self.gmdTunnel, otherStuff = daqAccess.allValuesOfRun(gmdTunnelName, runNumber)
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
        # TODO: incorporate this function in readRun.
        # allow for using the default path, which can be redefined as class variable. leaving retrocompatibility
        if path is None:
            path = self.DATA_RAW_DIR

        self.interval = pulseIdInterval
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
        self.delaystage = daqAccess.valuesOfInterval(delayStageName, pulseIdInterval)
        self.delaystage = self.delaystage[:, 1]

        # ~ print("reading BAM")
        self.bam = daqAccess.valuesOfInterval(bamName, pulseIdInterval)
        self.opticalDiode = daqAccess.valuesOfInterval(opticalDiodeName, pulseIdInterval)
        # ~ print("reading bunchCharge")
        self.bunchCharge = daqAccess.valuesOfInterval(bunchChargeName, pulseIdInterval)
        self.macroBunchPulseId = daqAccess.valuesOfInterval(macroBunchPulseIdName, pulseIdInterval)
        # self.macroBunchPulseId -= self.macroBunchPulseId[self.macroBunchPulseId > 0].min()
        self.macroBunchPulseId -= pulseIdInterval[0]
        self.gmdTunnel = daqAccess.valuesOfInterval(gmdTunnelName, pulseIdInterval)
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
        delaystageArray = numpy.zeros_like(self.dldMicrobunchId[mbIndexStart:mbIndexEnd, :])
        delaystageArray[:, :] = (self.delaystage[mbIndexStart:mbIndexEnd])[:, None]
        daDelaystage = delaystageArray.flatten()

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
                          daGmdTunnel, daMacroBunchPulseId])

        return da

    def createDataframePerElectron(self):
        """ Create a data frame from the read arrays (either from the test file or the run number)



        """

        # self.dldTime=self.dldTime*self.dldTimeStep

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
                                                         'bunchCharge', 'opticalDiode', 'gmdTunnel',
                                                         'macroBunchPulseId'))

        self.dd = self.dd[self.dd['microbunchId'] > 0]
        self.dd['dldTime'] = self.dd['dldTime'] * self.TOF_STEP_TO_NS

    def createDataframePerMicrobunch(self):

        numOfMacrobunches = self.bam.shape[0]

        # convert the delay stage position to the electron format
        delaystageArray = numpy.zeros_like(self.bam)
        delaystageArray[:, :] = (self.delaystage[:])[:, None]

        daDelaystage = dask.array.from_array(delaystageArray.flatten(), chunks=(self.CHUNK_SIZE))

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
        da = dask.array.stack([daDelaystage, daBam, daAux0, daAux1, daBunchCharge, daOpticalDiode, daMacroBunchPulseId])

        # create the data frame:
        self.ddMicrobunches = dask.dataframe.from_array(da.T,
                                                        columns=('delayStageTime', 'bam', 'aux0', 'aux1', 'bunchCharge',
                                                                 'opticalDiode', 'macroBunchPulseId'))

    def storeDataframes(self, fileName, format='parquet', append=False):
        """ Saves imported dask dataframe into a parquet or hdf5 file.

        Parameters:
            fileName (string): name (including path) of the file where to save data.
            format (string, optional): accepts: 'parquet' and 'hdf5'. Choose output file format.
                Default value makes a dask parquet file.
                append (bool): when using parquet file, allows to append the data to a preexisting file.


        """

        # todo: implement fileName checking wheather it is a path, and if not, use default data path.
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

    # ==================================================================

    def writeRunToMultipleParquet(self, runNumber=None, parquetPath=None, path=None, interval_size=None,
                                  single_file=False):
        """ Function that allows for storing parquet data from large runs on machines with limited ram memory.

        DEPRECATED - do not use.

        interval_size defines the size of each macrobunchID interval to save at a time, each in a separated parquet file.

        Data is saved in outputFolder as subfolders with names part_1, part_2 etc...
        use the function readMultipleDataframesParquet method of the DldProcessor class (DldProcessorV2 or later)
        to load data for analysis.
        as an example: an interval_size of 30000 was used on a 32Gb ram system.

        :parameter runNumber:


        :parameter parquetPath:
            Location where to store the multiple parquet files. If None, default is used.

        :parameter path:
            location of data to be analyzed. If None, default is used.

        :parameter interval_size:
            maximum number of macrobunches per interval. Each interval will run the readInterval method, creating then
            destroying a DldProcessor instance.

        NOTE: please do not read runs before running this, as the first data read will be ignored and will only occupy ram.

        """

        if path is None:
            path = self.DATA_RAW_DIR
        if parquetPath is None:
            parquetPath = self.DATA_PARQUET_DIR
        if runNumber is None:
            runNumber = self.runNumber
        if interval_size is None:
            interval_size = self.MAX_INTERVAL_SIZE

        fileName = parquetPath + str(runNumber)

        # get the intervals belonging to given run, and output the split ranges in a list
        temp_processor = DldFlashProcessor()
        intervals = temp_processor.getMacrobunchIDIntervals(runNumber, interval_size=interval_size, path=path)
        print('Data divided in {} intervals'.format(len(intervals)))
        del temp_processor

        # iterate over all intervals and output relative files.
        for i in range(len(intervals)):
            print("Reading interval {}".format(i + 1))
            temp_processor = DldFlashProcessor()
            temp_processor.readInterval(intervals[i], path=path)

            print("Saving Parquet File")
            if single_file:
                temp_processor.storeDataframes(fileName, 'parquet', append=True)
            else:
                temp_processor.storeDataframes(fileName + '/part_' + str(i), 'parquet')
        print("Data saved in {0} as {1} parquet folder couples. \nLoading saved data".format(fileName,
                                                                                             len(intervals) * 2))

        self.readMultipleDataframesParquet(fileName)
        try:
            test = len(self.dd)
            print('Successfully loaded parquet data.')
        except AttributeError:
            print('Problems during parquet data loading. No data available.')

    def readMultipleDataframesParquet(self, runNumber=None, parquetPath=None):
        """ Allows for loading of parquet datasets created in multiple files.

        DEPRECATED - see writeRunToMultipleParquet.

        Data is expected in a series of subfolders as created by the function storeDataframesMultiParquet,
        located in (DldFlashDataframeCreator_5 or later file)


        """

        if runNumber is None:
            runNumber = self.runNumber

        if parquetPath is None:
            fileName = self.DATA_PARQUET_DIR + str(runNumber)
        else:
            if parquetPath[-1] != '/':
                parquetPath = parquetPath + '/'
            fileName = parquetPath + str(runNumber)

        subDirs = os.listdir(fileName)
        print(fileName)
        print(subDirs)
        names = []
        for i in range(int(len(subDirs) / 2)):
            names.append(subDirs[2 * i][:-3])
        del subDirs
        self.readDataframesParquet("{0}/{1}".format(fileName, names[0]))

        for name in names[1:]:
            self.appendDataframeParquet("{0}/{1}".format(fileName, name))

    def getMacrobunchIDIntervals(self, runNumber, interval_size=10000, force_max_intervals=0, path=None):
        """ Divide macrobunches from a run into intervals of defined size.

        Returns list of tuples containing first and last macrobunchID of each interval.
        Usefull for splitting large runs in smaller blocks.
        Defined particularly for the function writeToMUltipleParquet.

        Parameters:
            runNumber (int): number of the run you want to look at
            interval_size (int): number of macrobunches to be contained in each interval.
            force_max_intervals (bool): number of intervals to return(counted from the start).
            path (str): path to the location where hdf5 data from FLASH is saved
            if None, uses the string defined in self.defaultPath

        Returns:
            intervals (list of tuples): list of tuples containing first and last macrobunchID of each interval

        """

        # allow for using the default path, which can be redefined as class variable. leaving retrocompatibility
        if path is None:
            path = self.DATA_RAW_DIR

        daqAccess = BeamtimeDaqAccess.create(path)
        dldPosXName = "/uncategorised/FLASH1_USER2/FLASH.FEL/HEXTOF.DAQ/DLD1:0/dset"
        _, otherStuff = daqAccess.allValuesOfRun(dldPosXName, runNumber)
        macrobunches_from = otherStuff[0]
        macrobunches_to = otherStuff[1]

        n_of_macrobunches = macrobunches_to - macrobunches_from
        n_of_intervals = int(n_of_macrobunches / interval_size) + 1

        print('{0:,} MacroBunchIDs divided into {1} intervals\n'.format(n_of_macrobunches, n_of_intervals))

        # force maximum number of segments:

        if force_max_intervals != 0:
            n_of_intervals = force_max_intervals
            print("Forced to process only first {} macrobunches\n".format(n_of_intervals * interval_size))

        intervals = []  # list containing tuple of start and stop point for each interval.

        for i in range(n_of_intervals):
            start = macrobunches_from + i * interval_size
            stop = macrobunches_from + (i + 1) * interval_size - 1
            if stop > macrobunches_to:
                stop = macrobunches_to
            intervals.append((int(start), int(stop)))
        return intervals


if __name__ == '__main__':
    main()
