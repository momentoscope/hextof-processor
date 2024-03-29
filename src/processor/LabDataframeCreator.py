from typing import Iterable, Union,Sequence
from processor.DldProcessor import DldProcessor
from processor.utilities import misc
import sys, os
import glob
import json
import h5py
import numpy as np
from pandas import Series, DataFrame, concat, MultiIndex, read_parquet
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
"""

# assert sys.version_info >= (3,8), f"Requires at least Python version 3.8,\
#     but was {sys.version}"

class LabDataframeCreator(DldProcessor):
    """  
    The class generates multidimensional pandas dataframes 
    from the lab data resolved by both macro and microbunches alongside electrons.
    """
    def __init__(self, path = None, filenames = None, channels = None, settings = None, silent=False):
        
        super().__init__(settings=settings,silent=silent)
        self.filenames = filenames
        self.path = self._check_data_path(path)
        
        # Parses and stores the channel names that are defined by the json file
        if channels is None:
            all_channel_list_dir = os.path.join(Path(__file__).parent.absolute(), "channels_lab.json")
        else:
            all_channel_list_dir = channels
        # Read all channel info from a json file
        if isinstance(all_channel_list_dir,dict):
            self.all_channels = channels
        else:
            with open(all_channel_list_dir, "r") as json_file:
                self.all_channels = json.load(json_file)
        self.channels = self.availableChannels
        
    @property
    def availableChannels(self):
        """Returns the channel names that are available for use, defined by the json file"""
        available_channels = list(self.all_channels.keys())
        return available_channels
        
    def createDataframePerFormat(self, h5_file, format_):
        valid_names = [each_name
            for each_name in self.channels
            if each_name in self.all_channels]  # filters for valid channels
        # Only channels with the defined format are selected and stored 
        # in an iterable list
        # print(valid_names)
        if format_ is not None:
            channels = [each_name
                for each_name in valid_names
                if self.all_channels[each_name]["format"] == format_]
        else:
            channels = [each_name for each_name in valid_names]
            
        if format_ == "slow":
            electronID = np.cumsum([0,*h5_file['DLD/NumOfEvents'][:-1]])
            
        elif format_ == "electron":
            electronID = np.arange(len(h5_file['DLD/DLD/times']))

        channels_in_h5 = misc.parse_h5_keys(h5_file)
        bad_channels = []
        good_channels = []
        for channel in channels:
            gn = self.all_channels[channel]['group_name']
            if gn not in channels_in_h5:
                bad_channels.append(channel)
            else:
                good_channels.append(channel)
        if len(bad_channels) > 0:
            
            print(f"ERROR: skipped channels missing in h5 file: {[self.all_channels[channel]['group_name'] for channel in bad_channels]}")
        # print([self.all_channels[channel]['group_name'] for channel in channels])
        # print(h5_file)

        dataframes = (Series(h5_file[self.all_channels[channel]['group_name']], 
                        name = channel, 
                        index = electronID)
              .to_frame() for channel in good_channels)

        return reduce(DataFrame.combine_first, dataframes)
    
    def readFile(self, filename):
        with h5py.File(filename) as h5_file:
            dataframe = concat((self.createDataframePerFormat(h5_file, format_) 
                                   for format_ in ['slow', 'electron']), axis=1)
        return dataframe
    
    def h5_to_parquet(self, h5, prq):
        try:
            (self.readFile(h5).reset_index()
            .to_parquet(prq, compression = None, index = False))
        except ValueError as e:
            self.failed_str.append(f'{prq}: {e}')
            self.prq_names.remove(prq)
 
    def fillNA(self):
        """Routine to fill the NaN values with intrafile forward filling. """
        # First use forward filling method to fill each file's pulse resolved channels.
        for i in range(len(self.dfs)):
            self.dfs[i] = self.dfs[i].fillna(method="ffill")

        # This loop forward fills between the consective files. 
        # The first run file will have NaNs, unless another run before it has been defined.
        for i in range(1, len(self.dfs)):
            subset = self.dfs[i]
            is_null = subset.loc[0].isnull().values.compute() # Find which column(s) contain NaNs.
            # Statement executed if there is more than one NaN value in the first row from all columns
            if is_null.sum() > 0: 
                # Select channel names with only NaNs
                channels_to_overwrite = list(is_null[0])
                # Get the values for those channels from previous file
                values = self.dfs[i-1].tail(1).values[0]
                # Fill all NaNs by those values
                subset[channels_to_overwrite] = subset[channels_to_overwrite].fillna(
                                                                dict(zip(channels_to_overwrite, values)))
                # Overwrite the dataframes with filled dataframes
                self.dfs[i] = subset

    def _check_data_path(self,path:Union[str,Path,None]=None) -> Path:
        """ Test the validity of the provided data path.

        Args:
            path: path to check

        Raises:
            AttributeError: if the path is not valid

        Returns:
            the Path instance of the given path.
        """
        if path is not None:
            self.path = Path(path)
        else:
            self.path = Path(self.DATA_RAW_DIR)
            if self.path is None:
                raise AttributeError('Must provide a path to the raw data.')
        return self.path

    def getAvailableRuns(self,path:Union[str,Path,None]=None) -> dict:        
        """ find all run numbers available at the given path

        Args:
            path: path to parse. Overwrites the instance value of path
        Returns:
            dictionary with run numbers and file path pairs
        """
        path = self._check_data_path(path)

        runs_dict = {}
        for file in path.iterdir():
            try:
                run_number = int(file.stem.split('_')[-1])
                if run_number not in runs_dict.keys():
                    runs_dict[run_number] = file
                else:
                    raise RuntimeError(
                        f'Found duplicate run number {run_number} in {path}.')
            except ValueError:
                pass
        return runs_dict

    def readRuns(
        self,
        run_numbers:Union[int,str,Sequence[Union[int,str]]],
        path:Union[str,Path,None]=None,
        parquet_path:Union[str,Path,None]=None,
        ) -> dd.DataFrame:
        """ Read data by run number.

        Args:
            run_numbers: one or a list of run numbers
            data_path: path to the data directory, if None, uses the class instance 
                value. Defaults to None.
            parquet_path:  Path to the parquet directory where to store the intermediate
                parquet files. Defaults to None.
        """
        if isinstance(run_numbers,(int,str)):
            run_numbers = [run_numbers]
        avaliable_runs = self.getAvailableRuns(path=path)
        files_to_read = [
            filepath for run_number,filepath in avaliable_runs.items() 
            if run_number in run_numbers
            ]
        return self.readData(files_to_read,parquet_path=parquet_path)

    def readFiles(
        self,
        files:Union[int,str,Sequence[Union[int,str]]],
        path:Union[str,Path,None]=None,
        parquet_path:Union[str,Path,None]=None,
        ignore_missing_files:bool=False
        ) -> dd.DataFrame:
        """ Read data by run number.

        Args:
            files: one or a list of file names of full file paths to load.
            data_path: path to the data directory, if None, uses the class instance 
                value. Defaults to None.
            parquet_path: Path to the parquet directory where to store the intermediate
                parquet files. Defaults to None.
        """
        path = self._check_data_path(path)

        if isinstance(files,(str,Path)):
            files = [files]
        files_to_read = []
        not_found = []
        for file in files:
            filepath = Path(file)
            if filepath.suffix == '':
                filepath = filepath.with_suffix('.h5')
            if not filepath.is_file():
                filepath = path/file
                if not filepath.is_file():
                    not_found.append(file)
                    continue
            files_to_read.append(filepath)
        if len(not_found) > 0 and not ignore_missing_files:
            raise FileNotFoundError(
                f'Failed to find {len(not_found)} of {len(files)} files: {not_found}'
                )
        return self.readData(files_to_read,parquet_path=parquet_path)

    def readData(self, files_to_read=None, parquet_path = None) -> dd.DataFrame:
        """ load data from the list of provided pahts.

        This is for internal use, please refer to readRuns or readFiles instead.

        Args:
            files_to_read: list of paths to the files to load. Defaults to None.
            parquet_path: Path to the parquet directory where to store the intermediate
                parquet files. Defaults to None.

        Returns:
            the generated dataframe
        """
        
        # create a per_file directory
        if parquet_path is None:
            self.parquet_dir = self.path.joinpath('parquet')
        else:
            self.parquet_dir = Path(parquet_path)
        if not self.parquet_dir.exists():
            os.mkdir(self.parquet_dir)
        
        if files_to_read is not None:
            assert isinstance(files_to_read,Iterable), 'files_to_read must be iterable'
            assert isinstance(files_to_read[0],Path), 'files_to_read must contain Paths'
            self.filenames = files_to_read
   
        # prepare a list of names for the files to read and parquets to write
        if len(self.filenames) > 1:
            files_str = f'File {self.filenames}'
        else:
            files_str = f'Files {self.filenames[0]} to {self.filenames[-1]}'

        # self.prq_names = [f'{self.parquet_dir}/{filename}' for filename in self.filenames]
        # self.filenames = [f'{self.path}/{filename}.h5' for filename in self.filenames]
        self.prq_names = [f'{self.parquet_dir}/{filename.stem}'for filename in self.filenames]
        self.filenames = [str(filename.with_suffix('.h5')) for filename in self.filenames]

        
        missing_files = []
        missing_prq_names = []
        
        # only read and write files which were not read already 
        for i in range(len(self.prq_names)): 
            if not Path(self.prq_names[i]).exists():
                missing_files.append(self.filenames[i])
                missing_prq_names.append(self.prq_names[i])
        
        print(f'Reading {files_str}: {len(missing_files)} new files of {len(self.filenames)} total.')
        self.failed_str = []

        # Set cores for multiprocessing
        N_CORES = len(missing_files)
        if N_CORES > cpu_count() - 1:
            N_CORES = cpu_count() - 1
        
        # Read missing files using multiple cores
        if len(missing_files) > 0:
            with Pool(processes=N_CORES) as pool:    
                pool.starmap(self.h5_to_parquet, tuple(zip(missing_files, missing_prq_names)))
                            
        if len(self.failed_str)>0:
            print(f'Failed reading {len(self.failed_str)} files of{len(self.filenames)}:')
            for s in self.failed_str:
                print(f'\t- {s}')
        if len(self.prq_names)==0:
            raise ValueError('No data available. Probably failed reading all h5 files')
        else:
            print(f'Loading {len(self.prq_names)} dataframes. Failed reading {len(self.filenames)-len(self.prq_names)} files.')  
            self.dfs = [dd.read_parquet(fn) for fn in self.prq_names] # todo skip pandas, as dask only should work
            self.fillNA()

        self.dd  = dd.concat(self.dfs).repartition(npartitions=len(self.prq_names))
        return self.dd
