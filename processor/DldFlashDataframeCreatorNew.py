import sys, os
import glob
import json
import h5py
import numpy as np
from pandas import Series, DataFrame, concat, MultiIndex, merge
from pathlib import Path
from functools import reduce

"""
    author:: Muhammad Zain Sohail
    Some functions taken or adapted from
    https://gitlab.desy.de/christopher.passow/flash-daq-hdf/
"""

assert sys.version_info >= (3,8), f"Requires at least Python version 3.8,\
    but was {sys.version}"


class DldFlashProcessorNew:
    """  
    The class generates multiindexed multidimensional pandas dataframes 
    from the new FLASH dataformat resolved by both macro and microbunches.
    """
    def __init__(self, data_raw_dir, run_number=None, train_id_interval=None,channels=None):

        self.run_number = run_number
        self.train_id_interval = train_id_interval
        self.data_raw_dir = data_raw_dir
        self.channels = []
        if channels is None:
            all_channel_list_dir = os.path.join(os.path.dirname(__file__),"channels.json")  # TODO: Generalize
        else:
            all_channel_list_dir = channels
        # Read all channel info from a json file
        with open(all_channel_list_dir, "r") as json_file:
            self.all_channels = json.load(json_file)
        self.channels = self.availableChannels # Set all channels as default
        self.resetMultiIndex()  # initializes the indices

    @property
    def availableChannels(self):
        """Returns the channel names that are available for use,
        defined by the json file"""
        return list(self.all_channels.keys())

    def resetMultiIndex(self):
        """Resets the index per pulse and electron"""
        self.index_per_electron = None
        self.index_per_pulse = None

    def createMultiIndexPerElectron(self, h5_file):
        """Creates an index per electron using dldMicrobunchId 
        for usage with the electron resolved pandas dataframe"""

        # Macrobunch IDs obtained from the dldMicrobunchId channel
        [train_id, np_array] = self.createNumpyArrayPerChannel(h5_file, "dldMicrobunchId")

        # Create a series with the macrobunches as index and microbunches as values
        macrobunches = Series((np_array[i] for i in train_id.index),
            name="dldMicrobunchId",
            index=train_id)

        # Explode dataframe to get all microbunch vales per macrobunch,
        # remove NaN values and convert to type int
        microbunches = macrobunches.explode().dropna().astype(int)
        
        # Create temporary index values 
        index_temp = MultiIndex.from_arrays((microbunches.index, microbunches.values),
                    names=["trainId", "pulseId"])


        # Calculate the electron counts per dldMicrobunchId
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
        np_array = group["value"][()]  # unpacks the values

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
                .drop(index=0, level=1))
        
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
            
            elif channel in ['monochromatorPhotonEnergy', 'delayStage']:
                return (Series((np_array[i] for i in train_id.index), name=channel)
                    .to_frame()
                    .set_index(train_id))
                
            else:
                # Resize arrays which are not of dimension train_id x 499, 
                # padding with NaNs
#                 if np_array.shape[1]<499:
#                     empty = np.full((np_array.shape[0], 499), np.nan)
#                     empty.flat[:len(np_array)] = np_array[:, :499]
#                     np_array = empty
#                 elif np_array.shape[1]>499:
#                     np_array = np_array[:, :499]
                
                # For all other pulse resolved channels, macrobunch resolved 
                # data is exploded to a dataframe and the MultiIndex set
            
                # Creates the index_per_pulse for the given channel
                self.createMultiIndexPerPulse(train_id, np_array)
                return (Series((np_array[i] for i in train_id.index), name=channel)
                    .explode()
                    .to_frame()
                    .set_index(self.index_per_pulse))

    def concatenateChannels(self, h5_file, format_=None):
        """Returns a concatenated pandas DataFrame for either all pulse
        resolved or all electron resolved channels."""
        valid_names = (each_name
            for each_name in self.channels
            if each_name in self.all_channels)  # filters for valid channels
        
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
            # for the split version:
