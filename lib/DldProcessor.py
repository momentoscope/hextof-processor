"""
  Copyright 2017-2018, 
    Yves Acremann, Kevin Bühlmann, Rafael Gort, Simon Däster
"""

"""
  This program is free software: you can redistribute it and/or modify
  it under the terms of the GNU General Public License as published by
  the Free Software Foundation, either version 3 of the License, or
  (at your option) any later version.

  This program is distributed in the hope that it will be useful,
  but WITHOUT ANY WARRANTY; without even the implied warranty of
  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
  GNU General Public License for more details.

  You should have received a copy of the GNU General Public License
  along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""



import xarray
import h5py
import numpy
import pandas
import types
import dask.dataframe
import dask
import dask.multiprocessing
import DldFlashProcessorCy
import math

import pylab as pl

import copy
import sys


"""
  This class is the basis for analyzing the electron events measured by
  the Hextof instrument at FLASH.
  The data is converted into a clean table format (DASK dataframes,
  containing the electron events with its positions, arrival times,
  but also any other parameters as needed for the analysis).
  For normalization a second Dask Dataframe is used, containing
  information about the FEL pulses.
  This class allows for accessing the data as HDF5 files as well as
  Parquet data.
"""
class DldProcessor():
    
    """
      The constructor just allows for setting a default center for
      calculating the radii of the electrons.
    """
    def __init__(self):
        self.dldTimeStep = 0.0205761316872428 # ns
        self.nCores = 8
        self.deleteBinners()
    
    """
      Access the data as hdf5 file (this is the format used internally,
      NOT the FLASH HDF5-files from the DAQ system!)
    """    
    def readDataframes(self, fileName):
        self.dd = dask.dataframe.read_hdf(fileName, '/electrons', mode='r', chunksize=10000000)
        self.ddMicrobunches = dask.dataframe.read_hdf(fileName, '/microbunches', mode='r', chunksize=10000000)
        #self.postProcess()
    
    """
      Dead the data as Parquet data structure. This is the preferred way, as access is
      particularly fast.
    """    
    def readDataframesParquet(self, fileName):
        self.dd = dask.dataframe.read_parquet(fileName + "_el", engine="arrow")
        self.ddMicrobunches = dask.dataframe.read_parquet(fileName + "_mb", engine="arrow")
    
    """
      Append data from a Parquet file. This way one can combine multiple DAQ runs
    """    
    def appendDataframeParquet(self, fileName):
        self.dd = self.dd.append(dask.dataframe.read_parquet(fileName + "_el", engine="arrow"))
        self.ddMicrobunches = self.ddMicrobunches.append(dask.dataframe.read_parquet(fileName + "_mb", engine="arrow"))
         
    """
      This method must be called after reading the Dask dataframes. It calculates the pump-probe time
      as well as the radii of the electron events (useful for radial integration).
    """   
    def postProcess(self, centerX=256, centerY=256):
        self.dd['pumpProbeTime'] = self.dd['delayStageTime'] - self.dd['bam']*1e-3*0.0
        self.ddMicrobunches['pumpProbeTime'] = self.ddMicrobunches['delayStageTime'] - self.ddMicrobunches['bam']*1e-3
        def radius(df):
            return numpy.sqrt(numpy.square(df.posX-centerX) + numpy.square(df.posY-centerY))
        self.dd['posR'] = self.dd.map_partitions(radius)
        
    
    """
    Store the binned output data in a hdf5 file
    
    Attributes
    binneddata: binned data with binnes in dldTime, posX, and posY (and if to be normalized, binned in detectors)
    filename: name of the file
    normalize: Normalized data for both detector, so it should be a 3d array (posX, posY,detectorID) 
    """
    def save2hdf5(self,binnedData, path = '/home/pg2user/OfflineAnalysis/',  filename='default.hdf5', normalizedData=None, overwrite=False):
        
        if normalizedData is not None:
            if binnedData.ndim != 4:
                raise Exception('Wrong dimension')
            data2hdf5 = numpy.zeros_like(binnedData[:,:,:,0])    
            
            
            # normalize for all time binns
            for i in range(binnedData.shape[0]):
                # normalize for both detectors (0 and 1)
                
                data2hdf5[i,:,:] = binnedData[i,:,:,0].transpose()/normalizedData[:,:,0].transpose()
                data2hdf5[i,:,:] += binnedData[i,:,:,1].transpose()/normalizedData[:,:,1].transpose()
        else:
            # detector binned? -> sum together
            if binnedData.ndim == 4:
                data2hdf5 = binnedData.sum(axis=3).transpose((0,2,1))
            else:
                if binnedData.ndim != 3:
                    raise Exception('Wrong dimension')
                #print(binnedData.transpose((1,2).shape)
                data2hdf5 = binnedData.transpose((0,2,1))
        
        # create file and save data
        mode = "w-" # fail if file exists
        if overwrite:
            mode = "w"
        
        f = h5py.File(path+filename, mode)
        dset = f.create_dataset("experiment/xyt_data", data2hdf5.shape, dtype='float64')
        
        dset[...] = data2hdf5
        f.close()
        print("Created file "+filename)


  
    """
     Add a binning:
      name: name of the column to bin to
      start, end, stepSize: interval used for binning
      If the name is 'pumpProbeTime': sets self.delaystageHistogram for normalization.
    """
    def addBinning(self, name, start, end, stepSize):
        bins = numpy.arange(start, end, stepSize)
        # write the parameters to the binner list:
        self.binNameList.append(name)
        self.binRangeList.append(bins)
        if (name == 'pumpProbeTime'):
            #self.delaystageHistogram = numpy.histogram(self.delaystage[numpy.isfinite(self.delaystage)], bins)[0]
            delaystageHistBinner = self.ddMicrobunches['pumpProbeTime'].map_partitions(pandas.cut, bins)
            delaystageHistGrouped = self.ddMicrobunches.groupby([delaystageHistBinner])
            self.delaystageHistogram = delaystageHistGrouped.count().compute()['bam'].to_xarray().values.astype(numpy.float64)
        


    
    """
     make an empty binner list
    """
    def deleteBinners(self):
        self.binNameList = []
        self.binRangeList = []
        
    
    
    """
     use the binner list to bin the data. It returns a numpy array.
    """
    def computeBinnedData(self):
        
        # function called by each thread of the analysis
        def analyzePart(part):
            grouperList = []
            for i in range(len(self.binNameList)):
                grouperList.append(pandas.cut(part[self.binNameList[i]], self.binRangeList[i]))
            grouped = part.groupby(grouperList)
            result = (grouped.count())['microbunchId'].to_xarray().values
            return numpy.nan_to_num(result)
        
        
        # prepare the partitions for the calculation in parallel    
        calculatedResults = []
        for i in range(0, self.dd.npartitions, self.nCores):
            resultsToCalculate = []
            # proces the data in blocks of n partitions (given by the number of cores):
            for j in range(0, self.nCores):
                if (i+j) >= self.dd.npartitions:
                    break
                part = self.dd.get_partition(i+j)
                resultsToCalculate.append(dask.delayed(analyzePart)(part))
            
            # now do the calculation on each partition (using the dask framework):
            if len(resultsToCalculate) > 0:
                print("computing partitions" + str(i)+ " len: " + str(len(resultsToCalculate)))
                results = dask.compute(*resultsToCalculate)
                total = numpy.zeros_like(results[0])
                for result in results:
                    total = total + result
                calculatedResults.append(total)
                del total
            del resultsToCalculate
        
        # we now need to add them all up (single core):
        result = numpy.zeros_like(calculatedResults[0])
        for r in calculatedResults:
            r = numpy.nan_to_num(r)
            result = result + r
        return result.astype(numpy.float64)
    
   
