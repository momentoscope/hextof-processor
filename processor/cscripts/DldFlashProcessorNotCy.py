# -*- coding: utf-8 -*-
"""

@author: Steinn Ymir Agustsson
"""
import numpy as np
import math

DTYPE = np.float

def main():
    pass


def assignToMircobunch(microbunchIds, toConvert):
    # assert microbunchIds.shape[0] == toConvert.shape[0]
    # assert isinstance(microbunchIds,DTYPE) and isinstance(toConvert,DTYPE)


    numOfMicrobunches = toConvert.shape[1]
    numOfElectrons = microbunchIds.shape[1]
    numOfMacrobunches = microbunchIds.shape[0]

    result = np.zeros([numOfMacrobunches, numOfElectrons], dtype=DTYPE)

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

if __name__ == '__main__':
    main()