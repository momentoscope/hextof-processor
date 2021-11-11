import numpy
import math
cimport numpy

DTYPE = numpy.float
ctypedef numpy.float_t DTYPE_t
# from cython.parallel import prange

# Here we define a method to convert an array ordered as (macrobunch, microbunch) into (macrobunch, electron).
# This is needed, for example, to convert bam data into the electron table.

#def assignToMircobunch(microbunchIds, toConvert):
def assignToMircobunch(numpy.ndarray[DTYPE_t, ndim = 2] microbunchIds, numpy.ndarray[DTYPE_t, ndim = 2] toConvert):
    """ Convert array from (mab,mib) to (mab,el)
    Here we define a method to convert an array ordered as (macrobunch, microbunch) into (macrobunch, electron).
    This is needed, for example, to convert bam data into the electron table.
    """
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
                result[macro, el] = math.nan
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
