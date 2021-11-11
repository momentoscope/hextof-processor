# -*- coding: utf-8 -*-

import configparser
import os
from datetime import datetime

import math
import h5py
import numpy as np
import psutil
import ast
import os
from configparser import ConfigParser
from collections import OrderedDict

# from processor import DldFlashDataframeCreator as DldFlashProcessor

# ================================================================================
"""Functions for calculation of pulse energy and pulse energy density of optical laser.
Calibration values taken from Pump beam energy converter 800 400.xls
Units are uJ for energy, um for beam diameter, uJ/cm^2 for energy density (and arb. for diode signal)
"""


def PulseEnergy400(Diode):
    """Calculate the pulse energy of 400nm laser in uJ. The unit is um for beam diameter.
    
    Parameter:
        Diode: numeric
            Measured value from photodiode (arb. units)
    """
    return 0.86 * (Diode * 0.0008010439 + 0.0352573)


def PulseEnergy800(Diode):
    """Calculate the pulse energy of 800nm laser in uJ. The unit is um for beam diameter.
    
    Parameter:
        Diode: numeric
            Meausred value from photodiode (arb. units)
    """

    return 0.86 * (Diode * 0.0009484577 + 0.1576)


def EnergyDensity400(Diode, Diameter=600):
    """Calculate the pulse energy density of 400nm laser in uJ/cm^2.
    The units are um for beam diameter, uJ/cm^2 for energy density.
    
    Parameters:
        Diode: numeric
            Measured value from photodiode (arb. units)
        Diameter: numeric | 600
            Beam diameter.
    """

    return PulseEnergy400(Diode) / (np.pi * np.square((Diameter * 0.0001) / 2))


def EnergyDensity800(Diode, Diameter=600):
    """Calculate the pulse energy density of 800nm laser in uJ/cm^2.
    The units are um for beam diameter, uJ/cm^2 for energy density.
    
    Parameters:
        Diode: numeric
            Measured value from photodiode (arb. units)
        Diameter: numeric | 600
            Beam diameter.
    """

    return PulseEnergy800(Diode) / (np.pi * np.square((Diameter * 0.0001) / 2))


# %% Settings
# ================================================================================


def parse_category(category, settings_file='default'):
    """ parse setting file and return desired value
    
    Args:
        category (str): title of the category
        setting_file (str): path to setting file. If set to 'default' it takes
            a file called SETTINGS.ini in the main folder of the repo.
    Returns:
        dictionary containing name and value of all entries present in this
        category.
    Notes:
        Author: Steinn Ymir Agustsson <sagustss@uni-mainz.de>
    """
    settings = ConfigParser()
    if settings_file == 'default':
        current_path = os.path.dirname(__file__)
        while not os.path.isfile(os.path.join(current_path, 'SETTINGS.ini')):
            current_path = os.path.split(current_path)[0]

        settings_file = os.path.join(current_path, 'SETTINGS.ini')
    settings.read(settings_file)
    try:
        cat_dict = {}
        for k, v in settings[category].items():
            try:
                if v[0] == "/":
                    cat_dict[k] = str(v)
                else:
                    cat_dict[k] = ast.literal_eval(v)
            except ValueError:
                cat_dict[k] = v
        return cat_dict
    except KeyError:
        print('No category {} found in SETTINGS.ini'.format(category))


def parse_setting(category, name, settings_file='default'):
    """ parse setting file and return desired value
    
    Args:
        category: str
            title of the category
        name: str
            name of the parameter
        setting_file: str | 'default'
            path to setting file. If set to 'default' it takes a file called SETTINGS.ini
            in the main folder of the repo.
    Returns:
        value of the parameter, None if parameter cannot be found.
    Notes:
        Author: Steinn Ymir Agustsson <sagustss@uni-mainz.de>
    """
    settings = ConfigParser()
    if settings_file == 'default':
        current_path = os.path.dirname(__file__)
        while not os.path.isfile(os.path.join(current_path, 'SETTINGS.ini')):
            current_path = os.path.split(current_path)[0]

        settings_file = os.path.join(current_path, 'SETTINGS.ini')
    settings.read(settings_file)

    try:
        value = settings[category][name]
        # if value[0] == "/":
        if os.path.isdir(value):
            return str(value)
        else:
            try:
                return ast.literal_eval(value)
            except SyntaxError:
                return str(value)
    except KeyError:
        print('No entry {} in category {} found in SETTINGS.ini'.format(name, category))
        return None
    except ValueError:
        return settings[category][name]


