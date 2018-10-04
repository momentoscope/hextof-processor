# -*- coding: utf-8 -*-
"""

@author: Steinn Ymir Agustsson
"""
import processor.DldFlashDataframeCreator as DldFlashProcessor
from utilities.misc import get_available_runs

def main():
    print('running')
    prc = DldFlashProcessor.DldFlashProcessor()
    runs = get_available_runs(prc.DATA_RAW_DIR)
    del prc

    print('{} runs found: '.format(len(runs)))
    for run, path in runs.items():
        run_n = int(run[3:])
        print('run: {} path: {}'.format(run_n,path))
        create_dataframe(run_n)

fails = {}

def create_dataframe(runNumber):
    prc = DldFlashProcessor.DldFlashProcessor()
    prc.runNumber = runNumber
    try:
        prc.readData()
        prc.storeDataframes()

    except Exception as E:
        fails[runNumber] = E

    for key, val in fails.items():
        print('{} failed with error {}'.format(key, val))

if __name__ == '__main__':
    main()