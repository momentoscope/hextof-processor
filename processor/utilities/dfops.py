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


def roll_col(df, col, window, sigma):
    """ helper function for rolling_average_on_acquisition_time.

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
        dataframe with '<col>_rolled' with the averaged data. """

    df_ = df.groupby('timeStamp').agg({col:'mean'})
    dfc_ = df.groupby('timeStamp').agg({col:'count'})


    df_[col+'_rolled'] = df_[col].interpolate(method='nearest').rolling(window,center=True,win_type='gaussian').mean(std=window/sigma).fillna(df_[col])
    df_ = df_.drop(df_.columns.difference([col+'_rolled']).tolist(), axis=1)
    
    return pd.DataFrame(df_.values.repeat(dfc_[col], axis=0), columns=df_.columns)



def rolling_average_on_acquisition_time(df,cols,window,sigma=2):
    """ Perform a rolling average with a gaussian weighted window over a list of columns.

        
        :Parameters:
        df : dataframe
            Dataframe to add noise/jittering to.
        cols : list
            list containing the names of the columns on which to perform the rolling average
        window:
            Size of the rolling average window
        sigma:
            number of standard deviations for the gaussian weighting of the window. 
            a value of 2 corresponds to a gaussian with sigma equal to half the window size.
            Smaller values reduce the weighting in the window frame. 
    :Return:
        input dataframe with an additional '<col>_rolled' with the averaged data. """
    for col in cols:
        df[col+'_rolled']=df.map_overlap(roll_col,before=int(window/2),after=int(window/2), col='dldTime',window=window,sigma=sigma)[col+'_rolled']
    
    return df