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

"""
  This class is used to process the hdf5 files from the FLASH DAQ-System
  and generate two clean tables: One ordered according to single electron
  events on the delayline detector (DLD) and one according to the
  pulse structure of the machine. This file needs to be modified on a
  beamtime-to-beamtime basis.
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
from imp import reload
import pylab as pl

import DldProcessor
reload(DldProcessor)

import sys
sys.path.append("/home/pg2user/PAH")
from camp.pah.beamtimedaqaccess import BeamtimeDaqAccess


"""
  This class reads an existing run and generates a hdf5 file containing the dask data frames.
  It is intended to be used with data generated from August 31, 2017 to September 19, 2017.
  This version enables read out of macrobunchID. For evaluation the start ID is set to zero.
  As both data channels containing this information are not recognized as channels by h5filedataaaccess,
  this file has been modified s. t. its isValidChannel always returns True. (Workaround, change if possible!!!)
  Had to change the delay stage channel, as the old one (.../ENC.DELAY) stored groups of ~10 times the same value
  (is probably read out with 10 Hz. The new channel is the column (index!) one of .../ENC.
  This change makes the treatment of problematic runs obsolete.
"""
defaultPath = '/home/pg2user/copiedFiles/beamtime'
class DldFlashProcessor(DldProcessor.DldProcessor):
    
    """
      The constructor sets the time step for the DLD-TCD in ns
    """
    def __init__(self):
        super().__init__()
        #self.dldTimeStep = 0.00685 # ns
        self.dldTimeStep = 0.0205761316872428 # ns
        

    """
      Read a run (the run number must be specified). The data is
      expected to be in "/home/pg2user/copiedFiles" (needs to be
      changed for later analysis after the beam time)
    """    
    def readRun(self, runNumber, path=defaultPath):
        # Import the dataset
        dldPosXName = "/uncategorised/FLASH1_USER2/FLASH.FEL/HEXTOF.DAQ/DLD1:0/dset"
        dldPosYName = "/uncategorised/FLASH1_USER2/FLASH.FEL/HEXTOF.DAQ/DLD1:1/dset"
        dldTimeName = "/uncategorised/FLASH1_USER2/FLASH.FEL/HEXTOF.DAQ/DLD1:3/dset"
        
        dldMicrobunchIdName = "/uncategorised/FLASH1_USER2/FLASH.FEL/HEXTOF.DAQ/DLD1:2/dset"
        dldAuxName = "/uncategorised/FLASH1_USER2/FLASH.FEL/HEXTOF.DAQ/DLD1:4/dset"
        #delayStageName = "/Experiment/Pump probe laser/laser delay"
        #ENC.DELAY seems to be the wrong channel! Values appear in groups of exactly the same value 
        #delayStageName = "/Experiment/Pump probe laser/delay line IK220.0/ENC.DELAY"
        #Proper channel is column with index 1 of ENC
        delayStageName = "/Experiment/Pump probe laser/delay line IK220.0/ENC"

        bamName = '/Electron Diagnostic/BAM/4DBC3/electron bunch arrival time (low charge)'
        bunchChargeName = '/Electron Diagnostic/Bunch charge/after undulator'
        macroBunchPulseIdName = '/Timing/Bunch train info/index 1.sts'
        opticalDiodeName ='/Experiment/PG/SIS8300 100MHz ADC/CH9/pulse energy/TD'
        gmdTunnelName ='/Photon Diagnostic/GMD/Pulse resolved energy/energy tunnel'
        
        #adc1Name = '/Experiment/PG/SIS8300 100MHz ADC/CH6/TD'
        #adc2Name = '/Experiment/PG/SIS8300 100MHz ADC/CH7/TD'
        
        daqAccess= BeamtimeDaqAccess.create(path)
        
        print('reading DAQ data')
        #~ print("reading dldPosX")
        self.dldPosX, otherStuff = daqAccess.allValuesOfRun(dldPosXName, runNumber)
        print('run contains macrobunchID from ',otherStuff[0],' to ',otherStuff[1])
        #~ print("reading dldPosY") 
        self.dldPosY, otherStuff = daqAccess.allValuesOfRun(dldPosYName, runNumber)
        #~ print("reading dldTime")
        self.dldTime, otherStuff = daqAccess.allValuesOfRun(dldTimeName, runNumber)
        #~ print("reading dldMicrobunchId")
        self.dldMicrobunchId, otherStuff = daqAccess.allValuesOfRun(dldMicrobunchIdName, runNumber)
        #~ print("reading dldAux")
        self.dldAux, otherStuff = daqAccess.allValuesOfRun(dldAuxName, runNumber)
        
        #~ print("reading delayStage")
        self.delaystage, otherStuff = daqAccess.allValuesOfRun(delayStageName, runNumber)
        self.delaystage = self.delaystage[:,1]
        
        #~ print("reading BAM")
        self.bam, otherStuff = daqAccess.allValuesOfRun(bamName, runNumber)
        self.opticalDiode, otherStuff = daqAccess.allValuesOfRun(opticalDiodeName, runNumber)
        #~ print("reading bunchCharge")
        self.bunchCharge, otherStuff = daqAccess.allValuesOfRun(bunchChargeName, runNumber)
        self.macroBunchPulseId, otherStuff = daqAccess.allValuesOfRun(macroBunchPulseIdName, runNumber)
        self.macroBunchPulseId -= otherStuff[0]
        self.gmdTunnel, otherStuff = daqAccess.allValuesOfRun(gmdTunnelName, runNumber)
        electronsToCount = self.dldPosX.copy().flatten()
        electronsToCount =numpy.nan_to_num(electronsToCount)
        electronsToCount = electronsToCount[electronsToCount > 0]
        electronsToCount = electronsToCount[electronsToCount < 10000]
        numOfElectrons = len(electronsToCount)
        print("Number of electrons: " + str(numOfElectrons))
        print("Creating data frame: Please wait...")
        self.createDataframePerElectron()
        self.createDataframePerMicrobunch()
        print('dataframe created')
        
        
        
        
        
    def readInterval(self, pulseIdInterval, path=defaultPath):
        """
        Access to data by macrobunch pulseID intervall. Usefull for scans that would otherwise hit the machine's
        memory limit.
        """
        # Import the dataset
        dldPosXName = "/uncategorised/FLASH1_USER2/FLASH.FEL/HEXTOF.DAQ/DLD1:0/dset"
        dldPosYName = "/uncategorised/FLASH1_USER2/FLASH.FEL/HEXTOF.DAQ/DLD1:1/dset"
        dldTimeName = "/uncategorised/FLASH1_USER2/FLASH.FEL/HEXTOF.DAQ/DLD1:3/dset"
        
        dldMicrobunchIdName = "/uncategorised/FLASH1_USER2/FLASH.FEL/HEXTOF.DAQ/DLD1:2/dset"
        dldAuxName = "/uncategorised/FLASH1_USER2/FLASH.FEL/HEXTOF.DAQ/DLD1:4/dset"
        #delayStageName = "/Experiment/Pump probe laser/laser delay"
        #ENC.DELAY seems to be the wrong channel! Values appear in groups of ~10 identical values
        #-> ENC.DELAY is read out with 1 Hz
        #delayStageName = "/Experiment/Pump probe laser/delay line IK220.0/ENC.DELAY"
        #Proper channel is culumn with index 1 of ENC
        delayStageName = "/Experiment/Pump probe laser/delay line IK220.0/ENC"

        bamName = '/Electron Diagnostic/BAM/4DBC3/electron bunch arrival time (low charge)'
        bunchChargeName = '/Electron Diagnostic/Bunch charge/after undulator'
        macroBunchPulseIdName = '/Timing/Bunch train info/index 1.sts'
        opticalDiodeName ='/Experiment/PG/SIS8300 100MHz ADC/CH9/pulse energy/TD'
        gmdTunnelName ='/Photon Diagnostic/GMD/Pulse resolved energy/energy tunnel'
        
        #adc1Name = '/Experiment/PG/SIS8300 100MHz ADC/CH6/TD'
        #adc2Name = '/Experiment/PG/SIS8300 100MHz ADC/CH7/TD'
        
        
        daqAccess= BeamtimeDaqAccess.create(path)
        
        print('reading DAQ data')
        #~ print("reading dldPosX")
        self.dldPosX= daqAccess.valuesOfInterval(dldPosXName, pulseIdInterval)
        #~ print("reading dldPosY") 
        self.dldPosY = daqAccess.valuesOfInterval(dldPosYName, pulseIdInterval)
        #~ print("reading dldTime")
        self.dldTime= daqAccess.valuesOfInterval(dldTimeName, pulseIdInterval)
        #~ print("reading dldMicrobunchId")
        self.dldMicrobunchId= daqAccess.valuesOfInterval(dldMicrobunchIdName, pulseIdInterval)
        #~ print("reading dldAux")
        self.dldAux= daqAccess.valuesOfInterval(dldAuxName, pulseIdInterval)
        
        #~ print("reading delayStage")
        self.delaystage= daqAccess.valuesOfInterval(delayStageName, pulseIdInterval)
        self.delaystage = self.delaystage[:,1]
        
        #~ print("reading BAM")
        self.bam= daqAccess.valuesOfInterval(bamName, pulseIdInterval)
        self.opticalDiode= daqAccess.valuesOfInterval(opticalDiodeName, pulseIdInterval)
        #~ print("reading bunchCharge")
        self.bunchCharge= daqAccess.valuesOfInterval(bunchChargeName, pulseIdInterval)
        self.macroBunchPulseId = daqAccess.valuesOfInterval(macroBunchPulseIdName, pulseIdInterval)
        #self.macroBunchPulseId -= self.macroBunchPulseId[self.macroBunchPulseId > 0].min()
        self.macroBunchPulseId -= pulseIdInterval[0]
        self.gmdTunnel= daqAccess.valuesOfInterval(gmdTunnelName, pulseIdInterval)
        electronsToCount = self.dldPosX.copy().flatten()
        electronsToCount =numpy.nan_to_num(electronsToCount)
        electronsToCount = electronsToCount[electronsToCount > 0]
        electronsToCount = electronsToCount[electronsToCount < 10000]
        numOfElectrons = len(electronsToCount)
        print("Number of electrons: " + str(numOfElectrons))
        print("Creating data frame: Please wait...")
        self.createDataframePerElectron()
        self.createDataframePerMicrobunch()
        print('dataframe created')



    """
      Create a data frame for a range of macrobunches
    """
    def createDataframePerElectronRange(self, mbIndexStart, mbIndexEnd):
        daX = self.dldPosX[mbIndexStart:mbIndexEnd, :].flatten()
        daY = self.dldPosY[mbIndexStart:mbIndexEnd, :].flatten()
       
        dldDetectorId = (self.dldTime[mbIndexStart:mbIndexEnd, :].copy()).astype(int)%2
        daDetectorId = dldDetectorId.flatten()
        
        daTime = self.dldTime[mbIndexStart:mbIndexEnd, :].flatten()
        
        
        # convert the bam data to electron format
        bamArray = DldFlashProcessorCy.assignToMircobunch(self.dldMicrobunchId[mbIndexStart:mbIndexEnd, :].astype(numpy.float64), self.bam[mbIndexStart:mbIndexEnd, :].astype(numpy.float64))
        daBam = bamArray.flatten()
        
        # convert the delay stage position to the electron format
        delaystageArray = numpy.zeros_like(self.dldMicrobunchId[mbIndexStart:mbIndexEnd, :])
        delaystageArray[:,:] =  (self.delaystage[mbIndexStart:mbIndexEnd])[:,None]
        daDelaystage = delaystageArray.flatten()
        
        
        daMicrobunchId = self.dldMicrobunchId[mbIndexStart:mbIndexEnd, :].flatten()
        
        
        # convert the MacroBunchPulseId to the electron format
        macroBunchPulseIdArray = numpy.zeros_like(self.dldMicrobunchId[mbIndexStart:mbIndexEnd, :])
        macroBunchPulseIdArray[:, :] =  (self.macroBunchPulseId[mbIndexStart:mbIndexEnd,0])[:,None]
        daMacroBunchPulseId = macroBunchPulseIdArray.flatten()
        
        bunchChargeArray = DldFlashProcessorCy.assignToMircobunch(self.dldMicrobunchId[mbIndexStart:mbIndexEnd, :].astype(numpy.float64), self.bunchCharge[mbIndexStart:mbIndexEnd, :].astype(numpy.float64))
        daBunchCharge = bunchChargeArray.flatten()
        
        opticalDiodeArray = DldFlashProcessorCy.assignToMircobunch(self.dldMicrobunchId[mbIndexStart:mbIndexEnd, :].astype(numpy.float64), self.opticalDiode[mbIndexStart:mbIndexEnd, :].astype(numpy.float64))
        daOpticalDiode = opticalDiodeArray.flatten()
        
        gmdTunnelArray = DldFlashProcessorCy.assignToMircobunch(self.dldMicrobunchId[mbIndexStart:mbIndexEnd, :].astype(numpy.float64), self.gmdTunnel[mbIndexStart:mbIndexEnd, :].astype(numpy.float64))
        daGmdTunnel = gmdTunnelArray.flatten()
        
       
        # the Aux channel: aux0:
        #aux0Arr= DldFlashProcessorCy.assignToMircobunch(self.dldMicrobunchId[mbIndexStart:mbIndexEnd, :].astype(numpy.float64), self.dldAux[mbIndexStart:mbIndexEnd, 0].astype(numpy.float64))
        #daAux0 = dask.array.from_array(aux0Arr.flatten(), chunks=(chunks))
        
        # the Aux channel: aux1:
        #aux1Arr= DldFlashProcessorCy.assignToMircobunch(self.dldMicrobunchId[mbIndexStart:mbIndexEnd, :].astype(numpy.float64), self.dldAux[mbIndexStart:mbIndexEnd, 1].astype(numpy.float64))
        #daAux1 = dask.array.from_array(aux0Arr.flatten(), chunks=(chunks))
        
        #added macroBunchPulseId at last position
        #da = dask.array.stack([daX, daY, daTime, daDelaystage, daBam, daMicrobunchId, 
        #                       daDetectorId, daBunchCharge, daOpticalDiode,
        #                       daGmdTunnel, daMacroBunchPulseId])
        da = numpy.stack([daX, daY, daTime, daDelaystage, daBam, daMicrobunchId, 
                               daDetectorId, daBunchCharge, daOpticalDiode,
                               daGmdTunnel, daMacroBunchPulseId])
                               
        
        return da
        



    """ 
      Create a data frame from the read arrays (either from the test file or the run number)
    """
    def createDataframePerElectron(self):
        #self.dldTime=self.dldTime*self.dldTimeStep
        maxIndex = self.dldTime.shape[0]
        chunkSize = min(1000000, maxIndex/8)
        numOfPartitions = int(maxIndex / chunkSize)+1
        daList = []
        for i in range(0, numOfPartitions):
            indexFrom = int(i*chunkSize)
            indexTo = int(min(indexFrom + chunkSize, maxIndex))
            result = dask.delayed(self.createDataframePerElectronRange)(indexFrom, indexTo)
            daList.append(result)
        #self.dd = self.createDataframePerElectronRange(0, maxIndex)
        # create the data frame:
        self.daListResult = dask.compute(*daList)
        
        a  = numpy.concatenate(self.daListResult, axis=1)
        da = dask.array.from_array(a.T, chunks=(1000000))
        
        self.dd = dask.dataframe.from_array(da, columns=('posX','posY', 'dldTime', 'delayStageTime', 'bam',
                                                      'microbunchId', 'dldDetectorId',
                                                      'bunchCharge', 'opticalDiode', 'gmdTunnel', 'macroBunchPulseId'))
        
        self.dd = self.dd[self.dd['microbunchId'] > 0]
        self.dd['dldTime'] = self.dd['dldTime'] * self.dldTimeStep
        
        
    """
      Create the data frame ordered by macrobunches.
    """    
    def createDataframePerMicrobunch(self):
        chunks = 1000000
        
        numOfMacrobunches = self.bam.shape[0]
        
        # convert the delay stage position to the electron format
        delaystageArray = numpy.zeros_like(self.bam)
        delaystageArray[:, :] = (self.delaystage[:])[:, None]
       
        daDelaystage = dask.array.from_array(delaystageArray.flatten(), chunks=(chunks))
        
        # convert the MacroBunchPulseId to the electron format
        macroBunchPulseIdArray = numpy.zeros_like(self.bam)
        macroBunchPulseIdArray[:, :] =  (self.macroBunchPulseId[:,0])[:,None]            
        daMacroBunchPulseId = dask.array.from_array(macroBunchPulseIdArray.flatten(), chunks=(chunks))
        
        daBam = dask.array.from_array(self.bam.flatten(), chunks=(chunks))
        numOfMicrobunches = self.bam.shape[1]
       
        # the Aux channel: aux0:
        dldAux0 = self.dldAux[:,0]
        aux0 = numpy.ones(self.bam.shape)*dldAux0[:,None]
        daAux0 = dask.array.from_array(aux0.flatten(), chunks=(chunks))
        # the Aux channel: aux1:
        dldAux1 = self.dldAux[:,1]
        aux1 = numpy.ones(self.bam.shape)*dldAux1[:,None]
        daAux1 = dask.array.from_array(aux1.flatten(), chunks=(chunks))
        
       
        daBunchCharge = dask.array.from_array(self.bunchCharge[:,0:numOfMicrobunches].flatten(), chunks=(chunks))
        
        lengthToPad = numOfMicrobunches - self.opticalDiode.shape[1]
        paddedOpticalDiode = numpy.pad(self.opticalDiode, ((0,0),(0,lengthToPad)), 'constant', constant_values=(0,0))
        daOpticalDiode = dask.array.from_array(paddedOpticalDiode.flatten(), chunks=(chunks))
        
        #Added MacroBunchPulseId
        da = dask.array.stack([daDelaystage, daBam, daAux0, daAux1, daBunchCharge, daOpticalDiode, daMacroBunchPulseId])
        
        # create the data frame:
        self.ddMicrobunches = dask.dataframe.from_array(da.T, 
                                                    columns=('delayStageTime', 'bam', 'aux0', 'aux1', 'bunchCharge', 'opticalDiode', 'macroBunchPulseId'))
                                                    
    """
      Store the data frames as hdf5 file
    """        
    def storeDataframes(self, fileName):
        dask.dataframe.to_hdf(self.dd, fileName, '/electrons')
        dask.dataframe.to_hdf(self.ddMicrobunches, fileName, '/microbunches')
        
    """
      Store the data frames as Parquet files
    """    
    def storeDataframesParquet(self, fileName):
        self.dd.to_parquet(fileName + "_el", compression="UNCOMPRESSED")
        self.ddMicrobunches.to_parquet(fileName + "_mb", compression="UNCOMPRESSED")
    
    """
      Append the data frames to existing Parquet files
    """     
    def appendDataframesParquet(self, fileName):
        self.dd.to_parquet(fileName + "_el", compression="UNCOMPRESSED",append=True,ignore_divisions=True)
        self.ddMicrobunches.to_parquet(fileName + "_mb", compression="UNCOMPRESSED",append=True,ignore_divisions=True)

