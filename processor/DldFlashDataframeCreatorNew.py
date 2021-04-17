import sys
import glob
import json
import h5py
import numpy as np
from pandas import Series, DataFrame
from pathlib import Path
from functools import reduce

"""
    author:: Muhammad Zain Sohail
    Some functions taken or adapted from https://gitlab.desy.de/christopher.passow/flash-daq-hdf/
"""

assert sys.version_info >= (3, 8), f"Requires at least Python version 3.8, but was {sys.version}"

class DldFlashProcessorNew():
    def __init__(self, runNumber=None, TrainIdInterval=None):
        
        self.runNumber = runNumber
        self.TrainIdInterval = TrainIdInterval
        self.dataRawDir = "/asap3/flash/gpfs/pg2/2020/data/11008860/raw/hdf/express/" # Needs to be generalized
        self.Channels = []
        all_channel_list_dir = 'channels.json' # Needs to be generalized but this can be default
        with open(all_channel_list_dir, 'r') as json_file:
            self.allChannels = json.load(json_file)
        
    
    def returnAvailableChannels(self):
        """ Returns the channel names that are available for use, defined by the json file """
        return list(self.allChannels.keys())

    def createDataframePerRunIdInterval(self, TrainIdInterval=None, runNumber=None, daq = "fl1user2"):
        """ Returns a concatenated DataFrame from a run including values only between TrainIdInterval"""
        if TrainIdInterval is None:
            TrainIdInterval = self.TrainIdInterval
        else:
            self.TrainIdInterval = TrainIdInterval
            
        if runNumber is None:
            runNumber = self.runNumber
        else:
            self.runNumber = runNumber
        
        # Get paths of all files in the run for a specific daq
        paths = self.runFilesNames(runNumber, daq)
        
        # Compute TrainIds for the whole Run using an arbritary channel, which is combined into
        # a pandas Series with indices being TrainIds, and the values being the file numbers
        channel = self.allChannels[self.Channels[0]]['group_name']
        TrainIDsPerFile = (Series(np.tile(i, h5py.File(each, 'r')[channel]["index"].size), 
                                 index=h5py.File(each, 'r')[channel]["index"]) for i, each in enumerate(paths))
        
        # Reduce all Run TrainIds into one Series
        TrainIDsPerRun = reduce(Series.append, TrainIDsPerFile)
        
        # Locate only files with the requested TrainIdInterval
        unique = np.unique(TrainIDsPerRun.loc[self.TrainIdInterval[0]:self.TrainIdInterval[1]])
        
        # Create Dataframe for all requested channels for each file and combine them, 
        # only returning with values between TrainIdInterval
        data_frames = [self.createDataframePerFile(each_file) for each_file in paths[unique[0]:unique[-1]]]
        assert data_frames, "Assertion: at least one file in files, but files was empty"
        return reduce(DataFrame.combine_first, data_frames).loc[self.TrainIdInterval[0]:self.TrainIdInterval[1]]
                                                                
    def createDataframePerRun(self, runNumber=None, daq = "fl1user2"): 
        """ Returns concatenated DataFrame for multiple files from a run"""
        if runNumber is None:
            runNumber = self.runNumber
        else:
            self.runNumber = runNumber
            
        files = self.runFilesNames(runNumber, daq)
        data_frames = [self.createDataframePerFile(each_file) for each_file in files]
        assert data_frames, "Assertion: at least one file in files, but files was empty"
        return reduce(DataFrame.combine_first, data_frames)

    def runFilesNames(self, runNumber, daq):
        """ Returns all filenames of given run located in directory for the given daq. """
        stream_name_prefixes = {"pbd": "GMD_DATA_gmd_data",
                                "pbd2": "FL2PhotDiag_pbd2_gmd_data",
                                "fl1user1": "FLASH1_USER1_stream_2",
                                "fl1user2": "FLASH1_USER2_stream_2",
                                "fl1user3": "FLASH1_USER3_stream_2",
                                "fl2user1": "FLASH2_USER1_stream_2",
                                "fl2user2": "FLASH2_USER2_stream_2"}
        date_time_section = lambda filename: str(filename).split("_")[-1]
        return sorted(Path(self.dataRawDir).glob(f"{stream_name_prefixes[daq]}_run{runNumber}_*.h5"), key=date_time_section)
        

    def createDataframePerFile(self, file_path):
        """ Returns a pandas DataFrame constructed for the given file.
            The DataFrame contains the datasets from the iterable in the order specified by channel names
        """
        with h5py.File(file_path, 'r') as h5_file:
            valid_names = (each_name for each_name in self.Channels if each_name in self.allChannels)  # filter
            self.data_frames = (self.createDataframePerChannel(h5_file, each) for each in valid_names)  # map
            return reduce(DataFrame.combine_first, self.data_frames, DataFrame())

    def createDataframePerChannel(self, h5_file, channel):
        """Returns a pandas DataFrame for a given channel name"""   
        group = h5_file[self.allChannels[channel]['group_name']]
        channel_dict = self.allChannels[channel]

        train_id = Series(group["index"], name="Train ID")
        np_array = group["value"][()] #unpacks the values
        
        # Uses predefined axis and slice from the json file to choose correct dimension for necessary channel
        if "axis" in channel_dict:
            np_array = np.take(np_array, channel_dict["slice"], axis=channel_dict["axis"])

        return Series((np_array[i] for i in train_id.index), name=channel, index=train_id).to_frame()
    