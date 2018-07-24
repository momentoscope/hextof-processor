"@author: Steinn Ymir Agustsson"

import os
from configparser import ConfigParser
import psutil
import argparse

"""Create a SETTINGS.ini file

This script creates or overwrites a preexisting SETTINGS.ini file.
Such file contains local user information such as absolute paths for raw data, processed parquet dataframes and local 
machine settings, such as number of cores and conversion quantities.

This script is to be launched in each machine once for initialization. Further changes to the settings file can be done
directly on the SETTINGS.ini file. 

This was created to allow this code to be machine and OS agnostic.
"""


def make_new_settings(rebuilding=False, clean=False):
    config = ConfigParser()

    settings_dict = {
        'paths': {
            'DATA_RAW_DIR': os.getcwd()+'/Tutorial/raw/',
            'DATA_H5_DIR': os.getcwd()+'/Tutorial/h5/',
            'DATA_PARQUET_DIR': os.getcwd()+'/Tutorial/parquet/',
            'DATA_RESULTS_DIR': os.getcwd()+'/Tutorial/results/',
            'PAH_MODULE_DIR': os.path.dirname(os.getcwd())+'/PAH/',
        },
        'processor': {
            'N_CORES': psutil.cpu_count(),
            'UBID_OFFSET': 5,
            'CHUNK_SIZE': 1000000,
            # new detector uses 0.006858710665255785
            # old detector used 0.0205761316872428
            'TOF_STEP_TO_NS': 0.006858710665255785,
            'TOF_STEP_TO_EV': 0.006858710665255785 * 0.22,
            'TOF_NS_TO_EV': 0.22,
            'ET_CONV_E_OFFSET': 323.98,
            'ET_CONV_T_OFFSET': 371.258,

        },
        'DAQ address - used': {
            'dld_pos_x': "/uncategorised/FLASH1_USER2/FLASH.FEL/HEXTOF.DAQ/DLD1:0/dset",
            'dld_pos_y': "/uncategorised/FLASH1_USER2/FLASH.FEL/HEXTOF.DAQ/DLD1:1/dset",
            'dld_time': "/uncategorised/FLASH1_USER2/FLASH.FEL/HEXTOF.DAQ/DLD1:3/dset",
            'dld_detector_id': "/uncategorised/FLASH1_USER2/FLASH.FEL/HEXTOF.DAQ/DLD1:3/dset",
            'dld_microbunch_id': "/uncategorised/FLASH1_USER2/FLASH.FEL/HEXTOF.DAQ/DLD1:2/dset",
            'dld_aux_0': "/uncategorised/FLASH1_USER2/FLASH.FEL/HEXTOF.DAQ/DLD1:4/dset",
            'dld_aux_1': "/uncategorised/FLASH1_USER2/FLASH.FEL/HEXTOF.DAQ/DLD1:4/dset",
            'delay_stage': "/Experiment/Pump probe laser/delay line IK220.0/ENC",
            'bam': '/Electron Diagnostic/BAM/4DBC3/electron bunch arrival time (low charge)',
            'bunch_charge': '/Electron Diagnostic/Bunch charge/after undulator',
            'macro_bunch_pulse_id': '/Timing/Bunch train info/index 1.sts',
            'optical_diode': '/Experiment/PG/SIS8300 100MHz ADC/CH9/pulse energy/TD',
            'gmd_tunnel': '/Photon Diagnostic/GMD/Pulse resolved energy/energy tunnel',
            'gmd_bda': '/Photon Diagnostic/GMD/Pulse resolved energy/energy BDA',
            'pump_pol': '/uncategorised/FLASH1_USER2/FLASH.EXP/NF.ESP301/PG2/MOTOR3.POS/dset',
        },
        'DAQ address - not used': {}
    }

    # write dictionary to .ini structure
    for section_name, section in settings_dict.items():
        config.add_section(section_name)
        for key, val in section.items():
            config.set(section_name, key, str(val))

    # trying not to overwrite old settings every time
    if not rebuilding:
        current_settings = ConfigParser()
        if os.path.isfile(os.path.join(os.path.dirname(__file__), 'SETTINGS.ini')):
            current_settings.read(os.path.join(os.path.dirname(__file__), 'SETTINGS.ini'))
        else:
            current_settings.read(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'SETTINGS.ini'))

        for section in current_settings:
            for entry in current_settings[section]:
                try:
                    if config.has_option(section, entry):
                        config.set(section, entry, current_settings[section][entry])
                    else:
                        print('WARNING: option {} not a standard setting.'.format(entry))
                        if not clean:
                            config.set(section, entry, current_settings[section][entry])
                except Exception as e:
                    print('Invalid section in current config: {}'.format(e))

    missing_folders = []
    for dir_name in config['paths']:
        if not os.path.isdir(config['paths'][dir_name]):
            missing_folders.append((dir_name, config['paths'][dir_name]))
    if len(missing_folders) > 0:
        print('WARNING: the following folders do not exist:')
        for i in missing_folders:
            print('{0}: {1}'.format(i[0], i[1]))

    # write .ini structure to file.
    with open('SETTINGS.ini', 'w') as configfile:  # save
        config.write(configfile)
    print(' -> New setting file generated.')


# -------------------------------------------------------------------

parser = argparse.ArgumentParser(description='Generate, update, or overwrite SETTINGS.ini file.')
parser.add_argument('--overwrite', dest='overwrite', action='store_true',
                    help='forces the SETTINGS.ini file to be overwritten (default: update mode)')
parser.add_argument('--clean', dest='clean', action='store_true',
                    help='removes options from current SETTINGS.ini that are not standard (default: keeps everything)')
args = parser.parse_args()
overwrite = args.overwrite
clean = args.clean

if os.path.isfile('SETTINGS.ini'):
    promptMsg = ''
    if overwrite:
        promptMsg = 'Overwriting existing settings.\nAre you sure? [y/n]'
    else:
        promptMsg = 'Updating existing settings.\nAre you sure? [y/n]'
    answer = input(promptMsg)
    if answer.lower() in ['y', 'yes', 'si', 'ja']:
        print(' -> Updating previous settings.')
        make_new_settings(rebuilding=overwrite, clean=clean)
    else:
        print('Settings file generation aborted by user.')
else:
    print(' -> No Settings found. Initializing new Settings file.')
    make_new_settings(rebuilding=True, clean=True)
