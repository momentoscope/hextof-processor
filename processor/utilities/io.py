# -*- coding: utf-8 -*-

from . import misc
import os

import h5py
import numpy as np
import tifffile
import xarray as xr


default_units = {
    'dldPosX': 'step', 
    'dldPosY': 'step', 
    'dldTime': 'step', 
    'tofVoltage':'V',
    'extractorVoltage':'V',
    'extractorCurrent':'V',
    'cryoTemperature':'K',
    'sampleTemperature':'K',
    'dldTimeBinSize':'ns',
    'delayStage':'ps',
    'streakCamera':'ps',
    'bam':'ps',
    'monochromatorPhotonEnergy':'eV',
    'timeStamp':'s',
    'dldTime_corrected':'ns',
    'energy':'eV',
    'kx':'1/A',
    'ky':'1/A'}

def res_to_xarray(res, binNames, binAxes, metadata=None):
    """ creates a BinnedArray (xarray subclass) out of the given np.array

    Parameters:
        res: np.array
            nd array of binned data
        binNames (list): list of names of the binned axes
        binAxes (list): list of np.arrays with the values of the axes
    Returns:
        ba: BinnedArray (xarray)
            an xarray-like container with binned data, axis, and all available metadata
    """
    dims = binNames
    coords = {}
    for name, vals in zip(binNames, binAxes):
        coords[name] = vals

    xres = xr.DataArray(res, dims=dims, coords=coords)

    for name in binNames:
        try:
            xres[name].attrs['unit'] = default_units[name]
        except KeyError:
            pass

    xres.attrs['units'] = 'counts'
    xres.attrs['long_name'] = 'photoelectron counts'

    if metadata is not None:
        for k, v in metadata.items():
            xres.attrs[k] = v

    return xres


def save_binned(data, file_name, format='h5', path=None, mode='w'):
    """ Save a binned numpy array to h5 file. The file includes the axes
    (taken from the scheduled bins) and the delay stage histogram, if it exists.

    Parameters:
        file_name: str
            Name of the saved file. The extension '.h5' is automatically added.
        path: str | None
            File path.
        mode: str | 'w'
            Write mode of h5 file ('w' = write).
    """
    _abort = False

    if path is None:
        path = misc.parse_setting('paths', 'DATA_H5_DIR') #TODO: generalise to get path from any settings, as in processor.
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
            xarray_to_h5(data, path + filename, mode)
        elif 'tif' in format:
            to_tiff(data, path + filename)


def xarray_to_h5(data, faddr, mode='w'):
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


def array_to_tiff(array,filename):
    """ Save array to imageJ compatible tiff stack.

    Args:
        array (np.array): array to save. 2D,3D or 4D
        filename (str): full path and name of file to save.

    """
    if array.ndim == 2:
        out = np.expand_dims(array,[0,1,2,5])
    elif array.ndim == 3:
        out = np.expand_dims(array,[0,2,5])
    elif array.ndim == 4:
        out = np.expand_dims(array, [2, 5])
    else:
        raise NotImplementedError('Only 2-3-4D arrays supported.')

    tifffile.imwrite(filename, out.astype(np.float32), imagej=True)
    print(f'Successfully saved array with shape {array.shape} to {filename}')


def xarray_to_tiff(data, filename, axis_dict=None):
    """ Save data to tiff file.

    Args:
        data: xarray.DataArray
            data to be saved. ImageJ likes tiff files with
            axis order as TZCYXS. Therefore, best axis order in input should be:
            Time, Energy, posY, posX. The channels 'C' and 'S' are automatically
            added and can be ignored.
        filename: str
            full path and name of file to save.
        axis_dict: dict
            name pairs for correct axis ordering. Keys should be
            any of T,Z,C,Y,X,S. The Corresponding value will be searched among
            the dimensions of the xarray, and placed in the right order for
            imagej stacks metadata.
        units: bool
            Not implemented. Will be used to set units in the tif stack
            TODO: expand imagej metadata to include physical units
    """

    assert isinstance(data, xr.DataArray), 'Data must be an xarray.DataArray'
    dims_to_add = {'C': 1, 'S': 1}
    dims_order = []

    if axis_dict is None:
        axis_dict = {'T': ['delayStage','pumpProbeTime','time'],
                     'Z': ['dldTime','energy'],
                     'C': ['C'],
                     'Y': ['dldPosY','ky'],
                     'X': ['dldPosX','kx'],
                     'S': ['S']}
    else:
        for key in ['T', 'Z', 'C', 'Y', 'X', 'S']:
            if key not in axis_dict.keys():
                axis_dict[key] = key

    # Sort the dimensions in the correct order, and fill with one-point dimensions
    # the missing axes.
    for key in ['T', 'Z', 'C', 'Y', 'X', 'S']:
        axis_name_list = [name for name in axis_dict[key] if name in data.dims]
        if len(axis_name_list) > 1:
            raise AttributeError(f'Too many dimensions for {key} axis.')
        elif len(axis_name_list) == 1:
            dims_order.append(*axis_name_list)
        else:
            dims_to_add[key] = 1
            dims_order.append(key)

    print(f'tif stack dimension order: {dims_order}')
    xres = data.expand_dims(dims_to_add)
    xres = xres.transpose(*dims_order)
    if '.tif' not in filename:
        filename += '.tif'
    try:
        tifffile.imwrite(filename, xres.values.astype(np.float32), imagej=True)
    except:
        tifffile.imsave(filename, xres.values.astype(np.float32), imagej=True)

    # resolution=(1./2.6755, 1./2.6755),metadata={'spacing': 3.947368, 'unit': 'um'})
    print(f'Successfully saved {filename}')


def to_tiff(data,filename,axis_dict=None):
    """ save array to imagej tiff sack."""
    if isinstance(data,xr.DataArray):
        xarray_to_tiff(data,filename,axis_dict=axis_dict)
    elif isinstance(data,np.array):
        array_to_tiff(data,filename)
    else:
        raise TypeError('Input data must be a numpy array or xarray DataArray')
