## Read DAQ data

**(1)** Load the data with a given DAQ run number
```python
# create a processor isntance
processor = DldFlashProcessor()
# assign a run number
processor.runNumber = 18843
```

The data can now be loaded from either a full DAQ run:
```python
#read the data from the DAQ hdf5 dataframes
processor.readData(runNumber=processor.runNumber)
```

or from a selected range of the `pulseIdInterval`:
```python
mbFrom = 1000 # first macrobunch
mbTo = 2000 # last macrobunch
processor.readData(pulseIdInterval=(mbFrom,mbTo))
```

**(2)** Run the `postProcess` method, which generates a BAM-corrected `pumpProbeDelay` array, together with polar coordinates for the momentum axes.
```python
processor.postProcess()
```

The dask dataframe is now created and can be used directly or stored in parquet format (optimized for speed) for future use. A shorter code summary is in the following:
```python
processor = DldFlashProcessor()
processor.runNumber = 18843
processor.readData(runNumber=processor.runNumber)
processor.postProcess()
```