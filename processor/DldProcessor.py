# -*- coding: utf-8 -*-
import warnings

warnings.simplefilter(action='ignore', category=FutureWarning)  # avoid printing FutureWarnings from other packages
import os
import dask
import dask.dataframe
import dask.multiprocessing
import h5py
import numpy as np
import pandas as pd
from tqdm import tqdm
from configparser import ConfigParser
import matplotlib.pyplot as plt

# warnings.resetwarnings()

_VERBOSE = False


class DldProcessor:
    """
    This class simplifies the analysis of data files recorded during the
    beamtime of August 2017. It converts the electrons from the DLD into
    a clean table and uses DASK for binning and further analysis.
    
    :Attributes (loaded from SETTINGS.ini):
        N_CORES : int
            The number of available CPU cores to use.
        CHUNK_SIZE : int
            Size of the chunks in which a parquet file will be divided.
        TOF_STEP_NS : float
            The step size in ns of the dldTime. Used to convert the
            step number to the ToF time in the delay line detector.
        TOF_STEP_EV : float
            The step size in eV of the dldTime. Used to convert the
            step number to energy of the photoemitted electrons.
        DATA_RAW_DIR : str
            Path to raw data hdf5 files output by FLASH
        DATA_PARQUET_DIR : str
            Path to where parquet files are stored.
        DATA_H5_DIR : str
            Path to where hdf5 files containing binned data are stored.
        DATA_RESULTS_DIR : str
            Path to default saving location for results in np.array,
            tiff stack formats etc.
    """

    def __init__(self):
        """ Create and manage a dask DataFrame from the data recorded at FLASH.
        """

        self.resetBins()
        # initialize attributes to their type. Values are then taken from
        # SETTINGS.ini through initAttributes()
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

        # set true to use the old binning method with arange, instead of
        # linspace
        self._LEGACY_BINNING = False

    def initAttributes(self, import_all=False):
        """ Parse settings file and assign the variables.

        :Parameters:
            import_all : bool | False
            
                :True: imports all entries in SETTINGS.ini from the sections [processor] and [paths].
                :False: only imports those that match existing attribute names.
                
            Here ``False`` is the better choice, since it keeps better track of attributes.
        """

        settings = ConfigParser()
        if os.path.isfile(
                os.path.join(
                    os.path.dirname(__file__),
                    'SETTINGS.ini')):
            settings.read(
                os.path.join(
                    os.path.dirname(__file__),
                    'SETTINGS.ini'))
        else:
            settings.read(
                os.path.join(
                    os.path.dirname(
                        os.path.dirname(__file__)),
                    'SETTINGS.ini'))

        for section in settings:
            for entry in settings[section]:
                if _VERBOSE:
                    print(
                        'trying: {} {}'.format(
                            entry.upper(),
                            settings[section][entry]))
                try:
                    _type = getattr(self, entry.upper())
                    setattr(
                        self, entry.upper(), _type(
                            settings[section][entry]))
                    if _VERBOSE:
                        print(entry.upper(), _type(settings[section][entry]))
                except AttributeError as e:
                    if _VERBOSE:
                        print('attribute error: {}'.format(e))
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
                            setattr(
                                self, entry.upper(), str(
                                    settings[section][entry]))
                    else:
                        pass

    def readDataframes(self, fileName=None, path=None, format='parquet'):
        """ Load data from a parquet or HDF5 dataframe.

        Access the data as hdf5 file (this is the format used internally,
        NOT the FLASH HDF5 files obtained from the DAQ system!)

        :Parameters:
            fileName : str | None
                Shared namestring of data file.
            path : str | None (default to ``self.DATA_PARQUET_DIR`` or ``self.DATA_H5_DIR``)
                name of the filepath (down to the lowest-level folder)
            format : str | 'parquet'
                file format, 'parquet' (parquet file), 'h5' or 'hdf5' (hdf5 file).
        """

        format = format.lower()
        assert format in [
            'parquet', 'h5', 'hdf5'], 'Invalid format for data input. Please select between parquet or h5.'

        if path is None:
            if format == 'parquet':
                path = self.DATA_PARQUET_DIR
            elif format in ['hdf5', 'h5']:
                path = self.DATA_H5_DIR
        
        if fileName is None:
            if self.runNumber is None:
                fileName = 'mb{}to{}'.format(
                    self.pulseIdInterval[0], self.pulseIdInterval[1])
            else:
                fileName = 'run{}'.format(self.runNumber)
        fullName = path + fileName  # TODO: test if naming is correct

        if format == 'parquet':
            self.dd = dask.dataframe.read_parquet(fullName + "_el")
            self.ddMicrobunches = dask.dataframe.read_parquet(fullName + "_mb")
        elif format in ['hdf5', 'h5']:
            self.dd = dask.dataframe.read_hdf(
                fullName, '/electrons', mode='r', chunksize=self.CHUNK_SIZE)
            self.ddMicrobunches = dask.dataframe.read_hdf(
                fullName, '/microbunches', mode='r', chunksize=self.CHUNK_SIZE)

    def appendDataframeParquet(self, fileName):
        """ Append data to an existing dask Parquet dataframe.

        This can be used to concatenate multiple DAQ runs in one dataframe.
        Data is taken from the dd and dd_microbunch dataframe attributes.

        :Parameter:
            fileName : str
                name (including path) of the folder containing the
                parquet files to append the new data.
        """

        print(len(self.dd.divisions))
        newdd = dask.dataframe.read_parquet(fileName + "_el")
        print(len(newdd.divisions))
        self.dd = self.dd.append(newdd)
        self.ddMicrobunches = self.ddMicrobunches.append(
            dask.dataframe.read_parquet(fileName + "_mb"))

    def postProcess(self, bamCorrectionSign=0, kCenter=None):
        """ Apply corrections to the dataframe.

        Runs the methods to post-process the dataframe. Includes BAM sign
        correction and polar coordinates axes generation.

        ``/!\`` BAM correction is tricky and will mess up the delay histogram.
        This is because of strong correlation with microbunch ID of both the
        BAM value and the photoemission yield, i.e. photons at the end of a
        macrobunch give more photoelectrons while being systematically
        shifted in time.

        :Parameters:
            bamCorrectionSign : int | 0
                Sign of to the BAM correction.
                Use None to have no correction and no name change.
                See ``correctBAM`` for details.
            kCenter : (int, int) | None
                position of the center of k-space in the DLD detector array.
                If set to None, no polar coordinates are added.
                See createPolarCoordinates for details.

        """

        if bamCorrectionSign is not None:
            self.correctBAM(sign=bamCorrectionSign)

        if kCenter is not None:
            self.createPolarCoordinates(kCenter)

    def correctBAM(self, sign=1):
        """ Correct pump probe time by BAM (beam arrival monitor) data.

        Corrects the pulse to pulse jitter, and changes name from
        delayStageTime to pumpProbeTime. BAM correction shifts the time delay
        by a constant value.

        ``/!\`` BAM correction is tricky and will mess up the delay histogram.
        This is because of strong correlation with the microbunch ID of both the
        BAM value and the photoemission yield, i.e. photons at the end of a
        macrobunch give more photoelectrons while becoming systematically
        shifted in time.

        Default value is 1 since the BAM measures the delay between the master
        clock start and the arrival of the beam.
        
        On the other hand, more positive delay stage values are for when the FEL
        arrives earlier (FEL before pump is on the more positive side of t0).
        A bigger delay in beam arrival for an FEL pulse means that the photoelectrons
        actually had a more negative delay (probe later than pump) than what the delay stage
        measured, and should therefore be moved to more negative values.

        :Parameter:
            sign : int
                Sign multiplier for BAM correction. Avoid using -1 unless debugging.
                
                =======  =====================================
                Value    Operation    
                =======  =====================================
                 0       no correction  
                 1       pumpProbeTime = delayStage - bam
                -1       pumpProbeTime = delayStage + bam
                =======  =====================================
        """

        self.dd['pumpProbeTime'] = self.dd['delayStage'] - \
                                   self.dd['bam'] * sign
        self.ddMicrobunches['pumpProbeTime'] = self.ddMicrobunches['delayStage'] - \
                                               self.ddMicrobunches['bam'] * sign

    def createPolarCoordinates(self, kCenter=(250, 250)):
        """ Calculate polar coordinates for k-space values.

        :Parameter:
            kCenter : (int,int) | (250, 250)
                Pixel position of the k-space center in the DLD array
        """

        def radius(df):
            return np.sqrt(np.square(df.posX - kCenter[0]) +
                           np.square(df.posY - kCenter[1]))

        def angle(df):
            return np.arctan2(df.posY - kCenter[1], df.posX - kCenter[0])

        self.dd['posR'] = self.dd.map_partitions(radius)
        self.dd['posT'] = self.dd.map_partitions(angle)

    def normalizePumpProbeTime(self, data_array, ax='pumpProbeTime'):
        # TODO: work on better implementation and accessibility for this method
        """ Normalizes the data array to the number of counts per delay stage step.

        :Parameter:
            data_array : numpy array
                data array containing binned data, as created by the ``computeBinnedData`` method.
            ax : str | 'pumpProbeTime'
                axis name
                
        :Raise:
            Throw a ValueError when no pump probe time delay axis is available.

        :Return:
            data_array_normalized : numpy array
                normalized version of the input array.
        """
                
        try:
            # Find the index of the normalization axis
            idx = self.binNameList.index(ax)
            
            data_array_normalized = np.swapaxes(data_array, 0, idx)
            norm_array = self.delaystageHistogram

            for i in range(np.ndim(data_array_normalized) - 1):
                norm_array = norm_array[:, None]
            print('normalized pumpProbe data found along axis {}'.format(idx))

            data_array_normalized = data_array_normalized / norm_array
            data_array_normalized = np.swapaxes(data_array_normalized, idx, 0)

            return data_array_normalized

        except ValueError:
            raise ValueError(
                'No pump probe time bin, could not normalize to delay stage histogram.')

    def save_binned(self, binnedData, namestr, path=None, mode='w'):
        """ Save a binned numpy array to h5 file. The file includes the axes
        (taken from the scheduled bins) and the delay stage histogram, if it exists.

        :Parameters:
            binnedData : numpy array
                Binned multidimensional data.
            namestr : str
                Extra namestring tag in the filename.
            path : str | None
                File path.
            mode : str | 'w'
                Write mode of h5 file ('w' = write).
        """
        _abort = False
        if path is None:
            path = self.DATA_RESULTS_DIR
        if not os.path.isdir(path): # test if the path exists...
            answer = input("The folder {} doesn't exist, do you want to create it? [y/n]")
            if 'y' in answer:
                os.makedirs(path)
            else:
                _abort = True


        filename = '{}.h5'.format(namestr)
        if os.path.isfile(path + filename):
            answer = input("A file named {} already exists. Overwrite it? [y/n or r for rename]".format(filename))
            if 'r' in answer:
                filename = input("choose a new name:")
            elif 'y' in answer:
                pass
            else:
                _abort = True

        if not _abort:
            with h5py.File(path + filename, mode) as h5File:

                print('saving data to {}'.format(path + filename))

                if 'pumpProbeTime' in self.binNameList:
                    idx = self.binNameList.index('pumpProbeTime')
                    pp_data = np.swapaxes(binnedData, 0, idx)

                elif 'delayStage' in self.binNameList:
                    idx = self.binNameList.index('delayStage')
                    pp_data = np.swapaxes(binnedData, 0, idx)
                else:
                    pp_data = None

                # Saving data

                ff = h5File.create_group('frames')

                if pp_data is None:  # in case there is no time axis, make a single dataset
                    ff.create_dataset('f{:04d}'.format(0), data=binnedData)
                else:
                    for i in range(pp_data.shape[0]): # otherwise make a dataset for each time frame.
                        ff.create_dataset('f{:04d}'.format(i), data=pp_data[i, ...])


                # Saving axes
                aa = h5File.create_group("axes")
                # aa.create_dataset('axis_order', data=self.binNameList)
                ax_n = 1
                for i, binName in enumerate(self.binNameList):
                    if binName in ['pumpProbeTime', 'delayStage']:
                        ds = aa.create_dataset('ax0 - {}'.format(binName), data=self.binAxesList[i])
                        ds.attrs['name'] = binName
                    else:
                        ds = aa.create_dataset('ax{} - {}'.format(ax_n, binName), data=self.binAxesList[i])
                        ds.attrs['name'] = binName
                        ax_n += 1
                # Saving delay histograms
                hh = h5File.create_group("histograms")
                if hasattr(self, 'delaystageHistogram'):
                    hh.create_dataset(
                        'delaystageHistogram',
                        data=self.delaystageHistogram)
                if hasattr(self, 'pumpProbeHistogram'):
                    hh.create_dataset(
                        'pumpProbeHistogram',
                        data=self.pumpProbeHistogram)

    def load_binned(self, file_name, mode='r', ret_type='list'):
        """ Load an HDF5 file saved with ``save_binned()`` method.

        :Parameters:
            file_name : str
                name of the file to load, including full path

            mode : str | 'r'
                Read mode of h5 file ('r' = read).
            ret_type: str | 'list','dict'
                output format for axes and histograms:
                'list' generates a list of arrays, ordered as
                the corresponding dimensions in data. 'dict'
                generates a dictionary with the names of each axis.

        :Returns:
            data : numpy array
                Multidimensional data read from h5 file.
            axes : numpy array
                The axes values associated with the read data.
            hist : numpy array
                Histogram values associated with the read data.
        """
        if file_name[-3:] == '.h5':
            filename = file_name
        else:
            filename = '{}.h5'.format(file_name)

        with h5py.File(path + filename, mode) as h5File:

            # Retrieving binned data
            frames = h5File['frames']
            data = []
            if len(frames) == 1:
                data = np.array(frames['f0000'])

            else:
                for frame in frames:
                    data.append(np.array(frames[frame]))
                data = np.array(data)

            # Retrieving axes
            axes = [0 for i in range(len(data.shape))]
            axes_d = {}
            for ax in h5File['axes/']:
                vals = h5File['axes/' + ax][()]
                #             axes_d[ax] = vals
                idx = int(ax.split(' - ')[0][2:])
                if len(frames) == 1:  # shift index to compensate missing time dimension
                    idx -= 1
                axes[idx] = vals

                # Retrieving delay histograms
            hists = []
            hists_d = {}
            for hist in h5File['histograms/']:
                hists_d[hist] = h5File['histograms/' + hist][()]
                hists.append(h5File['histograms/' + hist][()])

        if ret_type == 'list':
            return data, axes, hists
        elif ret_type == 'dict':
            return data, axes_d, hists_d

    def read_h5(self, h5FilePath):
        """ resad the h5 file at given path and return the contained data.

        :parameters:
            h5FilePaht : str
                Path to the h5 file to read.

        :returns:
            result : np.ndarray
                array containing binned data
            axes : dict
                dictionary with axes data labeled by axes name
            histogram : np.array
                array of time normalization data.
        """
        with h5py.File(h5FilePath, 'r') as f:
            result = []
            for frame in f['frames']:
                result.append(f['frames'][frame][...])
            result = np.stack(result, axis=0)

            histogram = None
            if 'pumpProbeHistogram' in f['histograms']:
                histogram = f['histograms']['pumpProbeHistogram'][...]
            elif 'delaystageHistogram' in f['histograms']:
                histogram = f['histograms']['delaystageHistogram'][...]
            axes = {}
            for ax_label in f['axes']:
                ax_name = ax_label.split(' ')[-1]
                axes[ax_name] = f['axes'][ax_label][...]

        return result, axes, histogram

    def addFilter(self, colname, lb=None, ub=None):
        """ Filters the dataframes contained in the processor instance

        :Parameters:
            colname : str
                name of the column in the dask dataframes
            lb : float64 | None
                lower bound of the filter
            ub : float64 | None
                upper bound of the filter
        
        :Effect:
            Filters the columns of ``dd`` and ``ddMicrobunches`` dataframes in place.
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

    def genBins(self, start, end, steps, useStepSize=True,
                forceEnds=False, include_last=True, force_legacy=False):
        """ Creates bins for use by binning functions.
        Can also be used to generate x axes.

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

        :Parameters:
            start : float
                Position of first bin
            end : float
                Position of last bin (not included!)
            steps : float
                Define the bin size. If useStepSize=True (default),
                this is the step size, while if useStepSize=False, then this is the
                number of bins. In Legacy mode (force_legacy=True, or
                processor._LEGACY_MODE=True)
            useStepSize : bool | True
                Tells python to interpret steps as a step size if
                True, or as the number of steps if False
            forceEnds : bool | False
                Tells python to give priority to the end parameter
                rather than the step parameter (see above for more info)
            include_last : bool | True
                Closes the interval on the right when true. If
                using step size priority, will expand the interval to include
                the next value when true, will shrink the interval to contain all
                points within the bounds if false.
            force_legacy : bool | False
                If true, imposes old method for generating bins,
                based on np.arange instead of np.inspace.
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
                if (abs(float(Decimal(str(abs(end - start))) %
                              Decimal(str(steps)))) > 0):
                    if include_last:
                        end += float(Decimal(str(steps)) - \
                                     (Decimal(str(abs(end - start))) % Decimal(str(steps))))
                    else:
                        end -= float((Decimal(str(abs(end - start))) %
                                      Decimal(str(steps))))
                        include_last = True
            n_bins = round((abs(end - start)) / steps) + 1
            if not include_last:
                n_bins -= 1
            bins = np.linspace(start, end, n_bins, endpoint=include_last)

        # non default interpretation of steps as the number of steps
        # /!\ remember to use n+1 if including the end point (default)
        else:
            assert isinstance(
                steps, int) and steps > 0, 'number of steps must be a positive integer number'
            bins = np.linspace(start, end, steps, endpoint=include_last)

        return bins

    def addBinning(self, name, start, end, steps, useStepSize=True, forceEnds=False,
                   include_last=True, force_legacy=False):
        """ Add binning of one dimension, to be then computed with ``computeBinnedData`` method.

        Creates a list of bin names, (binNameList) to identify the axis on
        which to bin the data. Output array dimensions order will be the same
        as in this list. The attribute binRangeList will contain the ranges of
        the binning used for the corresponding dimension.

        :Parameters:
            name : str
                Name of the column to apply binning to. Possible column names are`:`
                posX, posY, dldTime, pumpProbeTime, dldDetector, etc.
            start : float
                Position of first bin
            end : float
                Position of last bin (not included!)
            steps : float
                The bin size, if useStepSize=True (default),
                this is the step size, while if useStepSize=False, then this is the
                number of bins. In Legacy mode (force_legacy=True, or
                processor._LEGACY_MODE=True)
            useStepSize : bool | True
                Tells Python how to interpret steps.
                
                :True: interpret steps as a step size.
                :False: interpret steps as the number of steps.
            forceEnds : bool | False
                Tells python to give priority to the end parameter
                rather than the step parameter (see genBins for more info)
            include_last : bool | True
                Closes the interval on the right when true. If
                using step size priority, will expand the interval to include
                the next value when true, will shrink the interval to contain all
                points within the bounds if false.
            force_legacy : bool | False
                :True: use np.arange method to generate bins.
                :False: use np.linspace method to generate bins.
                
        :Return:
            axes : numpy array
                axis of the binned dimesion. The points defined on this axis are the middle points of
                each bin.
                
        :Note:
            If the name is 'pumpProbeTime': sets self.delaystageHistogram for normalization.
        
        .. seealso::
        
          ``computeBinnedData`` Method to compute all bins created with this function.

        """

        # write the parameters to the bin list:
        bins = self.genBins(start, end, steps, useStepSize, forceEnds, include_last, force_legacy)
        self.binNameList.append(name)
        self.binRangeList.append(bins)

        if (name == 'pumpProbeTime'):
            # self.delaystageHistogram = numpy.histogram(self.delaystage[numpy.isfinite(self.delaystage)], bins)[0]
            delaystageHistBinner = self.ddMicrobunches['pumpProbeTime'].map_partitions(
                pd.cut, bins)
            delaystageHistGrouped = self.ddMicrobunches.groupby(
                [delaystageHistBinner])
            self.pumpProbeHistogram = delaystageHistGrouped.count(
            ).compute()['bam'].to_xarray().values.astype(np.float64)
        if (name == 'delayStage'):
            # self.delaystageHistogram = numpy.histogram(self.delaystage[numpy.isfinite(self.delaystage)], bins)[0]
            delaystageHistBinner = self.ddMicrobunches['delayStage'].map_partitions(
                pd.cut, bins)
            delaystageHistGrouped = self.ddMicrobunches.groupby(
                [delaystageHistBinner])
            self.delaystageHistogram = delaystageHistGrouped.count(
            ).compute()['bam'].to_xarray().values.astype(np.float64)
        if useStepSize:
            stepSize = steps
        else:
            stepSize = (end - start) / steps

        axes = self.genBins(
            start + stepSize / 2,
            end - stepSize / 2,
            stepSize, useStepSize, forceEnds, include_last, force_legacy)
        if axes[-1]>end:
            axes = axes[:-1]
        self.binAxesList.append(axes)
        return axes

    def resetBins(self):
        """ Reset the bin list
        """

        self.binNameList = []
        self.binRangeList = []
        self.binAxesList = []

    def computeBinnedData(self, saveName=None, savePath=None):
        """ Use the bin list to bin the data.
        
        :Parameters:
            saveName : str | None
                filename
            savePath : str | None
                file path

        :Returns:
            result : numpy array
                A numpy array of float64 values. Number of bins defined will define the
                dimensions of such array.

        :Notes:
            postProcess method must be used before computing the binned data if binning
            along pumpProbeDelay or polar k-space coordinates.
        """

        def analyzePart(part):
            """ Function called by each thread of the analysis.
            """

            grouperList = []
            for i in range(len(self.binNameList)):
                grouperList.append(
                    pd.cut(part[self.binNameList[i]], self.binRangeList[i]))
            grouped = part.groupby(grouperList)
            result = (grouped.count())['microbunchId'].to_xarray().values

            return np.nan_to_num(result)

        # new binner for a partition, not using the Pandas framework. It should
        # be faster!
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
                numBins.append(len(self.binRangeList[i]) - 1)
                ranges.append(
                    (self.binRangeList[i].min(),
                     self.binRangeList[i].max()))
            # now we are ready for the analysis with numpy:
            res, edges = np.histogramdd(
                vals[:, colsToBin], bins=numBins, range=ranges)

            return res

        # prepare the partitions for the calculation in parallel
        calculatedResults = []

        if _VERBOSE:
            warnString = "always"
        else:
            warnString = "ignore"
        with warnings.catch_warnings():
            warnings.simplefilter(warnString)

            for i in tqdm(range(0, self.dd.npartitions, self.N_CORES)):
                resultsToCalculate = []
                # process the data in blocks of n partitions (given by the number
                # of cores):
                for j in range(0, self.N_CORES):
                    if (i + j) >= self.dd.npartitions:
                        break
                    part = self.dd.get_partition(i + j)
                    resultsToCalculate.append(dask.delayed(analyzePartNumpy)(part))

                # now do the calculation on each partition (using the dask
                # framework):
                if len(resultsToCalculate) > 0:
                    #                print("computing partitions " + str(i) + " to " + str(i + j) + " of " + str(
                    #                    self.dd.npartitions) + ". partitions calculated in parallel: " + str(
                    #                    len(resultsToCalculate)))
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
            self.save_binned(result, saveName, path=savePath, mode='w')

        return result

    def computeBinnedDataMulti(self, saveName=None, savePath=None,
                               rank=None, size=None):
        """ Use the bin list to bin the data. Cluster-compatible version (Maciej Dendzik)
        
        :Parameters:
            saveName : str | None
                filename
            savePath : str | None
                file path
            rank : int | None
                Rank number of cluster computer
            size : int | None
                Size of partition
        
        :Return:
            result : numpy array
                A numpy array of float64 values. The number of bins determines the
                dimensionality of the output array.

        :Notes:
            postProcess method must be used before computing the binned data if binning
            is applied along pumpProbeDelay or polar k-space coordinates.
        """

        def analyzePart(part):
            """ Function called by each thread of the analysis."""
            grouperList = []
            for i in range(len(self.binNameList)):
                grouperList.append(
                    pd.cut(part[self.binNameList[i]], self.binRangeList[i]))
            grouped = part.groupby(grouperList)
            result = (grouped.count())['microbunchId'].to_xarray().values

            return np.nan_to_num(result)

        # new binner for a partition, not using the Pandas framework. It should
        # be faster!
        def analyzePartNumpy(vals, cols):
            """ Function called by each thread of the analysis. This now should be faster. """
            # get the data as numpy:
            # vals = part.values
            # cols = part.columns.values
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
                ranges.append(
                    (self.binRangeList[i].min(),
                     self.binRangeList[i].max()))
            # now we are ready for the analysis with numpy:
            res, edges = np.histogramdd(
                vals[:, colsToBin], bins=numBins, range=ranges)

            return res

        # prepare the partitions for the calculation in parallel
        calculatedResults = []
        results = []
        print(rank, size)
        for i in range(0, self.dd.npartitions, size):
            resultsToCalculate = []
            # process the data in blocks of n partitions (given by the number of cores):
            # for j in range(0, self.N_CORES):
            if (i + rank) >= self.dd.npartitions:
                break
            partval = self.dd.get_partition(i + rank).values.compute()
            partcol = self.dd.get_partition(i + rank).columns.values
            if (i == 0):
                results = analyzePartNumpy(partval, partcol)
            else:
                results += analyzePartNumpy(partval, partcol)
            print("computing partitions " +
                  str(i +
                      rank) +
                  " of " +
                  str(self.dd.npartitions) +
                  ". partitions calculated in parallel: " +
                  str(size))

        results = np.nan_to_num(results)
        results = results.astype(np.float64)
        if saveName is not None:
            self.save_binned(results, saveName, path=savePath, mode='w')

        return results

    def deleteBinners(self):
        """ **[DEPRECATED]** use resetBins() instead
        """

        print('WARNING: deleteBinners method has been renamed to resetBins.')
        self.resetBins()

    def readDataframesParquet(self, fileName=None):
        """ **[DEPRECATED]** Load data from a dask Parquet dataframe.
        Use readDataframesParquet instead.

        :Parameter:
            fileName : str | None
                name (including path) of the folder containing
                parquet files where the data was saved.
        """
        # TODO: remove this function once retro-compatibility is ensured

        print(
            'WARNING: readDataframesParquet is being removed.\nUse readDataframes instead: Default behaviour is now '
            'parqet.\n',
            ' Specify format="h5" for legacy use.')
        self.readDataframes(fileName)

    # ==================
    # DEPRECATED METHODS
    # ==================

    def save2hdf5(self, binnedData, path=None, filename='default.hdf5',
                  normalizedData=None, overwrite=False):
        """ **[DEPRECATED]** Store the binned data in a hdf5 file.

        :Parameters:
            binneddata : pd.DataFrame
                binned data with bins in dldTime, posX, and posY (and if to be
                normalized, binned in detectors).
            filename : str | 'default.hdf5'
                name of the file.
            path : str | None | None
                path to the location where to save the hdf5 file. If `None`, uses the default value
                defined in SETTINGS.ini
            normalizedData : bool | None
                Normalized data for both detector, so it should be a 3D array
                (posX, posY, detectorID).
            overwrite : bool | False
                :True: overwrites existing files with matching filename.
                :False: no overwriting of files

        :Example:
            Normalization given, for example take it from run 18440.
        ::

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

                data2hdf5[i, :, :] = binnedData[i, :, :, 0].transpose(
                ) / normalizedData[:, :, 0].transpose()
                data2hdf5[i, :, :] += binnedData[i, :, :,
                                      1].transpose() / normalizedData[:, :, 1].transpose()
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
        dset = f.create_dataset(
            "experiment/xyt_data",
            data2hdf5.shape,
            dtype='float64')

        dset[...] = data2hdf5
        f.close()
        print("Created file " + filename)

    def addBinningOld(self, name, start, end, steps, useStepSize=True,
                      include_last=True, force_legacy=False):
        """ **[DEPRECATED]** Add binning of one dimension,
        to be then computed with ``computeBinnedData`` method.

        Creates a list of bin names, (binNameList) to identify the axis on
        which to bin the data. Output array dimensions order will be the same
        as in this list. The attribute binRangeList will contain the ranges of
        the binning used for the corresponding dimension.

        Binning is created using np.linspace (formerly was done with np.arange).
        The implementation allows to choose between setting a step size
        (useStepSize=True, default) or using a number of bins (useStepSize=False).

        :Parameters:
            name : str
                Name of the column to bin to. Possible column names are:
                posX, posY, dldTime, pumpProbeTime, dldDetector, etc.
            start : float
                Position of first bin
            end : float
                Position of last bin (not included!)
            steps : float
                Define the bin size. If useStepSize=True (default),
                this is the step size, while if useStepSize=False, then this is the
                number of bins. In Legacy mode (force_legacy=True, or
                processor._LEGACY_MODE=True)
            force_legacy : bool
                if true, imposes old method for generating bins,
                based on np.arange instead of np.linspace.

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
            assert isinstance(
                steps, int) and steps > 0, 'number of steps must be a positive integer number'
            bins = np.linspace(start, end, steps, endpoint=include_last)

        # write the parameters to the bin list:
        self.binNameList.append(name)
        self.binRangeList.append(bins)
        if (name == 'pumpProbeTime'):
            # self.delaystageHistogram = numpy.histogram(self.delaystage[numpy.isfinite(self.delaystage)], bins)[0]
            delaystageHistBinner = self.ddMicrobunches['pumpProbeTime'].map_partitions(
                pd.cut, bins)
            delaystageHistGrouped = self.ddMicrobunches.groupby(
                [delaystageHistBinner])
            self.delaystageHistogram = delaystageHistGrouped.count().compute()['bam'].to_xarray().values.astype(
                np.float64)  # TODO: discuss and improve the delay stage histogram normalization.
