# -*- coding: utf-8 -*-
"""

@author: Steinn Ymir Agustsson

    Copyright (C) 2018 Steinn Ymir Agustsson

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""
import numpy as np
import pandas as pd
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

    df = pd.DataFrame.from_dict(chan_dict).T
    return df


def main():
    pass


if __name__ == '__main__':
    main()