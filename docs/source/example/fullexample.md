## Complete code examples

Complete examples suitable for use in an IPython notebook

**(1)** Importing packages and modules

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
**(2)** Loading raw data
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
processor.addBinning('dldPosX',480,980,10)
processor.addBinning('dldPosY',480,980,10)

result = processor.ComputeBinnedData()
result = nan_to_num(result)
plt.imshow(result)
```