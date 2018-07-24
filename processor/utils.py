# -*- coding: utf-8 -*-

import sys
import os
import numpy as np
import h5py
import configparser
from matplotlib import pyplot as plt, cm


# ================================================================================
"""Functions for calculation of pulse energy and pulse energy density of optical laser.
Calibration values taken from Pump beam energy converter 800 400.xls
Units are uJ for energy, um for beam diameter, uJ/cm^2 for energy density (and arb. for diode signal)
"""

def PulseEnergy400(Diode):
    """Calculate the pulse energy of 400nm laser in uJ. The unit is um for beam diameter.
    
        :Parameter:
            Diode : numeric
                Measured value from photodiode (arb. units)
    """
    return 0.86 * (Diode * 0.0008010439 + 0.0352573)


def PulseEnergy800(Diode):
    """Calculate the pulse energy of 800nm laser in uJ. The unit is um for beam diameter.
    
        :Parameter:
            Diode : numeric
                Meausred value from photodiode (arb. units)
    """

    return 0.86 * (Diode * 0.0009484577 + 0.1576)


def EnergyDensity400(Diode, Diameter=600):
    """Calculate the pulse energy density of 400nm laser in uJ/cm^2.
    The units are um for beam diameter, uJ/cm^2 for energy density.
    
    :Parameters:
        Diode : numeric
            Measured value from photodiode (arb. units)
        Diameter : numeric
            Beam diameter
    """

    return PulseEnergy400(Diode) / (np.pi * np.square((Diameter * 0.0001) / 2))


def EnergyDensity800(Diode, Diameter=600):
    """Calculate the pulse energy density of 800nm laser in uJ/cm^2.
    The units are um for beam diameter, uJ/cm^2 for energy density.
    
    :Parameters:
        Diode : numeric
            Measured value from photodiode (arb. units)
        Diameter : numeric
            Beam diameter
    """

    return PulseEnergy800(Diode) / (np.pi * np.square((Diameter * 0.0001) / 2))


# ================================================================================


def radius(df, center=(0, 0)):
    """ Calculate the radius
    """

    return np.sqrt(np.square(df.posX - center[0]) + np.square(df.posY - center[1]))


def argnearest(array, val, rettype='vectorized'):
    """Find the coordinates of the nD array element nearest to a specified value

    :Parameters:
        array : numpy array
            Numeric data array
        val : numeric
            Look-up value
        rettype : str | 'vectorized'
            return type specification
            'vectorized' denotes vectorized coordinates (integer)
            'coordinates' denotes multidimensional coordinates (tuple)
    :Return:
        argval : numeric
            coordinate position
    """

    vnz = np.abs(array - val)
    argval = np.argmin(vnz)

    if rettype == 'vectorized':
        return argval
    elif rettype == 'coordinates':
        return np.unravel_index(argval, array.shape)


# ================================================================================
"""Output ImageJ/Fiji-compatible format
"""

def save_H5_hyperstack(data_array, filename, path=None, overwrite=True):
    """ Saves an hdf5 file with 4D (Kx,Ky,E,Time) images for import in FIJI

    :Parameters:
        data_array : numpy array
            4D data array, order must be Kx,Ky,Energy,Time
        filename : str
            The name of the file to save
        path : str
            The path to where to save hdf5 file. If None, uses the "results" folder from SETTINGS.ini
        overwrite : str
            If true, it overwrites existing file with the same
            name. Otherwise raises and error.
    """

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
    if os.path.exists(
            filepath):  # create new files every time, with new trailing number
        i = 1
        new_filepath = filepath + "_1"
        while os.path.exists(new_filepath):
            new_filepath = filepath + "_{}".format(i)
            i += 1
        filepath = new_filepath

    f = h5py.File(filepath, mode)
    pumpProbeTimeSteps = len(data_array[..., :])
    print(
        'Creating HDF5 dataset with {} time steps'.format(pumpProbeTimeSteps))

    for timeStep in range(pumpProbeTimeSteps):
        xyeData = data_array[..., timeStep]
        dset = f.create_dataset(
            "experiment/xyE_tstep{}".format(timeStep),
            xyeData.shape,
            dtype='float64')
        dset[...] = xyeData
    
    print("Created file " + filepath)


# ================================================================================

# def camelCaseIt_onlyPython3(snake_str):
#     first, *others = snake_str.split('_')
#     return ''.join([first.lower(), *map(str.title, others)])


def camelCaseIt(snake_case_string):
    """ Format a string in camel case
    """

    titleCaseVersion = snake_case_string.title().replace("_", "")
    camelCaseVersion = titleCaseVersion[0].lower() + titleCaseVersion[1:]
    
    return camelCaseVersion


