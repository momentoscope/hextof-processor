import os
from pathlib import Path
import yaml
from processor.DldFlashDataframeCreatorExpress import DldFlashProcessorExpress
from processor.LabDataframeCreator import LabDataframeCreator

class DataframeCreator():
    def __init__(self, config, filenames = None, runNumber = None, settings = None):
        self.config_parser(config)
        if self.acquisition == 'flash':
            self.prc = DldFlashProcessorExpress(self, runNumber, settings)
        if self.acquisition == 'lab':
            self.prc = LabDataframeCreator(self, filenames, settings)

    def config_parser(self, config):
        with open(config) as file:
            config = yaml.load_all(file, Loader=yaml.FullLoader)
            for doc in config:
                if 'general' in doc.keys():
                    self.general = doc['general']
                if 'channels' in doc.keys():
                    self.channels = doc['channels']
                if 'paths' in doc.keys():
                    self.paths = doc['paths']

            if not {'acquisition', 'ubid_offset', 'daq'}.issubset(self.general.keys()):
                    raise ValueError('One of the values from acquisition, ubid_offset or daq is missing. These are necessary.')
            self.acquisition = self.general['acquisition']
            self.UBID_OFFSET = self.general['ubid_offset']
            self.DAQ = self.general['daq']

            # Prases to locate the raw beamtime directory from config file
            if self.paths:
                if 'data_raw_dir' in self.paths:
                    self.DATA_RAW_DIR = Path(self.paths['data_raw_dir'])
                if 'data_parquet_dir' in self.paths:
                    self.DATA_PARQUET_DIR = Path(self.paths['data_parquet_dir'])
            else:
                if {'beamtime_id', 'year'}.issubset(self.general.keys()):
                    raise ValueError('The beamtime_id and year or data_raw_dir is required.')

                beamtime_id = self.general['beamtime_id']
                year = self.general['year']
                beamtime_dir = Path(f'/asap3/flash/gpfs/pg2/{year}/data/{beamtime_id}/')

                # Folder naming convention till end of October
                self.DATA_RAW_DIR = beamtime_dir.joinpath('raw/hdf/express')
                # Use new convention if express doesn't exist
                if not self.DATA_RAW_DIR.exists():
                    self.DATA_RAW_DIR = beamtime_dir.joinpath(f'raw/hdf/{self.DAQ.upper()}')

                if self.DATA_PARQUET_DIR is None:
                    parquet_path = 'processed/parquet'
                    self.DATA_PARQUET_DIR = beamtime_dir.joinpath(parquet_path)

                if not self.DATA_PARQUET_DIR.exists():
                    os.mkdir(self.DATA_PARQUET_DIR)
