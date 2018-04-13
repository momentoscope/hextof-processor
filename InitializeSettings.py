"@author: Steinn Ymir Agustsson"

import os
import configparser
import psutil

"""Create a SETTINGS.ini file

This script creates or overwrites a preexisting SETTINGS.ini file.
Such file contains local user information such as absolute paths for raw data, processed parquet dataframes and local 
machine settings, such as number of cores and conversion quantities.

This script is to be launched in each machine once for initialization. Further changes to the settings file can be done
directly on the SETTINGS.ini file. 

This was created to allow this code to be machine and OS agnostic.
"""


def make_new_settings():
    config = configparser.ConfigParser()

    settings_dict = {
        'paths': {
            'DATA_RAW_DIR': 'D:/data/FLASH/_RAW/online-3/',
            'DATA_H5_DIR': 'D:/data/FLASH/_processed/h5/',
            'DATA_PARQUET_DIR': 'D:/data/FLASH/_processed/parquet/',
            'DATA_RESULTS_DIR': 'D:/data/FLASH/Results/',
            'PAH_MODULE_DIR': 'D:/py_code/FLASH/PAH/',
        },
        'processor': {
            'N_CORES': psutil.cpu_count(),
            'CHUNK_SIZE': 1000000,
            'TOF_STEP_TO_NS': 0.0205761316872428,
            'TOF_STEP_TO_EV': 0.0205761316872428 * 0.22,
            'TOF_NS_TO_EV': 0.22,
        },
        'DAQ address - used': {
            'dld_pos_x': "/uncategorised/FLASH1_USER2/FLASH.FEL/HEXTOF.DAQ/DLD1:0/dset",
            'dld_pos_y': "/uncategorised/FLASH1_USER2/FLASH.FEL/HEXTOF.DAQ/DLD1:1/dset",
            'dld_time': "/uncategorised/FLASH1_USER2/FLASH.FEL/HEXTOF.DAQ/DLD1:3/dset",
            'dld_microbunch_id': "/uncategorised/FLASH1_USER2/FLASH.FEL/HEXTOF.DAQ/DLD1:2/dset",
            'dld_aux': "/uncategorised/FLASH1_USER2/FLASH.FEL/HEXTOF.DAQ/DLD1:4/dset",
            'delay_stage': "/uncategorised/FLASH1_USER2/FLASH.FEL/HEXTOF.DAQ/DLD1:4/dset",
            'bam': '/Electron Diagnostic/BAM/4DBC3/electron bunch arrival time (low charge)',
            'bunch_charge': '/Electron Diagnostic/Bunch charge/after undulator',
            'macro_bunch_pulse_id': '/Timing/Bunch train info/index 1.sts',
            'optical_diode': '/Experiment/PG/SIS8300 100MHz ADC/CH9/pulse energy/TD',
            'gmd_tunnel': '/Photon Diagnostic/GMD/Pulse resolved energy/energy tunnel',
            'gmd_bda': '/Photon Diagnostic/GMD/Pulse resolved energy/energy BDA',

        },
        'DAQ address - not used': {}
    }

    # write dictionary to .ini structure
    for section_name, section in settings_dict.items():
        config.add_section(section_name)
        for key, val in section.items():
            config.set(section_name, key, str(val))

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


if os.path.isfile('SETTINGS.ini'):
    answer = input('Overwriting existing settings.\nAre you sure? [y/n]')
    if answer.lower() in ['y', 'yes', 'si', 'ja']:
        print(' -> Overwriting previous settings.')
        make_new_settings()
    else:
        print('Settings file generation aborted by user.')
else:
    print(' -> No Settings found. Initializing new Settings file.')
    make_new_settings()