def write_setting(value, category, name, settings_file='default'):
    """ Write enrty in the settings file
    
    Args:
        category (str): title of the category
        name (str): name of the parameter
        setting_file (str): path to setting file. If set to 'default' it takes
            a file called SETTINGS.ini in the main folder of the repo.
    Returns:
        value of the parameter, None if parameter cannot be found.
    Notes:
        Author: Steinn Ymir Agustsson <sagustss@uni-mainz.de>
    """
    settings = ConfigParser()
    if settings_file == 'default':
        current_path = os.path.dirname(__file__)
        while not os.path.isfile(os.path.join(current_path, 'SETTINGS.ini')):
            current_path = os.path.split(current_path)[0]

        settings_file = os.path.join(current_path, 'SETTINGS.ini')
    settings.read(settings_file)

    settings[category][name] = str(value)

    with open(settings_file, 'w') as configfile:
        settings.write(configfile)


def parse_logbook(log_text):
    """ Parse a log book entry to read out metadata.

    Args:
        log_text (str or file): file or plain text of the log book, in the
        "correct" format TODO: add example of log entry
    Returns:
        logDict (dict): Dictionary with the relevant metadata
    Notes:
        Author: Steinn Ymir Agustsson <sagustss@uni-mainz.de>
    """
    assert isinstance(log_text, str) or os.path.isfile(log_text), 'Unrecognized format for logbook text'
    if os.path.isfile(log_text):
        with open(log_text, 'r') as f:
            text = f.read()
    else:
        text = log_text
    logDict = OrderedDict()

    t_split = text.split('\nFEL:')
    logDict['comments'] = t_split.pop(0)
    text = 'FEL:{}'.format(t_split[0])
    log_sections = []
    for line in text.split('\n'):
        log_sections.append(line.strip())
    log_sections = '|'.join([x.strip() for x in text.split('\n')]).split('||')

    for section in log_sections:
        while section[:1] == '|':
            section = section[1:]
        slist = section.split('|')
        title = slist[0].split(':')
        name = title.pop(0)
        logDict[name] = OrderedDict()
        try:
            status = title[0].strip()
            if status != '':
                logDict[name]['status'] = title[0].strip()
        except:
            pass
        for line in slist[1:]:
            linelist = line.replace(':', '=').split('=')
            try:
                logDict[name][linelist[0].strip()] = linelist[1].strip()
            except IndexError:
                logDict[name][linelist[0].strip()] = None
    return logDict


# %% Math
# ================================================================================


def radius(df, center=(0, 0)):
    """ Calculate the radius.
    """

    return np.sqrt(np.square(df.posX - center[0]) + np.square(df.posY - center[1]))


def argnearest(array, val, rettype='vectorized'):
    """Find the coordinates of the nD array element nearest to a specified value.

    Args:
        array (np.array): Numeric data array
        val (int or float) : Look-up value
        rettype (:obj:`str`,optional): return type specification
            'vectorized' (default) denotes vectorized coordinates (integer)
            'coordinates' denotes multidimensional coordinates (tuple)
    Returns:
        argval (int): coordinate position
    """

    vnz = np.abs(array - val)
    argval = np.argmin(vnz)

    if rettype == 'vectorized':
        return argval
    elif rettype == 'coordinates':
        return np.unravel_index(argval, array.shape)


# %% Data Input/Output
# ================================================================================

