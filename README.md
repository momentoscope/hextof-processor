# HextofOfflineAnalyzer
This code is used to analyze data measured at FLASH using the
Hextof instrument. The Hextof uses a delayline detector to detect
single electrons in position and arrival time.

The analysis of the data is based on clean tables as DASK dataframes.
The main table contains all detected electrons and can be binned
according to the needs of the experiment. The second dataframe contains
the FEL pulses needed for normalization.

The class "DldProcessor" contains the DASK dataframes as well as the
methods to do the binning (parallelized).

The "DldFlashDataframeCreator" class is used for creating the dataframes
from the hdf5 files generated by the DAQ system. It may need to be
modified for diferend beamtimes, whereas the "DldProcessor" should be
more universal.

The data from the DAQ system is read through the code provided by FLASH,
which can be found on the bitbucket repo at https://stash.desy.de/projects/CS
The location of the downloaded repo must be set in the SETTINGS file,
under PAH_MODULE_DIR. This will be contained in the processor object as
processor.PAH_MODULE_DIR.


Settings
-----------

To initialize correctly this code on a new machine, run the
InitializeSettings.py
file to create the SETTINGS.ini file where local settings are stored.
This is not tracked in the git, to keep compatibility across multiple
machines.

Current version
--

Latest version of the processor is in processor. lib contains a legacy
version, kept for retrocompatibility checks.

How to use
==

In order to make use of this offline-analysis tool, the irst thing is
how to import the correct modules.
Therefore, after adding the repos folder to the system path, start as:
```python
import sys,os
sys.path.append('/path/to/HextofOfflineAnalyzer/')

from processor.DldFlashDataframeCreator import DldFlashProcessor()
```

Some usefull imports for initializing an Ipython notebook should look as
follows:
```python
import sys,os
import numpy as np
import matplotlib.pyplot as plt
from importlib import reload

import processor.utils as utils # contains commonly used functions for
treating this data.
import processor.DldFlashDataframeCreator as DldFlashProcessor
reload(dldFlashProcessor)
```



Read DAQ data
-------------

Load the data from a given DAQ run number

```python
# create a processor isntance
processor = DldFlashProcessor()
# assign a run number
processor.runNumber = 18843
```

data can now be loaded from either a full DAQ run:
```python
#read the data from the DAQ hdf5 dataframes
processor.readData(runNumber=processor.runNumber)
```
or from a selected range of , the pulseIdInterval:
```python
mbFrom = 1000 # first macrobunch
mbTo = 2000 # last macrobunch
processor.readData(pulseIdInterval=(mbFrom,mbTo))
```
Next step is to run the postProcess method, which generates a bam
corrected pumpProbeDelay dataset, toghether with polar coordinates for
the k-resolved axes.

```python
processor.postProcess()
```

The dask dataframe is now created and can be used directly or stored in
parquet format for optimized future use.

A shorter snap of code for copy-pasting is the following:

```python
processor = DldFlashProcessor()
processor.runNumber = 18843
processor.readData(runNumber=processor.runNumber)
processor.postProcess()
```


Save dataset to dask parquet files
----------------------------------

For faster access to these dataframes for future analysis, it is
convenient to store the datasets in dask parquet dataframes.
This is done using:
```pthon
processor.storeDataframes('filename')
```

This saves two folders in path/to/file: name_el and name_mb. These are
the two datasets processor.dd and processor.ddMicrobunches.
if 'filename' is not specified, it uses either 'run{runNumber}' or
mb{firstMacrobunch}to{lastMacrobunch}'



Such datasets can be loaded back into the processor the readDataframes()
method.
Using parquet:
```python
processor = DldFlashProcessor()
processor.readDataframes('filename')
```


An optional parameter for both storeDataframes() and readDataframes() is
path=''. When unspecified, (left as default None) the value from
SETTINGS DATA_PARQUET_DIR or DATA_H5_DIR is assigned.

Alternatively it is possible to store these datasets similarly in hdf5
format, using the same function:
```pthon
processor.storeDataframes('filename', format='hdf5')
```
However, this is NOT advised, since the parquet format outperforms the
hdf5. This functionality is kept for retrocompatibility with older
datasets.

Binning
=======
In order to get n-dimensional np.arrays from the generated datasets,
it is necessary to bin data along the desired axes.
an example of how this is done, starting from loading parquet data:
```python
processor = DldFlashProcessor()
processor.runNumber = 18843
processor.readDataframes('path/to/file/name')
```
This can be also done from direct raw data read with readData()
To create the bin array structure:
```python
processor.addBinning('posX',480,980,10)
processor.addBinning('posY',480,980,10)
```
This adds binning along the k-parallel x and y directions, from point
480 to point 980 with bin size of 10.
Bins can be created defining start and end points and either step size
or number of steps. The default behavior is
The resulting array can now be obtained using
```python
result = processor.ComputeBinnedData()
```
where the resulting np.array of float64 values will have the axis order
same as the order in which we generated the bins.

Other binning axis commonly used are:

| name                   | string                   | typical values | units |
|:----------------------:|:------------------------:|:--------------:|------:|
| ToF delay (ns)         | 'dldTime'                | 620,670,10 *   | ns    |
| pump-probe time delay  | 'pumpProbeDelay'         | -10,10,1       | ps    |
| separate dld detectors | 'dldDetectors'           | -1,2,1         | ID    |
| microbunch (pulse) ID  | 'microbunchId'           | 0,500,1 **     | ID    |
| Auxiliary              | 'dldAux'                 |                |       |
| Beam Arrival Monitor   | 'bam'                    |                | fs    |
| FEL Bunch Charge       | 'bunchCharge'            |                |       |
| Macrobunch ID          | 'macroBunchPulseId'      |                | ID    |
| Laser diode            | 'opticalDiode'           | 1000,2000,100  |       |
| ?                      | 'gmdTunnel'              |                |       |
| ?                      | 'gmdBda'                 |                |       |



