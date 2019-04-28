# -*- coding: utf-8 -*-

import os
from configparser import ConfigParser
import xarray as xr
import utilities.misc as utils
import h5py
import numpy as np

class BinnedArray(xr.DataArray):
    
    def __init__(self,data=None, coords=None, dims=None, name=None,attrs=None, encoding=None, indexes=None, fastpath=False):
        super(BinnedArray,self).__init__(data, coords=coords, dims=dims, name=name,
            attrs=attrs, encoding=encoding, indexes=indexes, fastpath=fastpath)

    def to_h5(self, file_name, path=None, mode='w'):
        """ Save a binned numpy array to h5 file. The file includes the axes
        (taken from the scheduled bins) and the delay stage histogram, if it exists.

        :Parameters:
            file_name : str
                Name of the saved file. The extension '.h5' is automatically added.
            path : str | None
                File path.
            mode : str | 'w'
                Write mode of h5 file ('w' = write).
        """
        _abort = False

        if path is None:
            path = utils.parse_setting('paths','DATA_H5_DIR')
        if not os.path.isdir(path):  # test if the path exists...
            answer = input("The folder {} doesn't exist,"
                           "do you want to create it? [y/n]".format(path))
            if 'y' in answer:
                os.makedirs(path)
            else:
                _abort = True

        filename = '{}.h5'.format(file_name)
        if os.path.isfile(path + filename):
            answer = input("A file named {} already exists. Overwrite it? "
                           "[y/n or r for rename]".format(filename))
            if answer.lower() in ['y', 'yes', 'ja']:
                pass
            elif answer.lower() in ['n', 'no', 'nein']:
                _abort = True
            else:
                filename = input("choose a new name:")

        if not _abort:
            with h5py.File(path + filename, mode) as h5File:

                print('saving data to {}'.format(path + filename))

                if 'pumpProbeTime' in self.dims:
                    idx = self.dims.index('pumpProbeTime')
                    pp_data = np.swapaxes(self.data, 0, idx)

                elif 'delayStage' in self.dims:
                    idx = self.dims.index('delayStage')
                    pp_data = np.swapaxes(self.data, 0, idx)
                else:
                    pp_data = None

                # Saving data

                ff = h5File.create_group('frames')

                if pp_data is None:  # in case there is no time axis, make a single dataset
                    ff.create_dataset('f{:04d}'.format(0), data=self.data)
                else:
                    for i in range(pp_data.shape[0]):  # otherwise make a dataset for each time frame.
                        ff.create_dataset('f{:04d}'.format(i), data=pp_data[i, ...])

                # Saving axes
                aa = h5File.create_group("axes")
                # aa.create_dataset('axis_order', data=self.dims)
                ax_n = 1
                for binName in self.dims:
                    if binName in ['pumpProbeTime', 'delayStage']:
                        ds = aa.create_dataset('ax0 - {}'.format(binName), data=self.coords[binName])
                        ds.attrs['name'] = binName
                    else:
                        ds = aa.create_dataset('ax{} - {}'.format(ax_n, binName), data=self.coords[binName])
                        ds.attrs['name'] = binName
                        ax_n += 1
                # Saving delay histograms
#                hh = h5File.create_group("histograms")
#                if hasattr(self, 'delaystageHistogram'):
#                    hh.create_dataset(
#                        'delaystageHistogram',
#                        data=self.delaystageHistogram)
#                if hasattr(self, 'pumpProbeHistogram'):
#                    hh.create_dataset(
#                        'pumpProbeHistogram',
#                        data=self.pumpProbeHistogram)\

                for k,v in self.attrs.items():
                    g = h5File.create_group(k)
                    for kk,vv in v.items():
                        try:
                            g.create_dataset(kk,data=vv)
                        except TypeError:
                            if isinstance(vv, dict):
                                for kkk,vvv in vv.items():
                                    g.create_dataset('{}/{}'.format(kk,kkk),data=vvv)
                            else:
                                g.create_dataset(kk,data=str(vv))
                        
    def read_h5(self,filename):
        raise NotImplementedError()

    def read_logbook(self,log_text):
        log = utils.parse_logbook(log_text)
        
        try:
            self.attrs['metadata'] = {**log,**self.attrs['metadata']}        
        except KeyError:
            self.attrs['metadata'] = log

    



