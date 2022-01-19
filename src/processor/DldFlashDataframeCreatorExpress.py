from processor.DldProcessor import DldProcessor
import sys, os
import glob
import json
import h5py
import numpy as np
from pandas import Series, DataFrame, concat, MultiIndex
from dask import delayed, compute
import dask.dataframe as dd
from dask.diagnostics import ProgressBar
from pathlib import Path
from functools import reduce
from configparser import ConfigParser
from multiprocessing import Pool, cpu_count
from itertools import compress

"""
    author:: Muhammad Zain Sohail, Steinn Ymir Agustsson
    Some functions taken or adapted from
    https://gitlab.desy.de/christopher.passow/flash-daq-hdf/
"""

# assert sys.version_info >= (3,8), f"Requires at least Python version 3.8,\
#     but was {sys.version}"

class DldFlashProcessorExpress(DldProcessor):
    """  
    The class generates multiindexed multidimensional pandas dataframes 
    from the new FLASH dataformat resolved by both macro and microbunches alongside electrons.
    """
    def __init__(self, runNumber = None, channels = None, settings = None, beamtime_dir=None, 
                parquet_path=None, parquet_dir=None, beamtime_id=None, year=None, daq="fl1user2", silent=False):
        super().__init__(settings=settings,silent=silent)
        self.runNumber = runNumber
        
        # Parses and stores the channel names that are defined by the json file
        if channels is None:
            all_channel_list_dir = os.path.join(Path(__file__).parent.absolute(), "channels.json")
        else:
            all_channel_list_dir = channels
        # Read all channel info from a json file
        with open(all_channel_list_dir, "r") as json_file:
            self.all_channels = json.load(json_file)
        self.channels = self.availableChannels # Set all channels, exluding pulseId as default
        
        # Prases to locate the raw beamtime directory from settings file 
        if 'paths' in self.settings.keys():
            self.DATA_RAW_DIR = Path(self.settings['paths']['data_raw_dir'])
        else:    
            if beamtime_dir is None:
                if beamtime_id is None:
                    beamtime_id = self.settings['processor']['beamtime_id']
                if year is None:
                    year = self.settings['processor']['year']
                if beamtime_id is None or year is None:
                    raise ValueError('Either the beamtime_dir or beamtime_id and year or a settings file\
                    containing such info is needed to find the data.')
                self.beamtime_dir = Path(f'/asap3/flash/gpfs/pg2/{year}/data/{beamtime_id}/')

            else:
                self.beamtime_dir = Path(beamtime_dir)

            # Folder naming convention till end of October
            self.DATA_RAW_DIR = self.beamtime_dir.joinpath('raw/hdf/express')
            # Use new convention if express doesn't exist
            if not self.DATA_RAW_DIR.exists(): 
                self.DATA_RAW_DIR = self.beamtime_dir.joinpath(f'raw/hdf/{daq.upper()}')
        
        # Parses and creates directory to store parquet files
        if 'paths' in self.settings.keys():
            self.DATA_PARQUET_DIR = Path(self.settings['paths']['data_parquet_dir'])
        else:
            if parquet_dir is None:
                if parquet_path is None:
                    self.parquet_path = 'processed/parquet'
                self.DATA_PARQUET_DIR = self.beamtime_dir.joinpath(self.parquet_path)
            else:
                self.DATA_PARQUET_DIR = Path(parquet_dir)

            if not self.DATA_PARQUET_DIR.exists():
                os.mkdir(self.DATA_PARQUET_DIR)   
         
    @property
    def removeChannels(self, channel_names):
        """Removes the unnecessary channels from the available channels
        using list of channels to remove"""
        for channels in channel_names:
            self.all_channels.pop(channels, None)
        self.channels = self.availableChannels # Set all channels, exluding pulseId as default
        return self.channels

    @property
    def addChannels(self, channel_dict):
        """Add new channels using a dict format defined by:
        "channel_name": {
            "format": "per_pulse" | "per_train" | "per_electron",
            "group_name": "channel_group_path",
            "slice": ":"
        }
        """
        self.all_channels.update(channel_dict)
        self.channels = self.availableChannels # Set all channels, exluding pulseId as default
        return self.channels

    @property
    def availableChannels(self):
        """Returns the channel names that are available for use, 
        excluding pulseId, defined by the json file"""
        available_channels = list(self.all_channels.keys())
        available_channels.remove('pulseId')
        return available_channels
    
    @property
    def channelsPerPulse(self):
        """Returns a list of channels with per_pulse format, 
        including all auxillary channels"""
        channels_per_pulse = []
        for key in self.availableChannels:
            if self.all_channels[key]['format'] == 'per_pulse':
                if key == 'dldAux':
                    for aux_key in self.all_channels[key]['dldAuxChannels'].keys():
                        channels_per_pulse.append(aux_key)
                else:    
                    channels_per_pulse.append(key)
        return channels_per_pulse
    
    @property
    def channelsPerElectron(self):
        """Returns a list of channels with per_electron format"""
        return [key for key in self.availableChannels 
                if self.all_channels[key]['format'] == 'per_electron']
    
    @property
    def channelsPerTrain(self):
        """Returns a list of channels with per_train format"""
        return [key for key in self.availableChannels 
                if self.all_channels[key]['format'] == 'per_train']

    def resetMultiIndex(self):
        """Resets the index per pulse and electron"""
        self.index_per_electron = None
        self.index_per_pulse = None

    def createMultiIndexPerElectron(self, h5_file):
        """Creates an index per electron using pulseId 
        for usage with the electron resolved pandas dataframe"""

        # Macrobunch IDs obtained from the pulseId channel
        [train_id, np_array] = self.createNumpyArrayPerChannel(h5_file, "pulseId")

        # Create a series with the macrobunches as index and microbunches as values
        macrobunches = Series((np_array[i] for i in train_id.index),
            name="pulseId",
            index=train_id) - self.UBID_OFFSET

        # Explode dataframe to get all microbunch vales per macrobunch,
        # remove NaN values and convert to type int
        microbunches = macrobunches.explode().dropna().astype(int)
        
        # Create temporary index values 
        index_temp = MultiIndex.from_arrays((microbunches.index, microbunches.values),
                    names=["trainId", "pulseId"])

        # Calculate the electron counts per pulseId
        # unique preserves the order of appearance
        electron_counts = index_temp.value_counts()[index_temp.unique()].values

        # Series object for indexing with electrons
        electrons = Series([np.arange(electron_counts[i]) 
                            for i in range(electron_counts.size)]).explode()

        # Create a pandas multiindex using the exploded datasets
        self.index_per_electron = MultiIndex.from_arrays(
            (microbunches.index, microbunches.values, electrons),
            names=["trainId", "pulseId", 'electronId'])

    def createMultiIndexPerPulse(self, train_id, np_array):
        """Creates an index per pulse using a pulse resovled channel's 
        macrobunch ID, for usage with the pulse resolved pandas dataframe"""

        # Create a pandas multiindex, useful to compare electron and 
        # pulse resolved dataframes
        self.index_per_pulse = MultiIndex.from_product(
            (train_id, np.arange(0, np_array.shape[1])),
            names=["trainId", "pulseId"])

    def createNumpyArrayPerChannel(self, h5_file, channel):
        """Returns a numpy Array for a given channel name for a given file"""
        # Get the data from the necessary h5 file and channel
        group = h5_file[self.all_channels[channel]["group_name"]]
        channel_dict = self.all_channels[channel]  # channel parameters

        train_id = Series(group["index"], name="trainId")  # macrobunch
        # unpacks the timeStamp or value
        if channel == "timeStamp":
            np_array = group["time"][()]
        else:
            np_array = group["value"][()]

        # Uses predefined axis and slice from the json file
        # to choose correct dimension for necessary channel
        if "axis" in channel_dict:
            np_array = np.take(
                np_array, channel_dict["slice"], axis=channel_dict["axis"])
        return train_id, np_array

    def createDataframePerChannel(self, h5_file, channel):
        """Returns a pandas DataFrame for a given channel name for
        a given file. The Dataframe contains the MultiIndex and returns 
        depending on the channel's format"""
        [train_id, np_array] = self.createNumpyArrayPerChannel(
            h5_file, channel)  # numpy Array created
        channel_dict = self.all_channels[channel]  # channel parameters
        
        # If np_array is size zero, fill with NaNs
        if np_array.size == 0:
            np_array = np.full_like(train_id, np.nan, dtype = np.double)
            return Series((np_array[i] for i in train_id.index), name = channel, 
                          index = train_id)
                    
        # Electron resolved data is treated here
        if channel_dict["format"] == "per_electron":
            # Creates the index_per_electron if it does not exist for a given file
            if self.index_per_electron is None:
                self.createMultiIndexPerElectron(h5_file)

            # The microbunch resolved data is exploded and converted to dataframe, 
            # afterwhich the MultiIndex is set 
            # The NaN values are dropped, alongside the pulseId = 0 (meaningless)
            return (Series((np_array[i] for i in train_id.index), name=channel)
                .explode()
                .dropna()
                .to_frame()
                .set_index(self.index_per_electron)
                .drop(index = np.arange(-self.UBID_OFFSET, 0), level = 1, errors = 'ignore'))
        
        
        # Pulse resolved data is treated here
        elif channel_dict["format"] == "per_pulse":
            # Special case for auxillary channels which checks the channel dictionary 
            # for correct slices and creates a multicolumn pandas dataframe
            if channel == "dldAux":
                # The macrobunch resolved data is repeated 499 times to be
                # comapred to electron resolved data for each auxillary channel
                # and converted to a multicolumn dataframe     
                data_frames = (
                    Series((np_array[i, value] for i in train_id.index),
                    name=key,
                    index=train_id)
                    .to_frame()
                    for key, value in channel_dict["dldAuxChannels"].items())

                # Multiindex set and combined dataframe returned
                return reduce(DataFrame.combine_first, data_frames)
            
            else:
                # For all other pulse resolved channels, macrobunch resolved 
                # data is exploded to a dataframe and the MultiIndex set
            
                # Creates the index_per_pulse for the given channel
                self.createMultiIndexPerPulse(train_id, np_array)
                return (Series((np_array[i] for i in train_id.index), name=channel)
                    .explode()
                    .to_frame()
                    .set_index(self.index_per_pulse))

        elif channel_dict["format"] == "per_train":
            return (Series((np_array[i] for i in train_id.index), name=channel)
                .to_frame()
                .set_index(train_id))
        
        else:
            raise ValueError(channel + "has an undefined format. Available formats are \
                per_pulse, per_electron and per_train")

    def concatenateChannels(self, h5_file, format_=None):
        """Returns a concatenated pandas DataFrame for either all pulse
        resolved or all electron resolved channels."""
        valid_names = [each_name
            for each_name in self.channels
            if each_name in self.all_channels]  # filters for valid channels
        # Only channels with the defined format are selected and stored 
        # in an iterable list
        if format_ is not None:
            channels = [each_name
                for each_name in valid_names
                if self.all_channels[each_name]["format"] == format_]
        else:
            channels = [each_name for each_name in valid_names]

        # if the defined format has channels, returns a concatenatd Dataframe.
        # Otherwise returns empty Dataframe.
        if channels:
            data_frames = (
                self.createDataframePerChannel(h5_file, each)
                for each in channels) 
            return reduce(lambda left, right: left.join(right, how='outer'), data_frames)

    def createDataframePerFile(self, file_path):
        """Returns two pandas DataFrames constructed for the given file.
        The DataFrames contains the datasets from the iterable in the
        order opposite to specified by channel names. One DataFrame is 
        pulse resolved and the other electron resolved.
        """
        # Loads h5 file and creates two dataframes
        with h5py.File(file_path, "r") as h5_file:
            self.resetMultiIndex()  # Reset MultiIndexes for next file
            return self.concatenateChannels(h5_file) 
          
    def runFilesNames(self, run_number, daq, raw_data_dir):
        """Returns all filenames of given run located in directory for the given daq."""
        stream_name_prefixes = {"pbd": "GMD_DATA_gmd_data",
                                "pbd2": "FL2PhotDiag_pbd2_gmd_data",
                                "fl1user1": "FLASH1_USER1_stream_2",
                                "fl1user2": "FLASH1_USER2_stream_2",
                                "fl1user3": "FLASH1_USER3_stream_2",
                                "fl2user1": "FLASH2_USER1_stream_2",
                                "fl2user2": "FLASH2_USER2_stream_2"}
        date_time_section = lambda filename: str(filename).split("_")[-1]
        return sorted(Path(raw_data_dir)
            .glob(f"{stream_name_prefixes[daq]}_run{run_number}_*.h5"),
            key=date_time_section)
    
    def h5_to_parquet(self, h5, prq):
        try:
            (self.createDataframePerFile(h5)
            .reset_index(level=['trainId', 'pulseId','electronId'])
            .to_parquet(prq, compression = None, index = False))
        except ValueError as e:
            self.failed_str.append(f'{prq}: {e}')
            self.prq_names.remove(prq)
            
    def fillNA(self):
        """Routine to fill the NaN values with intrafile forward filling. """
        # First use forward filling method to fill each file's pulse and train resolved channels.
        channels = self.channelsPerPulse + self.channelsPerTrain
        for i in range(len(self.dfs)):
            self.dfs[i][channels] = self.dfs[i][channels].fillna(method="ffill")
        
        # This loop forward fills between the consective files. 
        # The first run file will have NaNs, unless another run before it has been defined.
        for i in range(1, len(self.dfs)):
            subset = self.dfs[i][channels] # Take only pulse channels
            is_null = subset.loc[0].isnull().values.compute() # Find which column(s) contain NaNs.
            # Statement executed if there is more than one NaN value in the first row from all columns
            if is_null.sum() > 0: 
                # Select channel names with only NaNs
                channels_to_overwrite = list(compress(channels, is_null[0]))
                # Get the values for those channels from previous file
                values = self.dfs[i-1][channels].tail(1).values[0]
                # Fill all NaNs by those values
                subset[channels_to_overwrite] = subset[channels_to_overwrite].fillna(
                                                                dict(zip(channels_to_overwrite, values)))
                # Overwrite the dataframes with filled dataframes
                self.dfs[i][channels] = subset

    def readData(self, runs=None, ignore_missing_runs=False, settings=None, channels=None,
             beamtime_dir=None, parquet_path=None, beamtime_id=None, year=None,
            daq="fl1user2"):
        """ Read express data from DAQ, generating a parquet in between.

        Args:
            runs: int | list
                run number or list of run numbers to load
            ignore_missing_runs: bool
                if False, rises FileNotFoundError in case files for a run are not available.
            settings: str | path
                pointer to the ini settings file, handeled by the dldProcessor class. It can
                be the name of a default settings file found in the settings dir of the repo,
                or the path to a specific settings file.
            channels: list
                list of channel names to include in the dataframe. if none defaults to all available channels
            beamtime_dir: str | path
                path to the raaw data. If none, its inferred from the settings file
            parquet_path: str | path
                path relative to beamtime_dir where to storethe parquet files. Defaults to "beamtime_dir/processed/parquet"
            beamtime_id: int
                the id of the beamtime. If none it is inferred from settings
            year: int
                the year of the beamtime. If none it is inferred from settings
            daq: str
                the daq containig the data. If none it is inferred from settings
                
        returns:
            prc: DldProcessor
                returns an instance of the processor class, with electron and pulse dataframes loaded.
        """
        if (self.runNumber or runs) is None:
            raise ValueError('Must provide a run or list of runs!')
                        
        if not runs:
            runs = self.runNumber 
            
        # create a per_file directory
        self.temp_parquet_dir = self.DATA_PARQUET_DIR.joinpath('per_file')
        if not self.temp_parquet_dir.exists():
            os.mkdir(self.temp_parquet_dir)

        # Prepare a list of names for the files to read and parquets to write
        try: 
            runs_str = f'Runs {runs[0]} to {runs[-1]}'
        except TypeError:
            runs_str = f'Run {runs}'
            runs = [runs]
        parquet_name = f'{self.temp_parquet_dir}/'
        all_files = []
        for run in runs:
            files = self.runFilesNames(run, daq, self.DATA_RAW_DIR)
            [all_files.append(f) for f in files]
            if len(files) == 0 and not ignore_missing_runs:
                raise FileNotFoundError(f'No file found for run {run}')

        self.prq_names = [parquet_name + all_files[i].stem for i in range(len(all_files))]
        missing_files = []
        missing_prq_names = []
        
        # only read and write files which were not read already 
        for i in range(len(self.prq_names)): 
            if not Path(self.prq_names[i]).exists():
                missing_files.append(all_files[i])
                missing_prq_names.append(self.prq_names[i])
        
        print(f'Reading {runs_str}: {len(missing_files)} new files of {len(all_files)} total.')
        self.failed_str = []
        
        self.resetMultiIndex()  # initializes the indices for h5_to_parquet
        
        # Set cores for multiprocessing
        N_CORES = len(missing_files)
        if N_CORES > cpu_count() - 1:
            N_CORES = cpu_count() - 1
        
        # Read missing files using multiple cores
        if len(missing_files) > 0:
            with Pool(processes=N_CORES) as pool:    
                pool.starmap(self.h5_to_parquet, tuple(zip(missing_files, missing_prq_names)))
                            
        if len(self.failed_str)>0:
            print(f'Failed reading {len(self.failed_str)} files of{len(all_files)}:')
            for s in self.failed_str:
                print(f'\t- {s}')
        if len(self.prq_names)==0:
            raise ValueError('No data available. Probably failed reading all h5 files')
        else:
            print(f'Loading {len(self.prq_names)} dataframes. Failed reading {len(all_files)-len(self.prq_names)} files.')  
            self.dfs = [dd.read_parquet(fn) for fn in self.prq_names]
            self.fillNA()
            df = dd.concat(self.dfs)
            df_electron = df.dropna(subset=self.channelsPerElectron)
            pulse_columns = ['trainId','pulseId','electronId'] + self.channelsPerPulse
            df_pulse = df[pulse_columns]
            df_pulse = df_pulse[(df_pulse['electronId']==0)|(np.isnan(df_pulse['electronId']))]

        self.dd  = df_electron.repartition(npartitions=len(self.prq_names))
        self.ddMicrobunches = df_pulse.repartition(npartitions=len(self.prq_names))
