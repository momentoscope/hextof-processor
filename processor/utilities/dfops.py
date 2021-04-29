# -*- coding: utf-8 -*-

import numpy as np
import pandas as pd
from dask.diagnostics import ProgressBar
def applyJitter(df, amp, col, type):
    """ Add jittering to a dataframe column.

    Adapted from MPES package: https://github.com/mpes-kit/mpes

    :Parameters:
        df : dataframe
            Dataframe to add noise/jittering to.
        amp : numeric
            Amplitude scaling for the jittering noise.
        col : str
            Name of the column to add jittering to.

    :Return:
        Uniformly distributed noise vector with specified amplitude and size.
    """
    colsize = df[col].size

    if (type == 'uniform'):
        # Uniform Jitter distribution
        return df[col] + amp * np.random.uniform(low=-1, high=1, size=colsize)
    elif (type == 'normal'):
        # Normal Jitter distribution works better for non-linear transformations and jitter sizes that don't match the original bin sizes
        return df[col] + amp * np.random.standard_normal(size=colsize)

def rolling_average_on_acquisition_time(df,col,window,sigma=2):
    """ Perform a rolling average with a gaussian weighted window.

        In order to preserve the number of points, the first and last "widnow" 
        number of points are substituted with the original signal.
        
        :Parameters:
        df : dataframe
            Dataframe to add noise/jittering to.
        col : str
            Name of the column on which to perform the rolling average
        window:
            Size of the rolling average window
        sigma:
            number of standard deviations for the gaussian weighting of the window. 
            a value of 2 corresponds to a gaussian with sigma equal to half the window size.
            Smaller values reduce the weighting in the window frame. 
    :Return:
        input dataframe with an additional '<col>_rolled' with the averaged data. """
    with ProgressBar():
        print(f'rolling average over {col}...')
        df_ = df.groupby('timeStamp').agg({col: 'mean'}).compute()
        df_['dt'] = pd.to_datetime(df_.index, unit='s')
        df_['ts'] = df_.index
    #     df['streakCamera'] = df['streakCamera']
        df_[col+'_rolled'] = df_[col].interpolate(method='nearest').rolling(window,center=True,win_type='gaussian').mean(std=window/sigma).fillna(df_[col])
        df_ = df_.drop(col, axis=1)
    return df.merge(df_,left_on='timeStamp',right_on='ts').drop(['ts','dt'], axis=1)