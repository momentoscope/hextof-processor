# -*- coding: utf-8 -*-
"""

@author: Steinn Ymir Agustsson
"""

""" The purpouse of this script is to test and time the performance of reading and binning methods."""

from datetime import datetime
import sys,os
# print(os.getcwd())
# os.chdir('../')
# print(os.getcwd())
# sys.path.append(os.getcwd())

import time
import processor.DldFlashDataframeCreator as DldFlashProcessor
import matplotlib.pyplot as plt
import argparse


parser = argparse.ArgumentParser(description='Bin data')
parser.add_argument('-run', dest='runNumber', metavar='N', type=int,
                    help='an integer for the accumulator')
# parser.add_argument('--clean', dest='clean', action='store_true',
#                     help='removes options from current SETTINGS.ini that are not standard (default: keeps everything)')
args = parser.parse_args()
# runNumber = None
runNumber = args.runNumber
# clean = args.clean


time.sleep(1)
if runNumber is None:
    runNumber = input("Please choose a run number: ")


t0 = datetime.now()
times = {}
processor = DldFlashProcessor.DldFlashProcessor()
processor.runNumber = runNumber

processor.readDataframes()


last_t = t0
times['readData'] = datetime.now() - last_t
last_t = datetime.now()

# processor.storeDataframes()
times['storeDataframes'] = datetime.now() - last_t
last_t = datetime.now()

processor.postProcess()
processor.addBinning('delayStage',-57,-42,0.5)
processor.addBinning('dldTime', 620, 670, 1)
processor.addBinning('dldPosX',480,980,5)
processor.addBinning('dldPosY',480,980,5)

result = processor.computeBinnedData(saveName='full')

times['bin_3d'] = datetime.now() - last_t
last_t = datetime.now()

time.sleep(1)

print("Total time: {} s".format(datetime.now() - t0))
print("Reading data: {}".format(times['readData']))
print("1D binning, : {}".format(times['bin_3d']))

# plt.imshow(result.sum(axis=0))
# plt.show()
