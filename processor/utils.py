"""Functions for calculation of pulse energy and pulse energy density of optical laser.
Calibration values taken from Pump beam energy converter 800 400.xls
Units are uJ for energy, um for beam diameter, uJ/cm^2 for energy density (and arb. for diode signal)"""

import sys, os
import numpy as np
import h5py
import configparser

#================================================================================

def PulseEnergy400(Diode):
    """ Returns the pulse energy of 400nm laser in uJ.

	:param Diode: value from photodiode (arb. units)
	um for beam diameter, uJ/cm^2 for energy density.
	"""
    return 0.86 * (Diode * 0.0008010439 + 0.0352573)


def PulseEnergy800(Diode):
    """ Returns the pulse energy of 800nm laser in uJ.

	:param Diode: value from photodiode (arb. units)
	um for beam diameter, uJ/cm^2 for energy density.
	"""
    return 0.86 * (Diode * 0.0009484577 + 0.1576)


def EnergyDensity400(Diode, Diameter=600):
    """ Returns the pulse energy density of 400nm laser in uJ/cm^2.

	:param Diode: value from photodiode (arb. units)
	um for beam diameter, uJ/cm^2 for energy density.
	"""
    return PulseEnergy400(Diode) / (np.pi * np.square((Diameter * 0.0001) / 2))


def EnergyDensity800(Diode, Diameter=600):
    """ Returns the pulse energy density of 800nm laser in uJ/cm^2.

	:param Diode: value from photodiode (arb. units)
	um for beam diameter, uJ/cm^2 for energy density
	"""
    return PulseEnergy800(Diode) / (np.pi * np.square((Diameter * 0.0001) / 2))

#================================================================================

def radius(df, center=(0, 0)):
    return np.sqrt(np.square(df.posX - center[0]) + np.square(df.posY - center[1]))

#================================================================================

def save_HDF5_timestack_XYET(data_array, filename, path=None, overwrite=True):
    """ Saves an hdf5 file with 4D (Kx,Ky,E,Time) images for import in FIJI

    Parameters:
        data_array (np.array): 4D data array, order must be Kx,Ky,Energy,Time
        filename (str): name of the file to save
        path (str, optional): path to where to save hdf5 file. If None, uses the "results" folder from SETTINGS.ini
        overwrite (str): if true, it overwrites existing file with the same
        	name. Otherwise raises and error.
    """
    # TODO: merge path and filename in one input variable.

    mode = "w-"  # fail if file exists
    if overwrite:
        mode = "w"

    if path is None:
        settings = configparser.ConfigParser()
        settings.read('SETTINGS.ini')
        path = settings['paths']['RESULTS_PATH']

    filepath = path + filename

    if not os.path.isdir(path):
        os.makedirs(path)
    if os.path.exists(filepath):  # create new files every time, with new trailing number
        i = 1
        new_filepath = filepath + "_1"
        while os.path.exists(new_filepath):
            new_filepath = filepath + "_{}".format(i)
            i += 1
        filepath = new_filepath

    f = h5py.File(filepath, mode)
    pumpProbeTimeSteps = len(data_array[..., :])
    print('Creating HDF5 dataset with {} time steps'.format(pumpProbeTimeSteps))

    for timeStep in range(pumpProbeTimeSteps):
        xyeData = data_array[..., timeStep]
        dset = f.create_dataset("experiment/xyE_tstep{}".format(timeStep), xyeData.shape, dtype='float64')
        dset[...] = xyeData
    print("Created file " + filepath)

#================================================================================


def camelCaseIt(snake_str):
    first, *others = snake_str.split('_')
    return ''.join([first.lower(), *map(str.title, others)])


#================================================================================


def t2e(t):
    offs=371.258
    oo=323.98

    e= 0.5*1e18*9.10938e-31/(((t)-offs)*((t)-offs))/1.602177e-19-oo
    return e

def e2t(e):
    offs=371.258
    oo=323.98

    t= np.sqrt(0.5*1e18*9.10938e-31/1.602177e-19/(e+oo))+offs
    return t