# ================================================================================
""" The following functions convert between binding energy (Eb) in eV (negative convention)
    and time of flight (ToF) in ns.
    
    The formula used is based on the ToF for an electron with a kinetic energy Ek. Then the
    binding energy Eb is given by
    
    Eb = Ek+W-hv-V = 1/2 m*v*v +W-hv-V
    
    With W the work function, hv the photon energy, V the electrostatic potential applied to
    the sample, v the velocity of the electrons in the drift tube, m the mass of the electron.
    The velocity v in the drift tube can be calculated knowing the length (1m) and the flight
    time in the drift tube. The measured ToF, however, has some offset due to clock start not
    coinciding with entry in the drift section.

    offs is supposed to include the time offset for when the electrons enter the drift section.
    Its main mainly affects peak spacing, and there are several strategies for calibrating this
    value:
    1.  By measuring the photon peak and correcting by some extractor voltage-dependent offset
    2.  Shifting the potential by 1V and imposing the same shift in the measured spectrum
    3.  Imposing some calibrated spacing between features in a spectrum

    oo is supposed to include -W+hv+V. It mainly affects absolute position of the peaks, and
    there are several strategies for calibrating this value:
    1.  By getting the correct values for W, hv, and V
    2.  It can be calibrated by imposing peak position

Parameters:
    t (float) the ToF
    e (float) the binding energy
"""


def t2e(t, toffset=None, eoffset=None):
    """ Transform ToF to eV.

    The functions (t2e and e2t) convert between binding energy (:math:`E_b`) in eV (negative convention)
    and time of flight (ToF) in ns.
    
    The formula used is based on the ToF for an electron with a kinetic energy :math:`E_k`. Then the
    binding energy :math:`E_b` is given by
    
    -Eb = Ek+W-hv-V = 1/2 m*v*v +W-hv-V
    
    With W the work function, hv the photon energy, V the electrostatic potential applied to
    the sample with respect to the drift section voltage, v the velocity of the electrons in the drift tube,
    m the mass of the electron.
    
    The velocity v in the drift tube can be calculated knowing the length (1m) and the flight
    time in the drift tube. The measured ToF, however, has some offset due to clock start not
    coinciding with entry in the drift section.

    toffset is supposed to include the time offset for when the electrons enter the drift section.
    Its main mainly affects peak spacing, and there are several strategies for calibrating this value,
    
    1.  By measuring the photon peak and correcting by some extractor voltage-dependent offset
    2.  Shifting the potential by 1V and imposing the same shift in the measured spectrum
    3.  Imposing some calibrated spacing between features in a spectrum

    eoffset is supposed to include -W+hv+V. It mainly affects absolute position of the peaks, and
    there are several strategies for calibrating this value,
    
    1.  By getting the correct values for W, hv, and V
    2.  It can be calibrated by imposing peak position

    :Parameters:
        t : float
            The time of flight
        toffset : float
            The time offset from thedld clock start to when the fastest photoelectrons reach the detector
        eoffset : float
            The energy offset given by W-hv-V

    :Return:
        e : float
            The binding energy
    """

    from configparser import ConfigParser
    settings = ConfigParser()
    if os.path.isfile(os.path.join(os.path.dirname(__file__), 'SETTINGS.ini')):
        settings.read(os.path.join(os.path.dirname(__file__), 'SETTINGS.ini'))
    else:
        settings.read(
            os.path.join(
                os.path.dirname(os.path.dirname(__file__)), 'SETTINGS.ini'))

    if toffset is None:
        toffset = float(settings['processor']['ET_CONV_T_OFFSET'])
    if eoffset is None:
        eoffset = float(settings['processor']['ET_CONV_E_OFFSET'])
    e = 0.5 * 1e18 * 9.10938e-31 / (((t) - toffset) *
                                    ((t) - toffset)) / 1.602177e-19 - eoffset
    return e


def e2t(e, toffset=None, eoffset=None):
    """ Transform eV to time of flight (ToF).

    The functions (t2e and e2t) convert between binding energy (:math:`E_b`) in eV (negative convention)
    and time of flight (ToF) in ns.
    
    The formula used is based on the ToF for an electron with a kinetic energy :math:`E_k`. Then the
    binding energy :math:`E_b` is given by
    
    -Eb = Ek+W-hv-V = 1/2 m*v*v +W-hv-V
    
    With W the work function, hv the photon energy, V the electrostatic potential applied to
    the sample, v the velocity of the electrons in the drift tube, m the mass of the electron.
    The velocity v in the drift tube can be calculated knowing the length (1m) and the flight
    time in the drift tube. The measured ToF, however, has some offset due to clock start not
    coinciding with entry in the drift section.

    offs is supposed to include the time offset for when the electrons enter the drift section.
    Its main mainly affects peak spacing, and there are several strategies for calibrating this value,
    
    1.  By measuring the photon peak and correcting by some extractor voltage-dependent offset
    2.  Shifting the potential by 1V and imposing the same shift in the measured spectrum
    3.  Imposing some calibrated spacing between features in a spectrum

    eoffset is supposed to include -W+hv+V. It mainly affects absolute position of the peaks, and
    there are several strategies for calibrating this value,
    
    1.  By getting the correct values for W, hv, and V
    2.  It can be calibrated by imposing peak position

    :Parameters:
        e : float
            The binding energy
        toffset : float
            The time offset from thedld clock start to when the fastest photoelectrons reach the detector
        eoffset : float
            The energy offset given by W-hv-V

    :Return:
        t : float
            The time of flight
    """

    from configparser import ConfigParser
    settings = ConfigParser()
    if os.path.isfile(os.path.join(os.path.dirname(__file__), 'SETTINGS.ini')):
        settings.read(os.path.join(os.path.dirname(__file__), 'SETTINGS.ini'))
    else:
        settings.read(
            os.path.join(
                os.path.dirname(os.path.dirname(__file__)), 'SETTINGS.ini'))

    if toffset is None:
        toffset = float(settings['processor']['ET_CONV_T_OFFSET'])
    if eoffset is None:
        eoffset = float(settings['processor']['ET_CONV_E_OFFSET'])
    t = np.sqrt(0.5 * 1e18 * 9.10938e-31 / 1.602177e-19 / (e + eoffset)) + toffset
    return t