\* ToF delay bin size needs to be multiplied by processor.TOF_STEP_TO_NS
in order to avoid artifacts.

\** binning on microbunch works only when not binning on any other
dimension

Binning is created using np.linspace (formerly was done with np.arange).
The implementation allows to choose between setting a step size
(useStepSize=True, default) or using a number of bins
(useStepSize=False).

In general, it is not possible to satisfy all 3 parameters: start, end,
steps. For this reason, you can choose to give priority to the step size
or to the interval size. In case forceEnds=False, the steps parameter is
given priority and the end parameter is redefined, so the interval can
actually be larger than expected. In case forceEnds = true, the stepSize
is not enforced, and the interval is divided by the closest step that
divides it cleanly. This of course only has meaning when choosing steps
that do not cleanly divide the interval.


Extracting data without binning
-----------

Sometimes it is not necessary to bin the electrons to extract the data. It is
actually possible to directly extract data from the appropriate dataframe. This
is useful if, for example, you just want to plot some parameters, not involving
the number of electrons that happen to have such a value (this would require
binning).

Because of the structure of the dataframe, which is divided in dd and ddMicrobunches,
it is possible to get electron-resolved data (the electron number will be on 
the x-axis), or uBunchID resolved data (the uBid will be on the x-axis).

The data you can get from the dd dataframe (electron-resolved) includes:

| name                   | string                   |
|:----------------------:|:------------------------:|
|x position of the electron| 'posX'|
|x position of the electron| 'posY'
|time of flight| 'dldTime'|
|pump probe delay stage reading| 'delayStageTime'
|beam arrival monitor jitter|    'bam'
|micro bunch ID| 'microbunchId'
|which detector| 'dldDetectorId'
|electron bunch charge|  'bunchCharge'
|pump laser optical diode reading|  'opticalDiode'
|gas monitor detector reading before gas attenuator| 'gmdTunnel'
|gas monitor detector reading after gas attenuator| 'gmdBda'
|macro bunch ID| 'macroBunchPulseId'

The data you can get from the ddMicrobunches (uBID resolved) dataframe includes:

| name                   | string                   |
|:----------------------:|:------------------------:|
|pump probe delay stage reading| 'delayStageTime'
|beam arrival monitor jitter|    'bam'
|auxillarey channel 0| 'aux0'
|auxillarey channel 1| 'aux1'
|electron bunch charge|  'bunchCharge'
|pump laser optical diode reading|  'opticalDiode'
|macro bunch ID| 'macroBunchPulseId'

Some of the values overlap, and in these cases, you can get the values either uBid-resolved
or electron-resolved.

An example of how to get values both from the dd and ddMicrobunches dataframes:
```python
bam_dd=processor.dd['bam'].values.compute()
bam_uBid=processor.ddMicrobunches['bam'].values.compute()
```
Be careful when reading the data not to include ids that contain NaNs (usually
at the beginning), otherwise this method will return all NaNs.

It is also possible to access the electron-resolved data on a uBid basis by using
```python
uBid=processor.dd['microbunchId'].values.compute()
value[int(uBid[j])]
```
or to plot the values as a function of uBid by using
```python
uBid=processor.dd['microbunchId'].values.compute()
MBid=processor.dd['macroBunchPulseId'].values.compute()
bam=processor.dd['bam'].values.compute()

pl.plot(uBid+processor.bam.shape[1]*MBid,bam)
```

The following code, as an example, averages gmdTunnel values for electrons
that have the same uBid (it effectively also bins the electrons in avgNorm
as a side effect):

```python
uBid=processor.dd['microbunchId'].values.compute()
pow=processor.dd['gmdBDA'].values.compute()

avgPow=np.zeros(500)
avgNorm=np.zeros(500)
for j in range(0,len(uBid)):
    if(uBid[j]>0 and uBid[j]<500 and pow[j]>0):
        avgNorm[int(uBid[j])]+=1
        avgPow1[int(uBid[j])]=(avgPow1[int(uBid[j])]*(avgNorm[int(uBid[j])])+pow[j])/(avgNorm[int(uBid[j])]+1.0)

```

# Full code example

Some examples, Ipython compatible:
imports:
```python
import sys,os
import math
import numpy as np
import h5py
import time

import matplotlib
import matplotlib.pyplot as plt
import matplotlib.cm as cm
import matplotlib.colors as colors
import scipy.signal as spsignal
# %matplotlib inline # uncomment in Ipython

from imp import reload
from scipy.ndimage import gaussian_filter
from processor import utils, DldFlashDataframeCreator as DldFlashProcessor
# reload(dldFlashProcessor)

```
Load from raw data:
```python
reload(dldFlashProcessor) # in case code has changed since import.

runNumber = 12345
read_from_raw = True # set false to go straight for the stored parquet data
save_and_use_parquet = True # set false to skip saving as parquet and reloading.

processor = DldFlashProcessor()
processor.runNumber = runNumber
if read_from_raw:
    processor.readData()
    processor.postProcess()
    if save_and_use_parquet:
        processor.storeDataframes()
        del processor
        processor = DldFlashProcessor()
        processor.runNumber = runNumber
        processor.readDataframes()
else:
    processor.readDataframes()

#start binning procedure
processor.addBinning('posX',480,980,10)
processor.addBinning('posY',480,980,10)

result = processor.ComputeBinnedData()
result = nan_to_num(result)
plt.imshow(result)
```
