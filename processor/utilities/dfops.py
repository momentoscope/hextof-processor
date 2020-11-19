# -*- coding: utf-8 -*-

import numpy as np

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

