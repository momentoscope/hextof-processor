# -*- coding: utf-8 -*-

import warnings

warnings.simplefilter(action='ignore', category=FutureWarning)  # avoid printing FutureWarnings from other packages
import os

from datetime import datetime
import json
import dask
import dask.dataframe
import dask.multiprocessing
from dask.diagnostics import ProgressBar
import h5py
import numpy as np
import pandas as pd
from tqdm import tqdm, tqdm_notebook
from configparser import ConfigParser
# import matplotlib.pyplot as plt
from processor.utilities import misc, dfops
from processor.utilities.io import res_to_xarray

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

    def __init__(self, settings=None):
        """ Create and manage a dask DataFrame from the data recorded at FLASH.
        """

        if settings is not None:
            self.loadSettings(settings)
        else:
            self.initAttributes()  # in else because it is called already in load_settings

        self.resetBins()

        # initialize attributes for metadata
        self.sample = {}  # this should contain 'name', 'sampleID', 'cleave number' etc...
        self.histograms = {}
        self.metadata = {}

    @property
    def metadata_dict(self):

        try:
            md = self.metadata
        except AttributeError:
            md = {}
            try: 
                md['run'] = self.runInfo
            except AttributeError:
                md['run'] = {
                    'runNumber': self.runNumber,
                    'pulseIdInterval': self.pulseIdInterval,
                }
            md['processor'] = {'n_cores': self.N_CORES,
                           'chunk_size': self.CHUNK_SIZE,
                               }
            md['calibration'] = {'TOF_STEP_TO_NS': self.TOF_STEP_TO_NS,
                                 'ET_CONV_E_OFFSET': self.ET_CONV_E_OFFSET,
                                 'ET_CONV_T_OFFSET': self.ET_CONV_T_OFFSET,
                                 'ET_CONV_L': self.ET_CONV_L,
                                 'TOF_IN_NS': self.TOF_IN_NS,
                                 }
            md['paths'] = {
                'DATA_RAW_DIR': self.DATA_RAW_DIR,
                'DATA_H5_DIR': self.DATA_H5_DIR,
                'DATA_PARQUET_DIR': self.DATA_PARQUET_DIR,
                'DATA_RESULTS_DIR': self.DATA_RESULTS_DIR,
                'LOG_DIR': self.LOG_DIR,
                'PAH_MODULE_DIR': self.PAH_MODULE_DIR,
                }
            # md['DAQ channels'] =
            md['sample'] = self.sample
            self.metadata = md
        return md

    @property
    def settings(self):
        """ Easy access to settings.ini file

        Returns:
            dictionary with the settings file structure
        """
        settings = ConfigParser()
        root_folder = os.path.dirname(__file__)
        if 'SETTINGS.ini' not in os.listdir(root_folder):
            root_folder = os.path.dirname(root_folder)
        file = os.path.join(root_folder, 'SETTINGS.ini')
        settings.read(file)
        if len(settings.sections()) == 0:
            raise Exception('Failed loading main settings!')
        else:
            return settings

    def initAttributes(self, import_all=False):
        """ Parse settings file and assign the variables.

        Args:
            import_all: bool | False
                Option to import method selection.\n
                ``True`` imports all entries in SETTINGS.ini except those from sections [DAQ channels].
                These are handled in the DldFlashProcessor subclass. Prints a warning when an entry
                is not found as class attribute\n
                ``False`` only imports those that match existing attribute names.
        Warnings:
            UserWarning:
                when an entry is found in the SETTINGS.ini file, which
                is not present as a pre-defined class attribute, it warns the
                user to add id to the code.
        """
        # Hard coded class attributes which can be overwritten by settings files.
        self.N_CORES = int(max(os.cpu_count() - 1, 1))
        self.UBID_OFFSET = int(0)
        self.CHUNK_SIZE = int(100000)
        self.TOF_STEP_TO_NS = np.float64(0.020576131995767355)
        self.ET_CONV_E_OFFSET = np.float64(357.7)
        self.ET_CONV_T_OFFSET = np.float64(82.7)
        self.ET_CONV_L = np.float64(.75)
        self.K_CENTER_X = np.float64(668)
        self.K_CENTER_Y = np.float64(658)
        self.K_RADIUS = np.float64(230)
        self.K_ROTATION_ANGLE = np.float64(0)
        self.STEP_TO_K = np.float64(1.)

        self.TOF_IN_NS = bool(True)
        self.RETURN_XARRAY = bool(True)
        self.SINGLE_CORE_DATAFRAME_CREATION = bool(False)

        self.DATA_RAW_DIR = str('/gpfs/pg2/current/raw/hdf')
        self.DATA_H5_DIR = str('/home/pg2user/data/h5')
        self.DATA_PARQUET_DIR = str('/home/pg2user/DATA/parquet/')
        self.DATA_RESULTS_DIR = str('/home/pg2user/DATA/results/')
        self.LOG_DIR = str('/home/pg2user/DATA/logs/')
        self.PAH_MODULE_DIR = str('')

        # parse the currently loaded settings file and store as class attributes
        # each entry which is not in DAQ channels. Those are handled in the
        # DldFlashProcessor class.
        for sec_name, section in self.settings.items():
            if sec_name != 'DAQ channels':  # ignore the DAQ channels
                for entry_name, entry_value in section.items():
                    for type_ in [int, np.float64]:  # try assigning numeric values
                        try:
                            val = type_(entry_value)
                            break
                        except ValueError:
                            val = None
                    if val is None:
                        val = entry_value
                        if val.upper() == 'FALSE':
                            val = False
                        elif val.upper() == 'TRUE':
                            val = True
                        elif val.upper() in ['AUTO', 'NONE']:  # add option for ignoring value.
                            val = None
                    if val is not None:
                        try:
                            old_type = type(getattr(self, entry_name.upper()))
                            new_type = type(val)
                            if old_type != new_type:
                                warnings.warn(
                                    f'Setting {entry_name} found as {new_type} instead of the expected {old_type}')
                            setattr(self, entry_name.upper(), val)
                        except:
                            if import_all:
                                setattr(self, entry_name.upper(), val)
                            elif  _VERBOSE:
                                warnings.warn(
                                    f'Found new setting {entry_name}. Consider adding to hard coded defaults for correct'
                                    f'type and error handling.')
                            else:
                                pass
        # Old parsing method:
        # for section in settings:
        #     for entry in settings[section]:
        #         if _VERBOSE:
        #             print('trying: {} {}'.format(entry.upper(), settings[section][entry]))
        #         try:
        #             if settings[section][entry].upper() == 'FALSE':
        #                 setattr(self, entry.upper(), False)
        #             else:
        #                 _type = type(getattr(self, entry.upper()))
        #                 setattr(self, entry.upper(), _type(settings[section][entry]))
        #             if _VERBOSE:
        #                 print(entry.upper(), _type(settings[section][entry]))
        #         except AttributeError as e:
        #             if _VERBOSE:
        #                 print('attribute error: {}'.format(e))
        #             if import_all:  # old method
        #                 try:  # assign the attribute to the best fitting type between float, int and string
        #                     f = float(settings[section][entry])
        #                     i = int(f)
        #                     if f - i == 0.0:
        #                         val = i  # assign Integer
        #                     else:
        #                         val = f  # assign Float
        #                     setattr(self, entry.upper(), val)
        #                 except ValueError:  # assign String
        #                     setattr(
        #                         self, entry.upper(), str(
        #                             settings[section][entry]))
        #             else:
        #                 pass

    def loadSettings(self, settings_file_name, preserve_path=True):
        """ Load settings from an other saved setting file.

        To save settings simply copy paste the SETTINGS.ini file to the
        utilities/settings folder, and rename it. Use this name in this method
        to then load its content to the SETTINGS.ini file.

        Args:
            settings_file_name: str
                Name of the settings file to load.
                This file must be in the folder "hextof-processor/utilities/settings".
            preserve_path: bool | True
                Disables overwriting local file saving paths. Defaults to True.

        """

        root_folder = os.path.dirname(__file__)
        if 'SETTINGS.ini' not in os.listdir(root_folder):
            root_folder = os.path.dirname(root_folder)
        old_settings_file = os.path.join(root_folder, 'SETTINGS.ini')
        new_settings = ConfigParser()
        if settings_file_name[-4:] != '.ini':
            settings_file_name += '.ini'
        new_settings_file = os.path.join(root_folder, 'settings', settings_file_name)
        new_settings.read(new_settings_file)
        if len(new_settings.sections()) == 0:
            print(f'No settings file {settings_file_name} found.')
            available_settings = os.listdir(os.path.join(root_folder, 'settings'))
            print('Available settings files are:', *available_settings, sep='\n\t')
        else:
            if preserve_path:
                old_settings = ConfigParser()
                old_settings.read(old_settings_file)
                new_settings['paths'] = old_settings['paths']
            with open(old_settings_file, 'w') as SETTINGS_file:  # overwrite SETTINGS.ini with the new settings
                new_settings.write(SETTINGS_file)
            print('Loaded settings from {}'.format(settings_file_name))
            # reload settings in the current processor instance
            self.initAttributes()

    # ==================
    # Dataframe creation
    # ==================

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
            try:
                with open(os.path.join(fullName + '_el', 'run_metadata.txt'), 'r') as json_file:
                    self.metadata = json.load(json_file)
            except Exception as err:
                print(f'Failed loading metadata from parquet stored files!, {err}')
        elif format in ['hdf5', 'h5']:
            self.dd = dask.dataframe.read_hdf(
                fullName, '/electrons', mode='r', chunksize=self.CHUNK_SIZE)
            self.ddMicrobunches = dask.dataframe.read_hdf(
                fullName, '/microbunches', mode='r', chunksize=self.CHUNK_SIZE)
        self.printRunOverview()
        print(f'Loaded data form {format} file')

    def appendDataframeParquet(self, fileName, path=None):
        """ Append data to an existing dask Parquet dataframe.

        This can be used to concatenate multiple DAQ runs in one dataframe.
        Data is taken from the dd and dd_microbunch dataframe attributes.

        :Parameter:
            fileName : str
                name (including path) of the folder containing the
                parquet files to append the new data.
        """
        if type(
                fileName) == int:  # if runNumber is given (only works if the run was prevously stored with default naming)
            fileName = 'run{}'.format(fileName)
        if path == None:
            path = self.DATA_PARQUET_DIR
        fullName = path + fileName
        newdd = dask.dataframe.read_parquet(fullName + "_el")
        self.dd = dask.dataframe.concat([self.dd, newdd], join='outer', interleave_partitions=True)
        newddMicrobunches = dask.dataframe.read_parquet(fullName + "_mb")
        self.ddMicrobunches = dask.dataframe.concat([self.ddMicrobunches, newddMicrobunches], join='outer',
                                                    interleave_partitions=True)

    @property
    def binnedArrayShape(self):
        s = []
        for a in self.binAxesList:
            s.append(len(a))
        return tuple(s)

    @property
    def binnedArraySize(self):
        s = []
        for a in self.binAxesList:
            s.append(len(a))
        return np.prod(s) * 64

    def printRunOverview(self):
        """ Print run information, used in readData and readDataParquet 
        """
        i=None
        try:
            i = self.runInfo
        except AttributeError:
            pass
        try:
            i = self.metadata_dict['run']
        except:
            pass                
            
        if i is None:
            print('no run info available.')
        else:
            print(f'Run {i["runNumber"]}')
            try:
                print(f"Started at {i['timeStart']}, finished at {i['timeStop']}, "
                      f"total duration {i['timeDuration']:,} s")
            except:
                pass
            print(f"Macrobunches: {i['numberOfMacrobunches']:,}  "
                  f"from {i['pulseIdInterval'][0]:,} to {i['pulseIdInterval'][1]:,} ")
            print(f"Total electrons: {i['numberOfElectrons']:,}, "
                  f"electrons/Macrobunch {i['electronsPerMacrobunch']:}")

    # ==========================
    # Dataframe column expansion
    # ==========================

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

    def calibrateEnergy(self, toffset=None, eoffset=None, l=None, useAvgSampleBias=False, k_shift_func=None,
                        k_shift_parameters=None, applyJitter=True, jitterAmplitude=4, jitterType='uniform'):
        """ Add calibrated energy axis to dataframe

        Uses the same equation as in tof2energy in calibrate.

        Args:
            toffset : float
                The time offset from the dld clock start to when the fastest photoelectrons reach the detector
            eoffset : float
                The energy offset given by W-hv-V
            l : float
                the effective length of the drift section
            useAvgSampleBias: bool (False)
                uses the average value for the sample bias across the dataset,
                possibly reducing noise, but cannot be used on runs where the
                sample bias was changed
            k_shift_func : function
                function fitting the shifts of energy across the detector.
            k_shift_parameters :
                parameters for the fit function to reproduce the energy shift.
            applyJitter : bool (True)
                if true, applies random noise of amplitude determined by jitterAmplitude
                to the dldTime step values.
            jitterType :
                noise distribution, 'uniform' or 'normal'.
        """
        if toffset is None:
            toffset = float(self.settings['processor']['ET_CONV_T_OFFSET'])
        if eoffset is None:
            eoffset = float(self.settings['processor']['ET_CONV_E_OFFSET'])
        if l is None:
            l = float(self.settings['processor']['ET_CONV_L'])

        self.dd['dldTime_corrected'] = self.dd['dldTime']
        if 'dldSectorId' in self.dd.columns:
            self.dd['dldTime_corrected'] -= self.dd['dldSectorId']

        def correct_dldTime_shift(df, func, *args):
            r = func((df['dldPosX'], df['dldPosY']), *args)
            if self.TOF_IN_NS:
                r /= 0.020576131995767355
            return r

        if k_shift_func is not None and k_shift_parameters is not None:
            self.dd['dldTime_corrected'] += self.dd.map_partitions(correct_dldTime_shift, k_shift_func,
                                                                 *k_shift_parameters)

        if applyJitter:
            self.dd['dldTime_corrected'] = self.dd.map_partitions(dfops.applyJitter, amp=jitterAmplitude,
                                                                  col='dldTime_corrected', type=jitterType)

        if useAvgSampleBias:
            eoffset -= self.dd['sampleBias'].mean()
        else:
            eoffset -= self.dd['sampleBias']

        k = 0.5 * 1e18 * 9.10938e-31 / 1.602177e-19
        self.dd['energy'] = k * np.power(l / ((self.dd['dldTime_corrected'] * self.TOF_STEP_TO_NS) - toffset),
                                         2.) - eoffset

    def calibratePumpProbeTime(self, t0=0, bamSign=1, streakSign=1, invertTimeAxis=True):
        """  Add pumpProbeTime axis to dataframes.

        Correct pump probe time by BAM and/or streak camera

        Args:
            t0: float
                pump probe time overlap
            bamSign: -1,+1
                sign of the bam correction:
                    +1 : pumpProbeTime =  delayStage + bam
                    -1 : pumpProbeTime =  delayStage - bam
                     0 : ignore bam correction
            streakSign: -1,0,+1
                sign of the bam correction:
                    +1 : pumpProbeTime =  delayStage + streakCam
                    -1 : pumpProbeTime =  delayStage - streakCam
                     0 : ignore streakCamera correction
            invertTimeAxis: bool (True)
                invert time direction on pump probe time

        """
        for df in [self.dd, self.ddMicrobunches]:
            df['pumpProbeTime'] = df['delayStage'] - t0

            if 'bam' in df:
                df['pumpProbeTime'] += df['bam'] * bamSign
            if 'streakCamera' in df:
                df['pumpProbeTime'] += df['streakCamera'] * streakSign
            if invertTimeAxis:
                df['pumpProbeTime'] = - df['pumpProbeTime']

    def calibrateMomentum(self, kCenterX=None, kCenterY=None, rotationAngle=None, px_to_k=None, createPolarCoords=True,
                          applyJitter=True, jitterAmp=0.5, jitterType='uniform'):
        """ Add calibrated parallel momentum axes to dataframe.

        Compute the calibration of parallel momentum kx and ky from the detector
        position dldPosX and dldPosY. Optionally, add columns with thethe polar
        coordinates kr and kt.

        Uses the same equation as in tof2energy in calibrate.
        Args:
            kCenterX : float
                dldPosX coordinate of the center of k-space
            kCenterY : float
                dldPosY coordinate of the center of k-space
            rotationAngle : float
                Rotates the momentum coordinates counterclockwise
            px_to_k : float
                Conversion between dldPosX/Y to momentum in inverse Angstroms
            createPolarCoords: bool (True)
                If True, also creates the polar momentum coordinates kr and kt
            applyJitter: bool (True)
                Apply jitter on the original axis to reduce artifacts when binning.
                This is especially necessary when rotating the momentum coordinates.
            jitterAmp: float
                Amplitude of the random jitter applied. Best kept at half the
                axis original spacing. In case of dldPosX and Y, this should be
                kept at 0.5, since they are integer steps.
            jitterType: 'uniform'
                Choose between 'uniform' or 'normal' random distributions. With
                 regularly spaced axes as here, uniform is preferred.
        """
        if kCenterX is None:
            kCenterX = self.K_CENTER_X
        if kCenterY is None:
            kCenterY = self.K_CENTER_Y
        if rotationAngle is None:
            rotationAngle = self.K_ROTATION_ANGLE
        if px_to_k is None:
            px_to_k = self.STEP_TO_K

        if applyJitter:
            X = self.dd.map_partitions(dfops.applyJitter, amp=jitterAmp, col='dldPosX', type=jitterType) - np.float(
                kCenterX)
            Y = self.dd.map_partitions(dfops.applyJitter, amp=jitterAmp, col='dldPosY', type=jitterType) - np.float(
                kCenterY)
        else:
            X = self.dd['dldPosX'] - np.float(kCenterX)
            Y = self.dd['dldPosY'] - np.float(kCenterY)
        sin, cos = np.sin(rotationAngle), np.cos(rotationAngle)

        self.dd['kx'] = px_to_k * (X * cos + Y * sin)
        self.dd['ky'] = px_to_k * (- X * sin + Y * cos)

        if createPolarCoords:
            def radius(df):
                return np.sqrt(np.square(df['kx']) + np.square(df['ky']))

            def angle(df):
                return np.arctan2(df['ky'], df['kx'])

            self.dd['kr'] = self.dd.map_partitions(radius)
            self.dd['kt'] = self.dd.map_partitions(angle)

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

    # ========================
    # Normalization histograms
    # ========================

    def normalizePumpProbeTime(self, data_array, ax='pumpProbeTime',preserve_mean=False):
        # TODO: work on better implementation and accessibility for this method
        """ Normalizes the data array to the number of counts per delay stage step.
            [DEPRECATED] this is buggy... the new normalizeDelay function should be used
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
            norm_array = self.delayStageHistogram

            for i in range(np.ndim(data_array_normalized) - 1):
                norm_array = norm_array[:, None]
            print('normalized pumpProbe data found along axis {}'.format(idx))

            data_array_normalized = data_array_normalized / norm_array
            data_array_normalized = np.swapaxes(data_array_normalized, idx, 0)

            return data_array_normalized

        except ValueError:
            raise ValueError(
                'No pump probe time bin, could not normalize to delay stage histogram.')

    def normalizeDelay(self, data_array, ax=None, preserve_mean=True):
        """ Normalizes the data array to the number of counts per delay stage step.

        :Parameter:
            data_array : numpy array
                data array containing binned data, as created by the ``computeBinnedData`` method.
            ax : str
                name of the axis to normalize to, default is None, which uses as
                normalization axis "pumpProbeTime" if found, otherwise "delayStage"
            preserve_mean : bool | True
                if True, divides the histogram by its mean, preserving the average value of the 
                normalized array.   
        :Raise:
            Throw a ValueError when no pump probe time delay axis is available.

        :Return:
            data_array_normalized : numpy array
                normalized version of the input array.
        """

        if ax is None:
            if 'pumpProbeTime' in self.binNameList:
                ax='pumpProbeTime'
                nhist = self.pumpProbeTimeHistogram.copy()
            elif 'delayStage' in self.binNameList:
                ax='delayStage'
                nhist = self.delayStageHistogram.copy()
            else:
                raise ValueError(f'No axis pump probe or delay stage histogram found, could not normalize.')
        else:
            try:
                nhist = getattr(self,f'{ax}Histogram')
            except:
                raise ValueError(f'No axis {ax} histogram found, could not normalize.')
        idx = self.binNameList.index(ax)
        print(f'normalized {ax} data found along axis {idx}')
        data_array_normalized = np.swapaxes(data_array, 0, idx)
        
        for i in range(np.ndim(data_array_normalized) - 1):
            nhist = nhist[:, None]
            
        data_array_normalized = data_array_normalized / nhist
        if preserve_mean:
            data_array_normalized *= np.mean(nhist)
        data_array_normalized = np.swapaxes(data_array_normalized, idx, 0)

        return data_array_normalized


    def normalizeGMD(self, data_array, axis_name, axis_values):
        """ create the normalization array for normalizing to the FEL intensity at the GMD
        :Parameter:
            data_array: np.ndarray
                data to be normalized
            axis_name:
                name of the axis along which to perform normalization
            axis_values:
                the bins of the axis_name provided.
        :Return:
            normalized_array: np.ndarray
                normalized version of the input array
        """
        print('Normalizing by GMD...')
        try:
            # Find the index of the normalization axis
            idx = self.binNameList.index(axis_name)

            data_array_normalized = np.swapaxes(data_array, 0, idx)

            norm_array = self.make_GMD_histogram(axis_name, axis_values)

            for i in range(np.ndim(data_array_normalized) - 1):
                norm_array = norm_array[:, None]
            data_array_normalized = data_array_normalized / norm_array
            data_array_normalized = np.swapaxes(data_array_normalized, idx, 0)

            return data_array_normalized

        except ValueError:
            raise ValueError('Failed the GMD normalization.')

    def make_GMD_histogram(self, axis_name, axis_values):  # TODO: improve performance... its deadly slow!

        gmd = np.nan_to_num(self.dd['gmdBda'].values.compute())
        axisDataframe = self.dd[axis_name].values.compute()

        norm_array = np.zeros(len(axis_values))
        for j in tqdm(range(0, len(gmd))):
            if (gmd[j] > 0):
                ind = np.argmin(np.abs(axis_values - axisDataframe[j]))
                norm_array[ind] += gmd[j]
        return norm_array

    def normalizeAxisMean(self, data_array, ax):
        """ Normalize to the mean of the given axis.
        
        Args:
            data_array: np.ndarray
                array to be normalized
            ax: int
                axis along which to normalize
        Returns:
            norm_array: np.ndarray
                normalized array
        """
        print("normalizing mean on axis {}".format(ax))
        try:
            # Find the index of the normalization axis
            idx = self.binNameList.index(ax)
            data_array_normalized = np.swapaxes(data_array, 0, idx)
            norm_array = data_array.mean(0)
            norm_array = norm_array[None, :]

            for i in range(np.ndim(data_array_normalized) - 2):
                norm_array = norm_array[:, None]

            data_array_normalized = data_array_normalized / norm_array
            data_array_normalized = np.swapaxes(data_array_normalized, idx, 0)

            return data_array_normalized

        except ValueError as e:
            raise ValueError("Could not normalize to {} histogram.\n{}".format(ax, e))

    def makeNormHistogram(self, name, compute=False):
        if name not in self.binNameList:
            raise ValueError(f'No bin axis {name} found. Cannot create normalization axis')
        else:
            bins = self.binRangeList[self.binNameList.index(name)]

            # self.delaystageHistogram = numpy.histogram(self.delaystage[numpy.isfinite(self.delaystage)], bins)[0]
            histBinner = self.ddMicrobunches[name].map_partitions(pd.cut, bins)
            histGrouped = self.ddMicrobunches.groupby([histBinner])
            # self.pumpProbeHistogram = delaystageHistGrouped.count().compute()['bam'].to_xarray().values.astype(np.float64)
            out = histGrouped.count()['bam'].values  # .astype(np.int32)
            if compute:
                print(f'Computing normalization array along {name}:')
                with ProgressBar():
                    out = out.compute()
            return out

    @property
    def pumpProbeTimeHistogram(self):
        """ Easy access to pump probe normalization array.
        Mostly for retrocompatibility"""
        try:
            if isinstance(self.histograms['pumpProbeTime'], dask.array.core.Array):
                print(f'Computing normalization array along pumpProbeTime')
                with ProgressBar():
                    self.histograms['pumpProbeTime'] = self.histograms['pumpProbeTime'].compute()
            return self.histograms['pumpProbeTime']
        except KeyError:
            return [None]

    @property
    def delayStageHistogram(self):
        """ Easy access to pump probe normalization array.
        Mostly for retrocompatibility"""
        try:
            if isinstance(self.histograms['delayStage'], dask.array.core.Array):
                print(f'Computing normalization array along delayStage')
                with ProgressBar():
                    self.histograms['delayStage'] = self.histograms['delayStage'].compute()
            return self.histograms['delayStage']
        except KeyError:
            return [None]
        
    # ==========================
    # Binning
    # ==========================

    def addFilter(self, colname, lb=None, ub=None):
        """ Filters the dataframes contained in the processor instance.

        Filters the columns of ``dd`` and ``ddMicrobunches`` dataframes in place.

        **Parameters**\n
        colname (str): name of the column in the dask dataframes
        lb (:obj:`float',optional):  lower bound of the filter
            if :None: (default), ignores lower boundary
        ub (:obj:`float',optional):  upper bound of the filter
            if :None: (default), ignores upper boundary
        
        **Attention**\n
        This is an irreversible process, since the dataframe gets overwritten.
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

        **Parameters**\n
        start: float
            Position of first bin
        end: float
            Position of last bin (not included!)
        steps: float
            Define the bin size. If useStepSize=True (default),
            this is the step size, while if useStepSize=False, then this is the
            number of bins. In Legacy mode (force_legacy=True, or
            processor._LEGACY_MODE=True)
        useStepSize: bool | True
            Tells python to interpret steps as a step size if
            True, or as the number of steps if False
        forceEnds: bool | False
            Tells python to give priority to the end parameter
            rather than the step parameter (see above for more info)
        include_last: bool | True
            Closes the interval on the right when true. If
            using step size priority, will expand the interval to include
            the next value when true, will shrink the interval to contain all
            points within the bounds if false.
        force_legacy: bool | False
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
            n_bins = int(round((abs(end - start)) / steps)) + 1
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
                   include_last=True, force_legacy=False, compute_histograms=False):
        """ Add binning of one dimension, to be then computed with ``computeBinnedData`` method.

        Creates a list of bin names, (binNameList) to identify the axis on
        which to bin the data. Output array dimensions order will be the same
        as in this list. The attribute binRangeList will contain the ranges of
        the binning used for the corresponding dimension.

        **Parameters**\n
        name: str
            Name of the column to apply binning to. Possible column names are`:`
            posX, posY, dldTime, pumpProbeTime, dldDetector, etc.
        start: float
            Position of first bin
        end: float
            Position of last bin (not included!)
        steps: float
            The bin size, if useStepSize=True (default),
            this is the step size, while if useStepSize=False, then this is the
            number of bins. In Legacy mode (force_legacy=True, or
            processor._LEGACY_MODE=True)
        useStepSize: bool | True
            Tells Python how to interpret steps.
            
            :True: interpret steps as a step size.
            :False: interpret steps as the number of steps.
        forceEnds: bool | False
            Tells python to give priority to the end parameter
            rather than the step parameter (see genBins for more info)
        include_last: bool | True
            Closes the interval on the right when true. If
            using step size priority, will expand the interval to include
            the next value when true, will shrink the interval to contain all
            points within the bounds if false.
        force_legacy: bool | False
            :True: use np.arange method to generate bins.
            :False: use np.linspace method to generate bins.
                
        **Return**\n
        axes: numpy array
            axis of the binned dimesion. The points defined on this axis are the middle points of
            each bin.
                
        **Note**\n
        If the name is 'pumpProbeTime': sets self.delaystageHistogram for normalization.
        
        .. seealso::
        
          ``computeBinnedData`` Method to compute all bins created with this function.

        """

        # write the parameters to the bin list:
        if name in ['dldTime'] and self.TOF_IN_NS:
            start = round(start/self.TOF_STEP_TO_NS)
            end = round(end/self.TOF_STEP_TO_NS)
            if useStepSize is True:
                # division by 8 is necessary since the first 3 bits of the channel where these values are
                # taken from is used for other purpouses. Therefore the real tof step is:
                steps = round(steps/self.TOF_STEP_TO_NS/8)*8 
                steps = max(steps,8)

        bins = self.genBins(start, end, steps, useStepSize, forceEnds, include_last, force_legacy)
        self.binNameList.append(name)
        self.binRangeList.append(bins)
        axes = np.array([np.mean((x, y)) for x, y in zip(bins[:-1], bins[1:])])

        if name in ['dldTime'] and self.TOF_IN_NS:
            axes *= self.TOF_STEP_TO_NS

        # TODO: could be improved for nonlinear scales
        self.binAxesList.append(axes)

        if name in ['pumpProbeTime', 'delayStage']:
            # add the normalization histogram to the histograms dictionary. computes them if requested, otherwise
            # only assigned the dask calculations for later computation.
            self.histograms[name] = self.makeNormHistogram(name, compute=compute_histograms)
            # These can be accessed in the old method through the class properties pumpProbeHistogram and delayStageHistogram

        return axes

    def resetBins(self):
        """ Reset the bin list """
        self.histograms = {}
        self.binNameList = []
        self.binRangeList = []
        self.binAxesList = []

    def computeBinnedData(self, saveAs=None, return_xarray=None, force_64bit=False, skip_metadata=True, fast_metadata=False, usePbar=True):
        """ Use the bin list to bin the data.
        
        **Parameters**\n
        saveAs: str | None
            full file name where to save the result (forces return_xarray
            to be true).
        return_xarray: bool
            if true, returns and xarray with all available axis and metadata
            information attached, otherwise a numpy.array.
        
        **Returns**\n
        result: numpy.array or xarray.DataArray
            A numpy array of float64 values. Number of bins defined will define the
            dimensions of such array.

        **Notes**\n
        postProcess method must be used before computing the binned data if binning
        along pumpProbeDelay or polar k-space coordinates.
        """
        if return_xarray is None:
            try:
                return_xarray = self.RETURN_XARRAY
            except:
                return_xarray = True


        def analyzePart(part):
            """ Function called by each thread of the analysis.

            Old deprecated method
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
            """ Function called by each thread of the analysis.
            
            **Parameter**\n
            part: partition
                partition to process.
            
            **Returns**\n
            res: numpy array
                binned array calculated from this partition.
            """
            # get the data as numpy:
            vals = part.values
            cols = part.columns.values
            # create array of columns to be used for binning
            colsToBin = []
            for binName in self.binNameList:
                idx = cols.tolist().index(binName)
                colsToBin.append(idx)

            #            # create the array with the bins and bin ranges
            #            numBins = []
            #            ranges = []
            #            for i in range(0, len(colsToBin)):
            #                # need to subtract 1 from the number of bin ranges
            #                numBins.append(len(self.binRangeList[i]) - 1)
            #                ranges.append(
            #                    (self.binRangeList[i].min(),
            #                     self.binRangeList[i].max()))
            #            # now we are ready for the analysis with numpy:
            #            res, edges = np.histogramdd(
            #                vals[:, colsToBin], bins=numBins, range=ranges)
            res, edges = np.histogramdd(vals[:, colsToBin], bins=self.binRangeList)
            return res

        # prepare the partitions for the calculation in parallel
        calculatedResults = []

        if _VERBOSE:
            warnString = "always"
        else:
            warnString = "ignore"
        with warnings.catch_warnings():
            warnings.simplefilter(warnString)

            for i in tqdm_notebook(range(0, self.dd.npartitions, self.N_CORES),disable=not usePbar):
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

        if force_64bit:
            result = result.astype(np.float64)

        if return_xarray or saveAs:
            
            try:
                if skip_metadata: 
                    raise KeyError('forced to skip metadata creation')
                else:
                    metadata = self.get_metadata(fast_mode=fast_metadata)
            except KeyError as err:
                print(f'Failed creating metadata: {err}')
                metadata = None
            result = res_to_xarray(result, self.binNameList, self.binAxesList, metadata)

        if saveAs is not None:
            pass  # TODO: Make saving function
            # self.save_binned(result, saveName, path=savePath, mode='w')

        return result

    def get_metadata(self, fast_mode=False):
        """  Creates a dictionary with the most relevant metadata.

        **Args**\n
        fast_mode: bool | False
            if False skips the heavy computation steps which take a long time.
        
        **Returns**\n
        metadata: dict
            dictionary with metadata information
        # TODO: distribute metadata generation in the appropriate methods.
        """
        print('Generating metadata...')
        metadata = {}
        try:
            start, stop = self.startEndTime[0], self.startEndTime[1]
        except AttributeError:
            if not fast_mode:
                start, stop = self.dd['timeStamp'].min().compute(), self.dd['timeStamp'].max().compute()
            else:
                start, stop = 0, 1

        metadata['timing'] = {'acquisition start': datetime.fromtimestamp(start).strftime('%Y-%m-%d %H:%M:%S'),
                              'acquisition stop': datetime.fromtimestamp(stop).strftime('%Y-%m-%d %H:%M:%S'),
                              'acquisition duration': stop - start,
                              # 'bin array creation': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                              }
        metadata['sample'] = self.sample
        metadata['settings'] = misc.parse_category('processor')
        metadata['DAQ channels'] = misc.parse_category('DAQ channels')
        if self.pulseIdInterval is None and not fast_mode:
            pulseIdFrom = self.dd['macroBunchPulseId'].min().compute()
            pulseIdTo = self.dd['macroBunchPulseId'].max().compute()
        else:
            pulseIdFrom, pulseIdTo = self.pulseIdInterval[0], self.pulseIdInterval[1]

        metadata['run'] = {
            'runNumber': self.runNumber,
            'macroBunchPulseIdInterval': [pulseIdFrom, pulseIdTo],
            'nMacrobunches': pulseIdTo - pulseIdFrom,
        }
        try:
            metadata['run']['nElectrons'] = self.numOfElectrons
            metadata['run']['electronsPerMacrobunch'] = self.electronsPerMacrobunch,
        except:
            pass  # TODO: find smarter solution

        metadata['histograms'] = {}

        if hasattr(self, 'delaystageHistogram'):
            metadata['histograms']['delay'] = {'axis': 'delayStage', 'histogram': self.delaystageHistogram}
        elif hasattr(self, 'pumpProbeHistogram'):
            metadata['histograms']['delay'] = {'axis': 'pumpProbeDelay', 'histogram': self.pumpProbeTimeHistogram}

        # if not fast_mode:
        #     try:
        #         axis_values = []
        #         ax_len = 0
        #         for ax, val in zip(self.binNameList, self.binAxesList):
        #             if len(val) > ax_len:
        #                 ax_len = len(val)
        #                 axis_name = ax
        #                 axis_values = val
        #
        #         GMD_norm = self.make_GMD_histogram(axis_name, axis_values)
        #         metadata['histograms']['GMD'] = {'axis': axis_name, 'histogram': GMD_norm}
        #     except Exception as e:
        #         print("Couldn't find GMD channel for making GMD normalization histograms\nError: {}".format(e))
        print('...done!')
        return metadata

    def res_to_xarray_old(self, res, fast_mode=False):
        """ Creates a BinnedArray (xarray subclass) out of the given numpy.array.
        
        **Parameters**\n
        res: np.array
            nd array of binned data
        fast_mode: bool default True
            if True, it skips the creation of metadata element which require computation.
        
        **Returns**\n
        ba: BinnedArray (xarray)
            an xarray-like container with binned data, axis, and all available metadata.
        """
        dims = self.binNameList
        coords = {}
        for name, vals in zip(self.binNameList, self.binAxesList):
            coords[name] = vals

        ba = BinnedArray(res, dims=dims, coords=coords)

        units = {}
        default_units = {'dldTime': 'step', 'delayStage': 'ps', 'pumpProbeDelay': 'ps'}
        for name in self.binNameList:
            try:
                u = default_units[name]
            except KeyError:
                u = None
            units[name] = u
        ba.attrs['units'] = units

        try:
            start, stop = self.startEndTime[0], self.startEndTime[1]
        except AttributeError:
            if not fast_mode:
                start, stop = self.dd['timeStamp'].min().compute(), self.dd['timeStamp'].max().compute()
            else:
                start, stop = 0, 1

        ba.attrs['timing'] = {'acquisition start': datetime.fromtimestamp(start).strftime('%Y-%m-%d %H:%M:%S'),
                              'acquisition stop': datetime.fromtimestamp(stop).strftime('%Y-%m-%d %H:%M:%S'),
                              'acquisition duration': stop - start,
                              'bin array creation': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                              }
        ba.attrs['sample'] = self.sample
        ba.attrs['settings'] = misc.parse_category('processor')
        ba.attrs['DAQ channels'] = misc.parse_category('DAQ channels')
        if self.pulseIdInterval is None:
            pulseIdFrom = self.dd['macroBunchPulseId'].min().compute()
            pulseIdTo = self.dd['macroBunchPulseId'].max().compute()
        else:
            pulseIdFrom, pulseIdTo = self.pulseIdInterval[0], self.pulseIdInterval[1]

        ba.attrs['run'] = {
            'runNumber': self.runNumber,
            'macroBunchPulseIdInterval': [pulseIdFrom, pulseIdTo],
            'nMacrobunches': pulseIdTo - pulseIdFrom,
        }
        try:
            ba.attrs['run']['nElectrons'] = self.numOfElectrons
            ba.attrs['run']['electronsPerMacrobunch'] = self.electronsPerMacrobunch,
        except:
            pass  # TODO: find smarter solution

        ba.attrs['histograms'] = {}

        if hasattr(self, 'delaystageHistogram'):
            ba.attrs['histograms']['delay'] = {'axis': 'delayStage', 'histogram': self.delaystageHistogram}
        elif hasattr(self, 'pumpProbeHistogram'):
            ba.attrs['histograms']['delay'] = {'axis': 'pumpProbeDelay', 'histogram': self.pumpProbeTimeHistogram}
        if not fast_mode:
            try:
                axis_values = []
                ax_len = 0
                for ax, val in coords.items():
                    if len(val) > ax_len:
                        ax_len = len(val)
                        axis_name = ax
                        axis_values = val

                GMD_norm = self.make_GMD_histogram(axis_name, axis_values)
                ba.attrs['histograms']['GMD'] = {'axis': axis_name, 'histogram': GMD_norm}
            except Exception as e:
                print("Couldn't find GMD channel for making GMD normalization histograms\nError: {}".format(e))

        return ba

    def computeBinnedDataMulti(self, saveName=None, savePath=None,
                               rank=None, size=None):
        """ Use the bin list to bin the data. Cluster-compatible version (Maciej Dendzik)
        
        **Parameters**\n
        saveName: str | None
            filename
        savePath: str | None
            file path
        rank: int | None
            Rank number of cluster computer
        size: int | None
            Size of partition
        
        **Return**\n
        result: numpy array
            A numpy array of float64 values. The number of bins determines the
            dimensionality of the output array.

        **Notes**\n
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

    def save_binned(self, binnedData, file_name, path=None, mode='w'):
        """ Save a binned numpy array to h5 file. The file includes the axes
        (taken from the scheduled bins) and the delay stage histogram, if it exists.

        **Parameters**\n
        binnedData: numpy array
            Binned multidimensional data.
        file_name: str
            Name of the saved file. The extension '.h5' is automatically added.
        path: str | None
            File path.
        mode: str | 'w'
            Write mode of h5 file ('w' = write).
        """
        _abort = False
        if path is None:
            path = self.DATA_H5_DIR
        if not os.path.isdir(path):  # test if the path exists...
            answer = input("The folder {} doesn't exist,"
                           "do you want to create it? [y/n]".format(path))
            if 'y' in answer:
                os.makedirs(path)
            else:
                _abort = True

        filename = '{}.h5'.format(file_name)
        if os.path.isfile(path + filename):
            answer = input("A file named {} already exists. Overwrite it? "
                           "[y/n or r for rename]".format(filename))
            if answer.lower() in ['y', 'yes', 'ja']:
                pass
            elif answer.lower() in ['n', 'no', 'nein']:
                _abort = True
            else:
                filename = input("choose a new name:")

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
                    for i in range(pp_data.shape[0]):  # otherwise make a dataset for each time frame.
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
                        data=self.pumpProbeTimeHistogram)

    @staticmethod
    def load_binned(file_name, mode='r', ret_type='list'):
        """ Load an HDF5 file saved with ``save_binned()`` method.
        wrapper for function utils.load_binned_h5()

        **Parameters**\n
        file_name: str
            name of the file to load, including full path
        mode: str | 'r'
            Read mode of h5 file ('r' = read).
        ret_type: str | 'list','dict'
            output format for axes and histograms:
            'list' generates a list of arrays, ordered as
            the corresponding dimensions in data. 'dict'
            generates a dictionary with the names of each axis.

        **Returns**\n
        data: numpy array
            Multidimensional data read from h5 file.
        axes: numpy array
            The axes values associated with the read data.
        hist: numpy array
            Histogram values associated with the read data.
        """
        return misc.load_binned_h5(file_name, mode=mode, ret_type=ret_type)

    # % retro-compatibility functions and deprecated methods

    def load_settings(self, settings_file_name, preserve_path=True):
        """ Retrocompatibility naming"""
        return self.loadSettings(settings_file_name, preserve_path=preserve_path)

    def deleteBinners(self):
        """ **[DEPRECATED]** use resetBins() instead
        """

        print('WARNING: deleteBinners method has been renamed to resetBins.')
        self.resetBins()

    def readDataframesParquet(self, fileName=None):
        """ **[DEPRECATED]** Load data from a dask Parquet dataframe.
        Use readDataframesParquet instead.

        **Parameter**\n
        fileName: str | None
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

    def read_h5(self, h5FilePath):
        """ [DEPRECATED] Read the h5 file at given path and return the contained data.

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