def save_H5_hyperstack(data_array, filename, path=None, overwrite=True):
    """ Saves an hdf5 file with 4D (Kx,Ky,E,Time) images for import in FIJI

    Parameters:
        data_array: numpy array
            4D data array, order must be Kx,Ky,Energy,Time.
        filename: str
            The name of the file to save
        path: str
            The path to where to save hdf5 file. If None, uses the "results" folder from SETTINGS.ini.
        overwrite: str
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


def load_binned_h5(file_name, mode='r', ret_type='list'):
    """ Load an HDF5 file saved with ``save_binned()`` method.

    Args:
        file_name (str): name of the file to load, including full path
        mode (:obj:`str`, optional): Read mode of h5 file ('r' = read).
        ret_type (:obj:`str`, optional): output format for axes and histograms:
            'list' generates a list of arrays, ordered as
            the corresponding dimensions in data. 'dict'
            generates a dictionary with the names of each axis.

    Returns:
        data np.array: Multidimensional data read from h5 file.
        axes np.array: The axes values associated with the read data.
        hist np.array: Histogram values associated with the read data.
    """
    if file_name[-3:] == '.h5':
        filename = file_name
    else:
        filename = '{}.h5'.format(file_name)

    with h5py.File(filename, mode) as h5File:

        # Retrieving binned data
        frames = h5File['frames']
        data = []
        if len(frames) == 1:
            data = np.array(frames['f0000'])

        else:
            for frame in frames:
                data.append(np.array(frames[frame]))
            data = np.array(data)

        # Retrieving axes
        axes = [0 for i in range(len(data.shape))]
        axes_d = {}
        for ax in h5File['axes/']:
            vals = h5File['axes/' + ax][()]
            #             axes_d[ax] = vals
            idx = int(ax.split(' - ')[0][2:])
            if len(frames) == 1:  # shift index to compensate missing time dimension
                idx -= 1
            axes[idx] = vals

            # Retrieving delay histograms
        hists = []
        hists_d = {}
        for hist in h5File['histograms/']:
            hists_d[hist] = h5File['histograms/' + hist][()]
            hists.append(h5File['histograms/' + hist][()])

    if ret_type == 'list':
        return data, axes, hists
    elif ret_type == 'dict':
        return data, axes_d, hists_d


def get_available_runs(rootpath):  # TODO: store the resulting dictionary to improve performance.
    """ Collects the filepaths to the available experimental run data.

    Parameters:
        rootpath: str
            path where to look for data (recursive in subdirectories)

    Return:
        available_runs: dict
            dict with run numbers as keys (e.g. 'run12345') and path where to load data from as str.
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
            except:  # TODO: use an assertion method for more solid error tracking.
                pass

    return available_runs


def get_path_to_run(runNumber, rootpath): # TODO: improve performance
    """ Returns the path to the data of a given run number

    Parameters:
        runNumber: str or int
            run number as integer or string.
        rootpath: str
            path where to look for data (recursive in subdirectories)


    Return:
        path: str
            path to where the raw data of the given run number is stored.
    """

    available_runs = get_available_runs(rootpath)

    try:
        return (available_runs['run{}'.format(runNumber)])
    except KeyError:
        raise FileNotFoundError('No run number {} under path {}'.format(runNumber, rootpath))


def availableParquet(parquet_dir=None):
    if parquet_dir is None:
        import configparser

        settings = configparser.ConfigParser()  # TODO: find a smarter way
        if os.path.isfile(os.path.join(os.path.dirname(__file__), 'SETTINGS.ini')):
            settings.read(os.path.join(os.path.dirname(__file__), 'SETTINGS.ini'))
        else:
            settings.read(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'SETTINGS.ini'))
        parquet_dir = settings['paths']['DATA_PARQUET_DIR']

    return [x[:-3] for x in os.listdir(parquet_dir) if '_el' in x]


# %% mathematical functions
# ================================================================================
def gaussian2D(x,y, amplitude, xo, yo, sigma_x, sigma_y, theta, offset):
#     x, y = M
    xo = float(xo)
    yo = float(yo)
    a = (np.cos(theta)**2)/(2*sigma_x**2) + (np.sin(theta)**2)/(2*sigma_y**2)
    b = -(np.sin(2*theta))/(4*sigma_x**2) + (np.sin(2*theta))/(4*sigma_y**2)
    c = (np.sin(theta)**2)/(2*sigma_x**2) + (np.cos(theta)**2)/(2*sigma_y**2)
    return offset + amplitude*np.exp( - (a*((x-xo)**2) + 2*b*(x-xo)*(y-yo)
                        + c*((y-yo)**2)))

def lorentzian2D(x,y, amp, mux, muy, g, c):
    numerator = np.abs(amp * g)
    denominator = ((x - mux) ** 2 + (y - muy) ** 2 + g ** 2) ** 1.5
    return numerator / denominator + c

