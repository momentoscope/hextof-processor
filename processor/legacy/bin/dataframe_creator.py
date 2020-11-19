# -*- coding: utf-8 -*-
"""

@author: Steinn Ymir Agustsson
"""
import processor.DldFlashDataframeCreator as DldFlashProcessor
from processor.utilities.misc import get_available_runs, create_dataframes

print('running')
prc = DldFlashProcessor.DldFlashProcessor()
runs = get_available_runs(prc.DATA_RAW_DIR)
del prc

print('{} runs found: '.format(len(runs)))
for run, path in runs.items():
    run_n = int(run[3:])
    print('run: {} path: {}'.format(run_n,path))
    create_dataframes(run_n)

fails = {}