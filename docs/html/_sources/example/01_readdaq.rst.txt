Read DAQ data
==============

Load the data with a given DAQ run number
############################################

.. code-block:: python

    # create a processor isntance
    processor = DldFlashProcessor()
    # assign a run number
    processor.runNumber = 18843


The data can now be loaded from either a full DAQ run:

.. code-block:: python

    # read the data from the DAQ hdf5 dataframes
    processor.readData(runNumber=processor.runNumber)


or from a selected range of the `pulseIdInterval`:

.. code-block:: python

    mbFrom = 1000 # first macrobunch
    mbTo = 2000 # last macrobunch
    processor.readData(pulseIdInterval=(mbFrom,mbTo))


Run the `postProcess` method
###################################

This generates a BAM-corrected `pumpProbeDelay` array, together with polar coordinates for the momentum axes.

.. code-block:: python

    processor.postProcess()


The dask dataframe is now created and can be used directly or stored in parquet format (optimized for speed) for future use. A shorter code summary is in the following:

.. code-block:: python

    processor = DldFlashProcessor()
    processor.runNumber = 18843
    processor.readData(runNumber=processor.runNumber)
    processor.postProcess()