"""Functions for calculation of pulse energy and pulse energy density of optical laser.
Calibration values taken from Pump beam energy converter 800 400.xls
Units are uJ for energy, um for beam diameter, uJ/cm^2 for energy density (and arb. for diode signal)"""

import sys, os
import numpy as np
import h5py
import configparser
from matplotlib import pyplot as plt, cm


# ================================================================================

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


# ================================================================================

def radius(df, center=(0, 0)):
    return np.sqrt(np.square(df.posX - center[0]) + np.square(df.posY - center[1]))


# ================================================================================

def save_H5_hyperstack(data_array, filename, path=None, overwrite=True):
    """ Saves an hdf5 file with 4D (Kx,Ky,E,Time) images for import in FIJI

    Parameters:
        data_array (np.array): 4D data array, order must be Kx,Ky,Energy,Time
        filename (str): name of the file to save
        path (str, optional): path to where to save hdf5 file. If None, uses the "results" folder from SETTINGS.ini
        overwrite (str): if true, it overwrites existing file with the same
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


# ================================================================================


# def camelCaseIt_onlyPython3(snake_str):
#     first, *others = snake_str.split('_')
#     return ''.join([first.lower(), *map(str.title, others)])

def camelCaseIt(snake_case_string):
    titleCaseVersion =  snake_case_string.title().replace("_", "")
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


# TODO: include offs and oo in the SETTINGS.ini file
def t2e(t, offset=None, oo=None):
    """ Transform ToF to eV.

    The functions (t2e and e2t) convert between binding energy (Eb) in eV (negative convention)
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

    Returns:
        e (float) the binding energy
    """
    if offset is None:
        offset = 371.258
    if oo is None:
        oo = 323.98

    e = 0.5 * 1e18 * 9.10938e-31 / (((t) - offset) * ((t) - offset)) / 1.602177e-19 - oo
    return e


def e2t(e, offset=None, oo=None):
    """ Transform eV to ToF.

    The functions (t2e and e2t) convert between binding energy (Eb) in eV (negative convention)
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
        e (float): the binding energy

    returns:
        t (float): the ToF
    """
    if offset is None:
        offset = 371.258
    if oo is None:
        oo = 323.98

    t = np.sqrt(0.5 * 1e18 * 9.10938e-31 / 1.602177e-19 / (e + oo)) + offset
    return t



#------------------------------------------------------------------------------
#------------------------------------------------------------------------------

def plot_lines(data,  normalization='None', range=None, color_range=(0,1),
               x_label='',y_label='', xlim=None, ylim=None,
               savefig=False, save_dir='E:/data/FLASH/', save_name='fig', static_curve=None):
    """

    :param data:
    :param normalization:
    :param range:
    :param color_range:
    :return:
    """
    f, axis = plt.subplots(1, 1, figsize=(8, 6), sharex=True)

    if range is None:
        from_ = 0
        to_= len(data[:,...])
    else:
        from_ = range[0]
        to_ = range[1]


    n_curves = len(data[from_:to_,0])
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
        plt.xlim(xlim[0],xlim[1])
    if ylim is not None:
        plt.ylim(ylim[0],ylim[1])

    if savefig:
        plt.savefig('{}{}.png'.format(save_dir,save_name), dpi=200, facecolor='w',
                edgecolor='w',
                orientation='portrait', papertype=None, format=None,
                transparent=True, bbox_inches=None, pad_inches=0.1,
                frameon=None)
    plt.show()

def get_idx(array,value):
    return (np.abs(array-value)).argmin()
