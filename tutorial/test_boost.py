import sys, os
from datetime import datetime
from tqdm.notebook import tnrange

# import numeric packages
import numpy as np
import xarray as xr
import dask
from dask.diagnostics import ProgressBar

# plotting packages
import matplotlib.pyplot as plt
import boost_histogram as bh

# hextof-processor imports
sys.path.append(os.path.dirname(os.getcwd()) ) # add hextof-processor to path
from processor.DldFlashDataframeCreator import DldFlashProcessor
from processor.utilities import calibration, diagnostics, misc, io, vis

# **OPTIONAL** clear memory and load the single event tables from parquet:
prc = DldFlashProcessor() # overwrite the processor with a fresh new instance
prc.runNumber = 22097
prc.DATA_PARQUET_DIR = '/home/sohailmu/hextof-processor/tutorial/parquet' # manually overwrite parquet data folder. it is STRONGLY recomendend to use an SSD drive here.
prc.readDataframes() # load data from single event tables saved as parquet

# Time of flight parameters
tof_from = 620#180
tof_to = 660
tof_step = 0.003 # the bigger number between this and the original step size is used in the final binning size definition.

# pump-probe delay parameters
delay_from = -517
delay_to = -512.5
delay_step = 0.05

# detector position parameters, valid both in x and y directions
dld_from=0
dld_to=3000
dld_step=30


prc.resetBins() # ensure there is no previous binning axes assigned.
method = 'boost'
# prc.addBinning('dldTime', tof_from,tof_to,tof_step, method = method);
# prc.addBinning('delayStage',delay_from,delay_to,delay_step, method = method);
prc.addBinning('dldPosX',dld_from,dld_to,dld_step, method = method);
# prc.addBinning('dldPosY',dld_from,dld_to,dld_step, method = method);