# ------------------------------------------------------------------------------
# ------------------------------------------------------------------------------


def plot_lines(data,
               normalization='None',
               range=None,
               color_range=(0, 1),
               x_label='',
               y_label='',
               xlim=None,
               ylim=None,
               savefig=False,
               save_dir='E:/data/FLASH/',
               save_name='fig',
               static_curve=None):
    """

    :Parameters:
        data :
            
        normalization :
            
        range :
            
        color_range :
            
    """

    f, axis = plt.subplots(1, 1, figsize=(8, 6), sharex=True)

    if range is None:
        from_ = 0
        to_ = len(data[:, ...])
    else:
        from_ = range[0]
        to_ = range[1]

    n_curves = len(data[from_:to_, 0])
    print(n_curves)
    cm_subsection = np.linspace(color_range[0], color_range[1], n_curves)
    colors = [cm.coolwarm(1 - x) for x in cm_subsection]

    for i, color in enumerate(colors[from_:to_]):
        label = '{}'.format(i)  # 20*(i+from_),
        curve = data[i + from_, :]  # result_unpumped[i]
        if normalization == 'sum':
            curve /= curve.sum()
        elif normalization == 'max':
            curve /= curve.max()

        axis.plot(curve, '-', color=color, label=label)
    #    axis[1].plot(x_axis_energy,curve_pump, '-', color=color,label=label)
    if static_curve is not None:
        plt.plot(static_curve, '--', color='black', label='static')
    plt.grid()
    plt.legend(fontsize='large')
    plt.xlabel(x_label, fontsize='xx-large')
    plt.ylabel(y_label, fontsize='xx-large')
    plt.xticks(fontsize='large')
    plt.yticks(fontsize='large')
    if xlim is not None:
        plt.xlim(xlim[0], xlim[1])
    if ylim is not None:
        plt.ylim(ylim[0], ylim[1])

    if savefig:
        plt.savefig(
            '{}{}.png'.format(save_dir, save_name),
            dpi=200,
            facecolor='w',
            edgecolor='w',
            orientation='portrait',
            papertype=None,
            format=None,
            transparent=True,
            bbox_inches=None,
            pad_inches=0.1,
            frameon=None)
    plt.show()


def get_idx(array, value):
    """ **[DEPRECATED]** Use argnearest
    """
    return (np.abs(array - value)).argmin()

def load_results(filename, path=None):
    # load the data saved with processor.save_array()
    
    pass

def get_available_runs(rootpath): # TODO: store the resulting dictionary to improve performance.
    """ returns a dictionary with paths to the data of available runs.

    :parameters:
        rootpath : str
            path where to look for data (recursive in subdirectories)
    :return:
        available_runs : dict
            dict with run numbers as keys (eg: 'run12345') and path where to load data from as str.
    """
    available_runs = {}
    for dir in os.walk(rootpath):
        if 'fl1user2' in dir[0]:
            try:
                run_path = dir[0][:-8]
                for name in dir[2]:
                    runNumber = name.split('_')[4]
                    if runNumber not in available_runs:
                        available_runs[runNumber] = run_path
            except: # TODO: use an assertion method for more solid error tracking.
                pass
    return available_runs

def get_path_to_run(runNumber, rootpath):
    """ Returns the path to the raw data of given runNumber

    :parameters:
        runNumber : str or int
            run number as integer or string.
        rootpath : str
            path where to look for data (recursive in subdirectories)


    :return:
        path : str
            path to where the raw data of the given run number is stored.
    """
    available_runs = get_available_runs(rootpath)
    try:
        return(available_runs['run{}'.format(runNumber)])
    except KeyError:
        raise KeyError('No run number {} under path {}'.format(runNumber,rootpath))