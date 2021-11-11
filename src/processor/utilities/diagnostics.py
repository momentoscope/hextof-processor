# -*- coding: utf-8 -*-
"""

@author: Steinn Ymir Agustsson
"""

from .misc import repr_byte_size
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import dask
from dask.diagnostics import ProgressBar


def channel_report(dd):
    """ Generates a table containing relevant statistical quantities on all available channels [EXPENSIVE!!]

    Args:
        dd (dask.DataFrame): Table to analyse

    Returns:
        df (pandas.DataFrame): table with computed values
    Notes:
        Author: Steinn Ymir Agustsson <sagustss@uni-mainz.de>

    """
    print('creating channel report...')
    with ProgressBar():
        chan_dict = {}
        for chan in dd.columns:
            vals = dd[chan].compute()
            clean = vals[np.isfinite(vals)]
            chan_dict[chan] = {}
            chan_dict[chan]['min'] = min(clean)
            chan_dict[chan]['max'] = max(clean)
            chan_dict[chan]['amp'] = chan_dict[chan]['max'] - chan_dict[chan]['min']
            chan_dict[chan]['mean'] = np.mean(clean)
            chan_dict[chan]['std'] = np.std(clean)
            chan_dict[chan]['len'] = len(vals)
            chan_dict[chan]['len_nan'] = len(vals) - len(clean)
            chan_dict[chan]['max_loc'] = vals.idxmax()
            chan_dict[chan]['min_loc'] = vals.idxmin()
            


    df = pd.DataFrame.from_dict(chan_dict).T
    return df

def channel_statistics(dd,columns=None):
    """ Statistical overiview of the dataset.

    The report contains minimum, maximum, amplitude(max-min), mean and standard
    deviation of each column.

    Args:
        dd (dask.DataFrame): Table to analyse
        columns (list,None): list of columns to analyse, if None it checks all
            columns in the dataframe.
    Returns:
        df (pandas.DataFrame): table with computed values
    Notes:
        Author: Steinn Ymir Agustsson <sagustss@uni-mainz.de>

    """
    print('creating channel report...')
    chan_dict = {}
    if columns is None:
        columns = dd.columns
    for chan in columns:
        try:
            vals = dd[chan]
            chan_dict[chan] = {}
            chan_dict[chan]['min'] = vals.min()
            chan_dict[chan]['max'] = vals.max()
            chan_dict[chan]['amp'] = chan_dict[chan]['max'] - chan_dict[chan]['min']
            chan_dict[chan]['mean'] = vals.mean()
            chan_dict[chan]['std'] = vals.std()
#             chan_dict[chan]['len'] = vals.size
#             chan_dict[chan]['len_nan'] = vals.size - vals.isna().size

        except KeyError:
            print(f'No column {chan} in dataframe')

    with ProgressBar():
        d, = dask.compute(chan_dict)
    return pd.DataFrame.from_dict(d)

def binned_array_size(processor):
    """ Prints the expected size in memory of the binned array, computed with
    the current binning parameters"""

    voxels = np.prod([len(x) for x in processor.binAxesList])
    print(repr_byte_size(voxels.astype(np.float64) * 64.))


def plot_channels(processor):
    """ Generates a plot of each available channel.

    Useful for diagnostics on data conditions

    Args:
        processor (DldProcessor): processor instance

    """
    cols = processor.dd.columns
    f, ax = plt.subplots(len(cols) // 2, 2, figsize=(15, 20))
    for i, chan in enumerate(processor.dd.columns):
        vals = processor.dd[chan].compute()
        clean = vals[np.isfinite(vals)]
        start, stop, mean = clean.min(), clean.max(), clean.mean()

        if np.abs((start - mean) / (stop - mean)) > 5:
            start = stop - 2 * mean
        elif np.abs((stop - mean) / (start - mean)) > 5:
            stop = start + 2 * mean

        step = max((stop - start) / 1000, 1)
        x = processor.addBinning(chan, start, stop, step)
        res = processor.computeBinnedData()
        ax[i // 2, i % 2].set_title(chan, fontsize='x-large')
        if len(res) > 1:
            try:
                ax[i // 2, i % 2].plot(x, res)
            except ValueError:
                ax[i // 2, i % 2].plot(x, res[:-1])
        processor.resetBins()


def plot_GMD_vs_bunches(self):
    """ not sure what this was done for...
    """

    f, ax = plt.subplots(1, 2)
    self.resetBins()
    ubId = self.addBinning('dldMicrobunchId', 1, 500, 1)
    result_ubId = self.computeBinnedData()
    ax[0].plot(ubId, result_ubId / max(result_ubId), label='Photoelectron count')
    ax[0].set_title('Microbunch')

    self.resetBins()

    MbId_values = self.dd['macroBunchPulseId'].compute()
    clean = MbId_values[np.isfinite(MbId_values)]
    start, stop, mean = clean.min(), clean.max(), clean.mean()
    if np.abs((start - mean) / (stop - mean)) > 5:
        start = stop - 2 * mean
    elif np.abs((stop - mean) / (start - mean)) > 5:
        stop = start + 2 * mean
    step = max((stop - start) / 1000, 1)

    MbId = self.addBinning('macroBunchPulseId', start, stop, step)
    result_MbId = self.computeBinnedData()
    ax[1].plot(MbId, result_MbId / max(result_MbId), label='Photoelectron count')
    ax[1].set_title('Macrobunch')

    gmd_values = np.nan_to_num(self.dd['gmdBda'].compute())
    ubId_values = self.dd['dldMicrobunchId'].compute()

    gmd_ubId = np.zeros_like(ubId)
    for g, ub in zip(gmd_values, ubId_values):
        ub_idx = int(ub)
        if 0 < ub_idx < len(gmd_ubId):
            gmd_ubId[ub_idx] += g

    gmd_MbId = np.zeros_like(MbId)
    for g, Mb in zip(gmd_values, MbId_values):
        Mb_idx = int(Mb)
        if 0 < Mb_idx < len(gmd_MbId):
            gmd_MbId[Mb_idx] += g

    ax[0].plot(ubId, gmd_ubId / max(gmd_ubId), label='GMD')
    ax[1].plot(MbId, gmd_MbId / max(gmd_MbId) + 1, label='GMD')
    for a in ax:
        a.legend()
        a.grid()
