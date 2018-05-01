import os
import dask
import dask.dataframe
import dask.multiprocessing
import h5py
import numpy as np
import pandas as pd
from configparser import ConfigParser
import matplotlib.pyplot as plt

_VERBOSE = False


# For code testing (Steinn Y. Agustsson)
def main():
    from processor.DldFlashDataframeCreator import DldFlashProcessor
    processor = DldFlashProcessor()
    processor.runNumber = 19135
    processor.readDataframes()
    processor.postProcess()
    pptime = processor.addBinning('pumpProbeTime',-54,-44,.1)
    ToF = processor.addBinning('dldTime', 630, 670, 10*processor.TOF_STEP_TO_NS)

    result = processor.computeBinnedData(saveName='test2')
    # processor.save_array(result,'test')


class DldProcessor():
    """
      This class simplifies the analysis of data files recorded during the
      beamtime of August 2017. It converts the electrons from the DLD into
      a clean table and uses DASK for binning and further analysis.
    """

    def __init__(self):
        """ Create and manage a DASK DataFrame from the data recorded at FLASH.

        Attributes (loaded from SETTINGS.ini):
            N_CORES (int): number of available CPU cores to use.
            CHUNK_SIZE (int): Size of the chunks in which a parquet file will
                be divided.
            TOF_STEP_NS (float): step size in ns of the dldTime. Used to
                convert the step number to the ToF time in the delay line
                detector.
            TOF_STEP_EV (float): step size in eV of the dldTime. Used to
                convert the step number to energy of the photoemitted electrons.
            DATA_RAW_DIR (str): Path to raw data hdf5 files output by FLASH
            DATA_PARQUET_DIR (str): Path to where parquet files are stored.
            DATA_H5_DIR (str): Path to where hdf5 files containing binned data
                are stored.
            DATA_RESULTS_DIR (str): Path to default saving location for results
                in np.array, tiff stack formats etc...
        """

        self.resetBins()
        # initialize attributes to their type. Values are then taken from SETTINGS.ini through initialize_attributes()
        self.N_CORES = int
        self.UBID_OFFSET = int
        self.CHUNK_SIZE = int
        self.TOF_STEP_TO_NS = float
        self.TOF_NS_TO_EV = float
        self.TOF_STEP_TO_EV = float
        self.ET_CONV_E_OFFSET = float
        self.ET_CONV_T_OFFSET = float

        self.DATA_RAW_DIR = str
        self.DATA_H5_DIR = str
        self.DATA_PARQUET_DIR = str
        self.DATA_RESULTS_DIR = str
        self.initAttributes()

        self._LEGACY_BINNING = False  # set true to use the old binning method with arange, instead of linspace

    def initAttributes(self, import_all=False):
        """ Parse settings file and assign the variables.

        Parameters:
            import_all (bool): if True, imports all entries in settings.ini under section [processor] and [paths].
                if False, only imports those that match existing attribute names.
                False is the better choice, since it keeps better track of attributes.
        """
        
        settings = ConfigParser()
        if os.path.isfile(os.path.join(os.path.dirname(__file__), 'SETTINGS.ini')):
            settings.read(os.path.join(os.path.dirname(__file__), 'SETTINGS.ini'))
        else:
            settings.read(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'SETTINGS.ini'))

        for section in settings:
            for entry in settings[section]:
                if _VERBOSE: print('trying: {} {}'.format(entry.upper(), settings[section][entry]))
                try:
                    _type = getattr(self, entry.upper())
                    setattr(self, entry.upper(), _type(settings[section][entry]))
                    if _VERBOSE: print(entry.upper(), _type(settings[section][entry]))
                except AttributeError as e:
                    if _VERBOSE: print('attribute error: {}'.format(e))
                    if import_all:  # old method
                        try:  # assign the attribute to the best fitting type between float, int and string
                            f = float(settings[section][entry])
                            i = int(f)
                            if f - i == 0.0:
                                val = i  # assign Integer
                            else:
                                val = f  # assign Float
                            setattr(self, entry.upper(), val)
                        except ValueError:  # assign String
                            setattr(self, entry.upper(), str(settings[section][entry]))
                    else:
                        pass

    def readDataframes(self, fileName=None, path=None, format='parquet'):
        """ Load data from a parquet or HDF5 dataframe.

        Access the data as hdf5 file (this is the format used internally,
        NOT the FLASH HDF5-files from the DAQ system!)

        Parameters:
            fileName (str): name (including path) of the folder containing hdf5
                files where the data was saved.
            format (str): either 'parquet' to load a parquet type of dataframe,
                or 'h5' or 'hdf5' to load hdf5 dataframes
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
            self.dd = dask.dataframe.read_parquet(fileName + "_el")
            self.ddMicrobunches = dask.dataframe.read_parquet(fileName + "_mb")
        else:
            self.dd = dask.dataframe.read_hdf(fileName, '/electrons', mode='r', chunksize=self.CHUNK_SIZE)
            self.ddMicrobunches = dask.dataframe.read_hdf(fileName, '/microbunches', mode='r',
                                                          chunksize=self.CHUNK_SIZE)

        # self.postProcess()

    def appendDataframeParquet(self, fileName):
        """ Append data to an existing dask Parquet dataframe.

        This can be used to concatenate multiple DAQ runs in one dataframe.
        Data is taken from the dd and dd_microbunch dataframe attributes.

        Parameters:
            fileName (str): name (including path) of the folder containing
                parquet files where to append the new data.
        """
        
        print(len(self.dd.divisions))
        newdd = dask.dataframe.read_parquet(fileName + "_el")
        print(len(newdd.divisions))
        self.dd = self.dd.append(newdd)
        self.ddMicrobunches = self.ddMicrobunches.append(dask.dataframe.read_parquet(fileName + "_mb"))

    def postProcess(self, bamCorrectionSign=0, kCenter=None):
        """ Apply corrections to the dataframe.

        Runs the methods to post process the dataframe. Includes BAM sign
        correction and polar coordinates axes generation.

        /!\ BAM correction is tricky and will mess up the delay histogram.
        This is because of strong correlation with micro bunch ID of both the
        BAM value and the photoemission yield, i.e. photons at the end of a
        Macro bunch give more photoelectrons while systematically being
        shifted in time.

        Parameters:
            bamCorrectionSign (int): used to apply sign to the bam correction: accepted values are 0,1,-1
                set to 0 to avoid applying bam correction, set to None to leave
                unchanged the pump probe delay information (doesnt change name).
                See correctBAM for details.
            kCenter (int,int):  position of the center of k-space in the dld
                detector array. If set to None, no polar coordinates are added.
                See createPolarCoordinates for details.

        """
        
        if bamCorrectionSign is not None:
            self.correctBAM(sign=bamCorrectionSign)

        if kCenter is not None:
            self.createPolarCoordinates(kCenter)

    def correctBAM(self, sign=1):
        """ Correct pump probe time by BAM.

        Corrects the pulse to pulse jitter, and changes name from
        delayStageTime to pumpProbeTime. BAM correction shifts the time delay
        by a constant value.

        /!\ BAM correction is tricky and will mess up the delay histogram.
        This is because of strong correlation with micro bunch ID of both the
        BAM value and the photoemission yield, i.e. photons at the end of a
        Macro bunch give more photoelectrons while systematically being
        shifted in time.

        Default value is 1 since the BAM measures the delay between the master
        clock start and the arrival of the beam.
        On the other hand, more positive delay stage values are for when the FEL
        arrives earlier (FEL before pump is on the more positive side of t0).
        A bigger delay in beam arrival for an FEL pulse means that the photoelectrons
        actually had a more negative delay (probe later than pump) than what the delay stage
        measured, and should therefore be moved to more negative values.

        Parameters:
            sign (int): sign multiplier for BAM correction
                accepted values: 0, 1, -1
                Avoid using -1 unless debugging
        """
        
        self.dd['pumpProbeTime'] = self.dd['delayStageTime'] - self.dd['bam'] * sign
        self.ddMicrobunches['pumpProbeTime'] = self.ddMicrobunches['delayStageTime'] - self.ddMicrobunches[
            'bam'] * sign

    def createPolarCoordinates(self, kCenter=(250, 250)):
        """ Define polar coordinates for k-space values.

        Parameters:
            kCenter (int,int): position of the center of k-space in the dld
                detector array
        """

        def radius(df):
            return np.sqrt(np.square(df.posX - kCenter[0]) + np.square(df.posY - kCenter[1]))

        def angle(df):
            return np.arctan2(df.posY - kCenter[1], df.posX - kCenter[0])

        self.dd['posR'] = self.dd.map_partitions(radius)
        self.dd['posT'] = self.dd.map_partitions(angle)

    def normalizePumpProbeTime(self, data_array, ax=None):
    # TODO: work on better implementation and accessibility for this method
        """ Normalise data to the delay stage histogram.

        Normalises the data array to the number of counts per delay stage step.

        Parameters:
            data_array (np.array): data array containing binned data, as
            created by the computeBinnedData method.

        Raises:
            ValueError: when no pump probe time delay axis is available.

        Returns:
            data_array_normalized: normalized version of the input array.
        """
        
        try:
            if ax is None:
                idx = self.binNameList.index('pumpProbeTime')
            else:
                idx = ax
            data_array_normalized = np.swapaxes(data_array, 0, idx)
            norm_array = self.delaystageHistogram
            for i in range(np.ndim(data_array_normalized) - 1):
                norm_array = norm_array[:, None]
            print('normalized pumpProbe data found along axis {}'.format(idx))
            data_array_normalized = data_array_normalized / norm_array
            data_array_normalized = np.swapaxes(data_array_normalized, idx, 0)
            return data_array_normalized

        except ValueError:
            raise ValueError('No pump probe time bin, could not normalize to delay stage histogram.')

    def save2hdf5(self, binnedData, path=None, filename='default.hdf5', normalizedData=None, overwrite=False):
        """ Store the binned data in a hdf5 file.

        Parameters:
            binnedData (pd.DataFrame): binned data with bins in dldTime, posX, and posY
                (and if to be normalized, binned in detectors)
            filename (string): name of the file,
            path (string, optional): path to the location where to save the hdf5 file. If None, uses the default value
                defined in SETTINGS.ini
            normalizedData (bool): Normalized data for both detector, so it should be a 3d array (posX, posY,detectorID).
            overwrite (bool): if True, overwrites existing files with matching name.

        Example:
            Normalization given, for example take it from run 18440.

            processor.readRun(18440)
            processor.addBinning('posX', 500, 1000, 2)
            processor.addBinning('posY', 500, 1000, 2)
            processor.addBinning('dldDetectorId', -1, 2, 1)
            norm = processor.computeBinnedData()
            norm = np.nan_to_num(norm)
            norm[norm<10]=1 # 10 or smaller seems to be outside of detector
            norm[:,:,0][norm[:,:,0] >= 10]/=norm[:,:,0][norm[:,:,0] >= 10].mean()
            norm[:,:,1][norm[:,:,1] >= 10]/=norm[:,:,1][norm[:,:,1] >= 10].mean()
            norm[norm<0.05]=0.1

            Raises:
                Exception Wrong dimension: if data from binnedData has dimensions different from 4
        """

        # TODO: generalise this function for different data input shapes or bin orders
        if path is None:
            path = self.DATA_H5_DIR

        if normalizedData is not None:
            if binnedData.ndim != 4:
                raise Exception('Wrong dimension')
            data2hdf5 = np.zeros_like(binnedData[:, :, :, 0])

            # normalize for all time binns
            for i in range(binnedData.shape[0]):
                # normalize for both detectors (0 and 1)

                data2hdf5[i, :, :] = binnedData[i, :, :, 0].transpose() / normalizedData[:, :, 0].transpose()
                data2hdf5[i, :, :] += binnedData[i, :, :, 1].transpose() / normalizedData[:, :, 1].transpose()
        else:
            # detector binned? -> sum together
            if binnedData.ndim == 4:
                data2hdf5 = binnedData.sum(axis=3).transpose((0, 2, 1))
            else:
                if binnedData.ndim != 3:
                    raise Exception('Wrong dimension')
                # print(binnedData.transpose((1,2).shape)
                data2hdf5 = binnedData.transpose((0, 2, 1))

        # create file and save data
        mode = "w-"  # fail if file exists
        if overwrite:
            mode = "w"

        f = h5py.File(path + filename, mode)
        dset = f.create_dataset("experiment/xyt_data", data2hdf5.shape, dtype='float64')

        dset[...] = data2hdf5
        f.close()
        
        print("Created file " + filename)

    def save_binned(self, binnedData, name, path=None, mode='w'):
        """ Save a binned array to h5 file. The file includes the axes (taken from the scheduled bins)
        and the delay histograms, if present.

        Parameters:
        
            binnedData : 
                binned data
            name : str
                extra name tag in the filename
            path : str | None
                file path
            mode : str | 'w' (write)
                write mode of h5 file
        """

        if path is None:
            path = self.DATA_RESULTS_DIR

        filename = 'run{}_{}.h5'.format(self.runNumber,name)
        h5File =  h5py.File(path+filename, mode)

        # Saving data
        h5File.create_dataset('binnedData',data=binnedData)

        # Saving axes
        aa = h5File.create_group("axes")
        for i, binName in enumerate(self.binNameList):
            aa.create_dataset(format(binName), data=self.binRangeList[i])

        # Saving delay histograms
        hh = h5File.create_group("histograms")
        if hasattr(self,'delaystageHistogram'):
            hh.create_dataset('delaystageHistogram', data=self.delaystageHistogram)
        if hasattr(self,'delaystageHistogram'):
            hh.create_dataset('pumpProbeHistogram', data=self.pumpProbeHistogram)

        h5File.close()

    def load_binned(self, name, path=None, mode='r'):
        """ load an h5 file saved with save_array.
        
        Parameters:
        
                name : str
                    extra name tag in the filename
                path : str | None
                    file path
                mode : str | 'r' (read)
                    read mode of h5 file
        """
        
        if path is None:
            path = self.DATA_RESULTS_DIR

        filename = 'run{}_{}.h5'.format(self.runNumber, name)
        h5File = h5py.File(path + filename, mode)

        # Retrieving binned data
        data = h5File['binnedData'][()]

        # Retrieving axes from h5 file
        axes = []
        for ax in h5File['axes/']:
            axes.append(h5File['axes/'+ax][()])

        # Retrieving delay histograms
        hists = []
        for hist in h5File['histograms/']:
            hists.append(h5File['histograms/'+hist][()])

        h5File.close()
        
        return data, axes, hists

    def addBinningOld(self, name, start, end, steps, useStepSize=True, include_last=True, force_legacy=False, ):
        """ Add binning of one dimension, to be then computed with computeBinnedData method.

        Creates a list of bin names, (binNameList) to identify the axis on
        which to bin the data. Output array dimensions order will be the same
        as in this list. The attribute binRangeList will contain the ranges of
        the binning used for the corresponding dimension.

        Binning is created using np.linspace (formerly was done with np.arange).
        The implementation allows to choose between setting a step size
        (useStepSize=True, default) or using a number of bins (useStepSize=False).

        Parameters:
            name (string): Name of the column to bin to. Possible column names are:
                posX, posY, dldTime, pumpProbeTime, dldDetector, etc...
            start (float): position of first bin
            end (float): position of last bin (not included!)
            steps (float): define the bin size: if useStepSize=True (default),
                this is the step size, while if useStepSize=False, then this is the
                number of bins. In Legacy mode (force_legacy=True, or
                processor._LEGACY_MODE=True)

            force_legacy (bool): if true, imposes old method for generating binns,
                based on np.arange instead of linspace.

        See also:
            computeBinnedData : Method to compute all bins created with this function.

        Notes:
            If the name is 'pumpProbeTime': sets self.delaystageHistogram for normalization.
        """
        
        _LEGACY_BINNING = False
        if _LEGACY_BINNING or force_legacy:
            bins = np.arange(start, end, steps)

        elif useStepSize:
            rest = abs(end - start) % steps
            n_bins = int((abs(end - start) - rest) / steps) + 1

            if not include_last:
                n_bins -= 1
            bins = np.linspace(start, end, n_bins, endpoint=include_last)
        else:
            assert isinstance(steps, int) and steps > 0, 'number of steps must be a positive integer number'
            bins = np.linspace(start, end, steps, endpoint=include_last)

        # write the parameters to the bin list:
        self.binNameList.append(name)
        self.binRangeList.append(bins)
        if (name == 'pumpProbeTime'):
            # self.delaystageHistogram = numpy.histogram(self.delaystage[numpy.isfinite(self.delaystage)], bins)[0]
            delaystageHistBinner = self.ddMicrobunches['pumpProbeTime'].map_partitions(pd.cut, bins)
            delaystageHistGrouped = self.ddMicrobunches.groupby([delaystageHistBinner])
            self.delaystageHistogram = delaystageHistGrouped.count().compute()['bam'].to_xarray().values.astype(
                np.float64)  # TODO: discuss and improve the delay stage histogram normalization.

    def filterProcessor(self, colname, lb=None, ub=None):
        """ Apply a value range filter to a column in the dataframes generated in the current processor
        
        Parameters:
        
            colname : str
                column name for the filter
            lb : numeric | None
                lower bound of the filter
            ub : numeric | None
                upper bound of the filter
        """
        
        if colname in self.dd.columns:
            if lb is not None:
                self.dd = self.dd[self.dd[colname] > lb]
            if ub is not None:
                self.dd = self.dd[self.dd[colname] < ub]
        if colname in self.ddMicrobunches.columns:
            if lb is not None:
                self.ddMicrobunches = self.ddMicrobunches[self.ddMicrobunches[colname] > lb]
            if ub is not None:
                self.ddMicrobunches = self.ddMicrobunches[self.ddMicrobunches[colname] < ub]

    def genBins(self, start, end, steps, useStepSize=True, forceEnds=False, include_last=True, force_legacy=False):
        """Creates bins for use by binning functions. Can also be used to generate x axes.

        Binning is created using np.linspace (formerly was done with np.arange).
        The implementation allows to choose between setting a step size
        (useStepSize=True, default) or using a number of bins (useStepSize=False).

        In general, it is not possible to satisfy all 3 parameters: start, end, steps.
        For this reason, you can choose to give priority to the step size or to the
        interval size. In case forceEnds=False, the steps parameter is given
        priority and the end parameter is redefined, so the interval can actually
        be larger than expected. In case forceEnds = true, the stepSize is not
        enforced, and the interval is divided by the closest step that divides it
        cleanly. This of course only has meaning when choosing steps that do not
        cleanly divide the interval.

        Parameters:
            start (float): position of first bin
            end (float): position of last bin (not included!)
            steps (float): define the bin size: if useStepSize=True (default),
                this is the step size, while if useStepSize=False, then this is the
                number of bins. In Legacy mode (force_legacy=True, or
                processor._LEGACY_MODE=True)
            useStepSize (bool): tells python to interpret steps as a step size if
                True, or as the number of steps if False
            forceEnds (bool): tells python to give priority to the end parameter
                rather than the step parameter (see above for more info)
            include_last (bool): closes the interval on the right when true. If
                using step size priority, will expand the interval to include
                the next value when true, will shrink the interval to contain all
                points within the bounds if false.
            force_legacy (bool): if true, imposes old method for generating binns,
                based on np.arange instead of linspace.
        """
        from decimal import Decimal

        _LEGACY_BINNING = False
        # uses old method of binning
        if _LEGACY_BINNING or force_legacy:
            bins = np.arange(start, end, steps)

        # default interpretation of steps as the step size
        # needs Decimal library for dealing with float representation issues
        elif useStepSize:
            if not forceEnds:
                if (abs(float(Decimal(str(abs(end - start))) % Decimal(str(steps)))) > 0):
                    if include_last:
                        end += float(Decimal(str(steps))-(Decimal(str(abs(end - start))) % Decimal(str(steps))))
                    else:
                        end -= float((Decimal(str(abs(end - start))) % Decimal(str(steps))))
                        include_last = True
            n_bins = round((abs(end - start)) / steps) + 1
            if not include_last:
                n_bins -= 1
            bins = np.linspace(start, end, n_bins, endpoint=include_last)

        # non default interpretation of steps as the number of steps
        # /!\ remember to use n+1 if including the end point (default)
        else:
            assert isinstance(steps, int) and steps > 0, 'number of steps must be a positive integer number'
            bins = np.linspace(start, end, steps, endpoint=include_last)
        
        return bins

    def addBinning(self, name, start, end, steps, useStepSize=True, forceEnds=False, include_last=True, force_legacy=False):
        """ Add binning of one dimension, to be then computed with computeBinnedData method.

        Creates a list of bin names, (binNameList) to identify the axis on
        which to bin the data. Output array dimensions order will be the same
        as in this list. The attribute binRangeList will contain the ranges of
        the binning used for the corresponding dimension.

        Parameters:
            name (string): Name of the column to bin to. Possible column names are:
                posX, posY, dldTime, pumpProbeTime, dldDetector, etc...
            start (float): position of first bin
            end (float): position of last bin (not included!)
            steps (float): define the bin size: if useStepSize=True (default),
                this is the step size, while if useStepSize=False, then this is the
                number of bins. In Legacy mode (force_legacy=True, or
                processor._LEGACY_MODE=True)
            useStepSize (bool): tells python to interpret steps as a step size if
                True, or as the number of steps if False
            forceEnds (bool): tells python to give priority to the end parameter
                rather than the step parameter (see genBins for more info)
            include_last (bool): closes the interval on the right when true. If
                using step size priority, will expand the interval to include
                the next value when true, will shrink the interval to contain all
                points within the bounds if false.
            force_legacy (bool): if true, imposes old method for generating binns,
                based on np.arange instead of linspace.
        Returns:
            axes (np.array): axis of the binned dimesion. The points defined on this axis are the middle points of each
                bin.

        See also:
            computeBinnedData : Method to compute all bins created with this function.

        Notes:
            If the name is 'pumpProbeTime': sets self.delaystageHistogram for normalization.
        """

        # write the parameters to the bin list:
        bins = self.genBins(start, end, steps, useStepSize, forceEnds, include_last, force_legacy)
        self.binNameList.append(name)
        self.binRangeList.append(bins)
        if (name == 'pumpProbeTime'):
            # self.delaystageHistogram = numpy.histogram(self.delaystage[numpy.isfinite(self.delaystage)], bins)[0]
            delaystageHistBinner = self.ddMicrobunches['pumpProbeTime'].map_partitions(pd.cut, bins)
            delaystageHistGrouped = self.ddMicrobunches.groupby([delaystageHistBinner])
            self.pumpProbeHistogram = delaystageHistGrouped.count().compute()['bam'].to_xarray().values.astype(
                np.float64)
        if (name == 'delayStageTime'):
            # self.delaystageHistogram = numpy.histogram(self.delaystage[numpy.isfinite(self.delaystage)], bins)[0]
            delaystageHistBinner = self.ddMicrobunches['delayStageTime'].map_partitions(pd.cut, bins)
            delaystageHistGrouped = self.ddMicrobunches.groupby([delaystageHistBinner])
            self.delaystageHistogram = delaystageHistGrouped.count().compute()['bam'].to_xarray().values.astype(
                np.float64)
        if useStepSize:
            stepSize = steps
        else:
            stepSize = (end-start)/steps
        axes = self.genBins(start+stepSize/2,end-stepSize/2,stepSize, useStepSize, forceEnds, include_last, force_legacy)

        return axes

    def resetBins(self):
        """ Reset the bin list
        """
        
        self.binNameList = []
        self.binRangeList = []

    def computeBinnedData(self,saveName=None, savePath= None, saveMode='w'):
        """ Use the bin list to bin the data.

        Returns:
            result (np.array): It returns a numpy array of float64 values. Number of bins defined will define the
            dimensions of such array.

        Notes:
            postProcess method must be used before computing the binned data if binning along pumpProbeDelay or polar
            k-space coordinates.
        """

        def analyzePart(part):
            """ Function called by each thread of the analysis.
            """
            
            grouperList = []
            for i in range(len(self.binNameList)):
                grouperList.append(pd.cut(part[self.binNameList[i]], self.binRangeList[i]))
            grouped = part.groupby(grouperList)
            result = (grouped.count())['microbunchId'].to_xarray().values
            
            return np.nan_to_num(result)
        
        
        
        
        
        # new binner for a partition, not using the Pandas framework. It should be faster!
        def analyzePartNumpy(part):
            """ Function called by each thread of the analysis. This now should be faster.
            """
            
            # get the data as numpy:
            vals = part.values
            cols = part.columns.values
            # create array of columns to be used for binning
            colsToBin = []
            for binName in self.binNameList:
                idx = cols.tolist().index(binName)
                colsToBin.append(idx)
    
            # create the array with the bins and bin ranges
            numBins = []
            ranges = []
            for i in range(0, len(colsToBin)):
                # need to subtract 1 from the number of bin ranges
                numBins.append(len(self.binRangeList[i])-1)
                ranges.append((self.binRangeList[i].min(), self.binRangeList[i].max()))
            # now we are ready for the analysis with numpy:
            res, edges = np.histogramdd(vals[:,colsToBin],bins=numBins,range=ranges)
            
            return res
        
        
        
        
        

        # prepare the partitions for the calculation in parallel    
        calculatedResults = []
        for i in range(0, self.dd.npartitions, self.N_CORES):
            resultsToCalculate = []
            # process the data in blocks of n partitions (given by the number of cores):
            for j in range(0, self.N_CORES):
                if (i + j) >= self.dd.npartitions:
                    break
                part = self.dd.get_partition(i + j)
                resultsToCalculate.append(dask.delayed(analyzePartNumpy)(part))

            # now do the calculation on each partition (using the dask framework):
            if len(resultsToCalculate) > 0:
                print("computing partitions " + str(i) + " to " + str(i + j) + " of " + str(
                    self.dd.npartitions) + ". partitions calculated in parallel: " + str(
                    len(resultsToCalculate)))
                results = dask.compute(*resultsToCalculate)
                total = np.zeros_like(results[0])
                for result in results:
                    total = total + result
                calculatedResults.append(total)
                del total
            del resultsToCalculate

        # we now need to add them all up (single core):
        result = np.zeros_like(calculatedResults[0])
        for r in calculatedResults:
            r = np.nan_to_num(r)
            result = result + r
        result = result.astype(np.float64)
        if saveName is not None:
            self.save_binned(result, saveName, path=savePath, mode=saveMode)
        
        return result
        
    def computeBinnedDataMulti(self,saveName=None, savePath= None, saveMode='w', rank=None, size=None):
        """ Use the bin list to bin the data.

        Returns:
            result (np.array): It returns a numpy array of float64 values. Number of bins defined will define the
            dimensions of such array.

        Notes:
            postProcess method must be used before computing the binned data if binning along pumpProbeDelay or polar
            k-space coordinates.
        """

        def analyzePart(part):
            """ Function called by each thread of the analysis."""
            grouperList = []
            for i in range(len(self.binNameList)):
                grouperList.append(pd.cut(part[self.binNameList[i]], self.binRangeList[i]))
            grouped = part.groupby(grouperList)
            result = (grouped.count())['microbunchId'].to_xarray().values
            
            return np.nan_to_num(result)
        
        
        
        
        
        # new binner for a partition, not using the Pandas framework. It should be faster!
        def analyzePartNumpy(vals,cols):
            """ Function called by each thread of the analysis. This now should be faster. """
            # get the data as numpy:
            #vals = part.values
            #cols = part.columns.values
            # create array of columns to be used for binning
            colsToBin = []
            for binName in self.binNameList:
                idx = cols.tolist().index(binName)
                colsToBin.append(idx)
    
            # create the array with the bins and bin ranges
            numBins = []
            ranges = []
            for i in range(0, len(colsToBin)):
                numBins.append(len(self.binRangeList[i]))
                ranges.append((self.binRangeList[i].min(), self.binRangeList[i].max()))
            # now we are ready for the analysis with numpy:
            res, edges = np.histogramdd(vals[:,colsToBin],bins=numBins,range=ranges)
            
            return res
        
        
        
        
        

        # prepare the partitions for the calculation in parallel    
        calculatedResults = []
        results=[]
        print(rank,size)
        for i in range(0, self.dd.nparti tions, size):
            resultsToCalculate = []
            # process the data in blocks of n partitions (given by the number of cores):
            #for j in range(0, self.N_CORES):
            if (i + rank) >= self.dd.npartitions:
                    break
            partval = self.dd.get_partition(i + rank).values.compute()
            partcol = self.dd.get_partition(i + rank).columns.values
            if (i==0):
              results=analyzePartNumpy(partval,partcol)
            else:
              results+=analyzePartNumpy(partval,partcol) 
            print("computing partitions " + str(i+rank) + " of " + str(
                    self.dd.npartitions) + ". partitions calculated in parallel: " + str(size))
            
        results = np.nan_to_num(results)
        results = results.astype(np.float64)
        if saveName is not None:
            self.save_binned(results, saveName, path=savePath, mode=saveMode)
        
        return results

    # ==================
    # DEPRECATED METHODS
    # ==================

    def deleteBinners(self):
        """ DEPRECATED in favour of resetBins
        """
        
        print('WARNING: deleteBinners method has been renamed to resetBins.')
        self.resetBins()

    def readDataframesParquet(self, fileName=None):
        """ DEPRECATED: load data from a dask Parquet dataframe.

        DEPRECATED, use readDataframesParquet instead.

        Parameters:
            fileName (str): name (including path) of the folder containing
                parquet files where the data was saved.
        """
        # TODO: remove this function once retro-compatibility is ensured
        
        print(
            'WARNING: readDataframesParquet is being removed.\nUse readDataframes instead: Default behaviour is now parqet.\n',
            ' Specify format="h5" for legacy use.')
        self.readDataframes(fileName)


if __name__ == "__main__":
    main()
