"""
  Copyright 2017-2018, Yves Acremann
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


import numpy
import math
cimport numpy
DTYPE = numpy.float
ctypedef numpy.float_t DTYPE_t

"""
  Here we define a method to convert an array ordered as (macrobunch, microbunch) into (macrobunch, electron).
  This is needed, for example, to convert bam data into tle electron table.
"""
def assignToMircobunch(numpy.ndarray[DTYPE_t, ndim = 2] microbunchIds, numpy.ndarray[DTYPE_t, ndim = 2] toConvert):
    assert microbunchIds.shape[0] == toConvert.shape[0]
    assert microbunchIds.dtype == DTYPE and toConvert.dtype == DTYPE
    
    cdef int numOfMicrobunches
    cdef int numOfElectrons
    cdef int numOfMacrobunches
    numOfMicrobunches = toConvert.shape[1]
    numOfElectrons = microbunchIds.shape[1]
    numOfMacrobunches = microbunchIds.shape[0]
    
    cdef int macro
    cdef int el
    cdef float microbunchId
    cdef int intMicrobunchId
    cdef numpy.ndarray[DTYPE_t, ndim = 2] result = numpy.zeros([numOfMacrobunches, numOfElectrons], dtype=DTYPE)
    cdef float value
    for macro in range(0, numOfMacrobunches):
        
        for el in range(0, numOfElectrons):
            
            microbunchId = microbunchIds[macro, el]
            if (math.isnan(microbunchId)):
                result[macro, el] =math.nan
                continue
                    
            if (microbunchId < 0):
                result[macro, el] = math.nan
                continue
            
            if (microbunchId >= numOfMicrobunches):
                result[macro, el] = math.nan
                continue
        
            # if everything is OK:
            intMicrobunchId = int(microbunchId)
            result[macro, el] = toConvert[macro, intMicrobunchId]
                
    return result