def multi_lorentzian2D(M,*args):
    x,y = M
    arr = np.zeros(x.shape)
    n=7
    for i in range(len(args)//n):
        arr += lorentzian2D(M, *args[i*n:i*n+n])
    return arr

def multi_gaussian2D(M, *args):
    x,y = M
    arr = None
    n=7
    for i in range(len(args)//n):
        if arr is None:
            arr = gaussian2D(x,y, *args[i*n:i*n+n])
        else:
            arr += gaussian2D(x,y, *args[i*n:i*n+n])
    return arr




# %% String operations
# ================================================================================

def camelCaseIt(snake_case_string):
    """ Format a string in camel case
    """

    titleCaseVersion = snake_case_string.title().replace("_", "")
    camelCaseVersion = titleCaseVersion[0].lower() + titleCaseVersion[1:]

    return camelCaseVersion

def repr_byte_size(size_bytes):
    """ Represent in a string the size in Bytes in a compact format.

    Adapted from https://stackoverflow.com/questions/5194057/better-way-to-convert-file-sizes-in-python
    Follows same notation as Windows does for files. See: https://en.wikipedia.org/wiki/Mebibyte
    """

    if size_bytes == 0:
        return "0B"
    size_name = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)
    return "%s %s" % (s, size_name[i])
# %% plotting
# # ================================================================================

def plot_lines(data, normalization='None', range=None, color_range=(0, 1),
               x_label='', y_label='', xlim=None, ylim=None, savefig=False,
               save_dir='E:/data/FLASH/', save_name='fig', static_curve=None):
    """ function to fit a series of curves with nice colorplot. """

    from matplotlib import pyplot as plt, cm

    f, axis = plt.subplots(1, 1, figsize=(8, 6), sharex=True)

    if range is None:
        from_ = 0
        to_ = len(data[:, ...])
    else:
        from_ = range[0]
        to_ = range[1]

    n_curves = len(data[from_:to_, 0])
    print('Number of curves: {}'.format(n_curves))
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
        plt.savefig('{}{}.png'.format(save_dir, save_name),
                    dpi=200, facecolor='w', edgecolor='w', orientation='portrait',
                    papertype=None, format=None, transparent=True, bbox_inches=None,
                    pad_inches=0.1, frameon=None)
    plt.show()


# ==================
# Methods by Steinn!
# ==================


def get_system_memory_status(print_=False):
    mem_labels = ('total', 'available', 'percent', 'used', 'free')
    mem = psutil.virtual_memory()
    memstatus = {}
    for i, val in enumerate(mem):
        memstatus[mem_labels[i]] = val
    if print_:
        for key, value in memstatus.items():
            if key == 'percent':
                print('{}: {:0.3}%'.format(key, value))
            else:
                print('{}: {:0,.4} GB'.format(key, value / 2 ** 30))
    return memstatus


def read_and_binn(runNumber, *args, static_bunches=False, source='raw', save=True):
    print(datetime.now())

    from processor import DldFlashDataframeCreator as DldFlashProcessor

    processor = DldFlashProcessor.DldFlashProcessor()
    processor.runNumber = runNumber
    if source == 'raw':
        processor.readData()
    elif source == 'parquet':
        try:
            processor.readDataframes()
        except:
            print('No Parquet data found, loading raw data.')
            processor.readData()
            processor.storeDataframes()
    processor.postProcess()
    if static_bunches is True:
        processor.dd = processor.dd[processor.dd['dldMicrobunchId'] > 400]
    else:
        processor.dd = processor.dd[processor.dd['dldMicrobunchId'] > 100]
        processor.dd = processor.dd[processor.dd['dldMicrobunchId'] < 400]
    shortname = ''
    processor.resetBins()
    dldTime = delayStage = dldPos = None
    for arg in args:
        if arg[0] == 'dldTime':
            dldTime = arg[1:]
        elif arg[0] == 'delayStage':
            delayStage = arg[1:]
        elif arg[0] == 'dldPos':
            dldPos = arg[1:]

    if dldTime:
        processor.addBinning('dldTime', *dldTime)
        shortname += 'E'
    if delayStage:
        processor.addBinning('delayStage', *delayStage)
        shortname += 'T'
    if dldPos:
        processor.addBinning('dldPosX', *dldPos)
        processor.addBinning('dldPosY', *dldPos)
        shortname += 'KxKy'

    if save:
        saveName = 'run{} - {}'.format(runNumber, shortname)
        result = processor.computeBinnedData(saveName=saveName)
    else:
        result = processor.computeBinnedData()
    axes = processor.binRangeList
    return result, axes, processor


def create_dataframes(runNumbers, *args):
    """ Creates a parquet dataframe for each run passed.
    Returns:
        fails: dictionary of runs and error which broke the dataframe generation
    """
    if isinstance(runNumbers, int):
        runNumbers = [runNumbers, ]
    for run in args:
        if isinstance(run, list) or isinstance(run, tuple):
            runNumbers.extend(run)
        else:
            runNumbers.append(run)
    fails = {}
    for run in runNumbers:
        try:
            from processor import DldFlashDataframeCreator as DldFlashProcessor
            prc = DldFlashProcessor.DldFlashProcessor()
            prc.runNumber = run
            prc.readData()
            prc.storeDataframes()
            print('Stored dataframe for run {} in {}'.format(run, prc.DATA_PARQUET_DIR))
        except Exception as E:
            fails[run] = E
    for key, val in fails.items():
        print('{} failed with error {}'.format(key, val))

    return fails
