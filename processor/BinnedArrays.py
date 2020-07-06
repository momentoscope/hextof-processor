# -*- coding: utf-8 -*-

import os
from configparser import ConfigParser
import xarray as xr
import tifffile
import tempfile
import shutil
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
                # aa.create_dataset('axis_order', data=data.dims)
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
#                if hasattr(data, 'delaystageHistogram'):
#                    hh.create_dataset(
#                        'delaystageHistogram',
#                        data=data.delaystageHistogram)
#                if hasattr(data, 'pumpProbeHistogram'):
#                    hh.create_dataset(
#                        'pumpProbeHistogram',
#                        data=data.pumpProbeHistogram)\

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

    
def res_to_xarray(res, binNames, binAxes, metadata):
    """ creates a BinnedArray (xarray subclass) out of the given np.array

    :Parameters:
        res: np.array
            nd array of binned data
        binNames (list): list of names of the binned axes
        binAxes (list): list of np.arrays with the values of the axes
    :Returns:
        ba: BinnedArray (xarray)
            an xarray-like container with binned data, axis, and all available metadata
    """
    dims = binNames
    coords = {}
    for name, vals in zip(binNames, binAxes):
        coords[name] = vals

    xres = xr.DataArray(res, dims=dims, coords=coords)

    units = {}
    default_units = {'dldTime': 'step', 'delayStage': 'ps', 'pumpProbeDelay': 'ps'}
    for name in binNames:
        try:
            u = default_units[name]
        except KeyError:
            u = None
        units[name] = u
    xres.attrs['units'] = units

    for k,v in metadata.items():
        xres.attrs[k] = v

    return xres

def save_binned(data, file_name, format='h5', path=None, mode='w'):
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
        path = utils.parse_setting('paths', 'DATA_H5_DIR')
    if not os.path.isdir(path):  # test if the path exists...
        answer = input("The folder {} doesn't exist,"
                       "do you want to create it? [y/n]".format(path))
        if 'y' in answer:
            os.makedirs(path)
        else:
            _abort = True

    if format == 'h5':
        filename = '{}.h5'.format(file_name)
    elif 'tif' in format:
        filename = '{}.tiff'.format(file_name)
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
        if format == 'h5':
            xres_to_h5(data, path + filename, mode)
        elif 'tif' in format:
            xres_to_tiff(data, path+filename)
def xres_to_h5(data, faddr, mode):
    """ Save xarray formatted data to hdf5

    Args:
        data (xarray.DataArray): input data
        faddr (str): complete file name (including path)
        mode (str): hdf5 read/write mode

    Returns:

    """
    with h5py.File(faddr, mode) as h5File:

        print(f'saving data to {faddr}')

        if 'pumpProbeTime' in data.dims:
            idx = data.dims.index('pumpProbeTime')
            pp_data = np.swapaxes(data.data, 0, idx)

        elif 'delayStage' in data.dims:
            idx = data.dims.index('delayStage')
            pp_data = np.swapaxes(data.data, 0, idx)
        else:
            pp_data = None

        # Saving data

        ff = h5File.create_group('binned')

        if pp_data is None:  # in case there is no time axis, make a single dataset
            ff.create_dataset('f{:04d}'.format(0), data=data.data)
        else:
            for i in range(pp_data.shape[0]):  # otherwise make a dataset for each time frame.
                ff.create_dataset('f{:04d}'.format(i), data=pp_data[i, ...])

        # Saving axes
        aa = h5File.create_group("axes")
        # aa.create_dataset('axis_order', data=data.dims)
        ax_n = 1
        for binName in data.dims:
            if binName in ['pumpProbeTime', 'delayStage']:
                ds = aa.create_dataset(f'ax0 - {binName}', data=data.coords[binName])
                ds.attrs['name'] = binName
            else:
                ds = aa.create_dataset(f'ax{ax_n} - {binName}', data=data.coords[binName])
                ds.attrs['name'] = binName
                ax_n += 1
        # Saving delay histograms
        #                hh = h5File.create_group("histograms")
        #                if hasattr(data, 'delaystageHistogram'):
        #                    hh.create_dataset(
        #                        'delaystageHistogram',
        #                        data=data.delaystageHistogram)
        #                if hasattr(data, 'pumpProbeHistogram'):
        #                    hh.create_dataset(
        #                        'pumpProbeHistogram',
        #                        data=data.pumpProbeHistogram)\

        meta_group = h5File.create_group('metadata')
        for k, v in data.attrs.items():
            g = meta_group.create_group(k)
            for kk, vv in v.items():
                try:
                    g.create_dataset(kk, data=vv)
                except TypeError:
                    if isinstance(vv, dict):
                        for kkk, vvv in vv.items():
                            g.create_dataset(f'{kk}/{kkk}', data=vvv)
                    else:
                        g.create_dataset(kk, data=str(vv))
        print('Saving complete!')


def xres_to_tiff(data, filename):


    xres = xres.expand_dims({'C': 1, 'S': 1})
    tifffile.imwrite('temp.tif', xres.values.astype(np.float32),
                     imagej=True, )  # resolution=(1./2.6755, 1./2.6755),metadata={'spacing': 3.947368, 'unit': 'um'})