#             data_frames = [self.concatenateChannels(h5_file, format_) 
#                   for format_ in ["per_electron", "per_pulse"]]
            return self.concatenateChannels(h5_file) 
          
    def runFilesNames(self, run_number, daq):
        """Returns all filenames of given run located in directory for the given daq."""
        stream_name_prefixes = {"pbd": "GMD_DATA_gmd_data",
                                "pbd2": "FL2PhotDiag_pbd2_gmd_data",
                                "fl1user1": "FLASH1_USER1_stream_2",
                                "fl1user2": "FLASH1_USER2_stream_2",
                                "fl1user3": "FLASH1_USER3_stream_2",
                                "fl2user1": "FLASH2_USER1_stream_2",
                                "fl2user2": "FLASH2_USER2_stream_2"}
        date_time_section = lambda filename: str(filename).split("_")[-1]
        return sorted(Path(self.data_raw_dir)
            .glob(f"{stream_name_prefixes[daq]}_run{run_number}_*.h5"),
            key=date_time_section)

    def createDataframePerRun(self, run_number=None, daq="fl1user2"):
        """Returns concatenated DataFrame for multiple files from a run"""

        if run_number is None:
            run_number = self.run_number
        else:
            self.run_number = run_number

        files = self.runFilesNames(run_number, daq)
        
        # Creates a list of dataframes for all files in a run
        # genexpr not used due to the need to call this twice
        # data_frames = [
        #     self.createDataframePerFile(each_file) for each_file in files]

        # assert (data_frames
        # ), "Assertion: at least one file in files, but files was empty"

        # Deconvolves the dataframes list to seperate pulse resolved 
        # dataframes from electron resolved, returing the concatenated 
        # version of both
#         return data_frames
        # for split dataframes
        # return concat(list(zip(*data_frames))[0]), concat(list(zip(*data_frames))[1])
        data_frames = (self.createDataframePerFile(each_file) for each_file in files)
        return concat(data_frames)

    def savetoParquet(self, parquet_dir, run_number=None, daq="fl1user2"):
        """Saves the run data with the selected channels into a parquet file"""

        # Moves the indexes to columns, and saves to parquet in given directory
        createDataframePerRun(run_number, daq).reset_index(level=['trainId', 'pulseId']
                     ).to_parquet(parquet_dir + str(self.run_number)
                                        , compression = None, index = False)

        
# ################################################
# prc = DldFlashDataframeCreator()
# prc.runNumber = 12345
# prc.readData()
# prc.addBinning(dldPosX)
# prc.addBinning(dldTime)
# res = prc.computeBinnedData(ski
# compare to : 
# prc = DldFlashDataframeCreator()
# prc.loadDataframes(prq)
# prc.dd = YOURDATAFRAME
# prc.addBinning(dldPosX)
# prc.addBinning(dldTime)
# res = prc.computeBinnedData(skip_metadata=True)
##################################################

    # ==================
    # Might not work
    # ==================
    def createDataframePerRunIdInterval(
        self, train_id_interval=None, run_number=None, daq="fl1user2"
    ):
        """Returns a concatenated DataFrame from a run including values only between train_id_interval"""
        if train_id_interval is None:
            train_id_interval = self.train_id_interval
        else:
            self.train_id_interval = train_id_interval

        if run_number is None:
            run_number = self.run_number
        else:
            self.run_number = run_number

        # Get paths of all files in the run for a specific daq
        paths = self.runFilesNames(run_number, daq)

        # Compute TrainIds for the whole Run using an arbritary channel, which is combined into
        # a pandas Series with indices being TrainIds, and the values being the file numbers
        channel = self.all_channels[self.channels[0]]["group_name"]
        train_ids_per_file = (
            Series(
                np.tile(i, h5py.File(each, "r")[channel]["index"].size),
                index=h5py.File(each, "r")[channel]["index"])
                for i, each in enumerate(paths))

        # Reduce all Run TrainIds into one Series
        train_ids_per_run = reduce(Series.append, train_ids_per_file)

        # Locate only files with the requested train_id_interval
        unique = np.unique(
            train_ids_per_run.loc[
                self.train_id_interval[0] : self.train_id_interval[1]])

        # Create Dataframe for all requested channels for each file and combine them,
        # only returning with values between train_id_interval
        data_frames = [
            self.createDataframePerFile(each_file)
            for each_file in paths[unique[0] : unique[-1]]]
        assert (
            data_frames
        ), "Assertion: at least one file in files, but files was empty"
        return reduce(DataFrame.combine_first, data_frames).loc[
            self.train_id_interval[0] : self.train_id_interval[1]]
