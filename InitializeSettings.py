"@author: Steinn Ymir Agustsson"

import os
import configparser
import psutil

"""Create a SETTINGS.ini file

WARNING:
    Running this script overwrites any previously existing Settings.

This script creates or overwrites a preexisting SETTINGS.ini file.
Such file contains local user information such as absolute paths for raw data, processed parquet dataframes and local 
machine settings, such as number of cores and conversion quantities.

This script is to be launched in each machine once for initialization. Further changes to the settings file can be done
directly on the SETTINGS.ini file. 

This was created to allow this code to be machine and OS agnostic.
"""

if os.path.isfile('SETTINGS.ini'):
    print(' -> Overwriting previous settings.')
else:
    print(' -> No Settings found. Initializing new Settings file.')

config = configparser.ConfigParser()

entries = {
    'paths': {
        'FLASH_RAW_DATA_PATH': 'D:/data/FLASH/_RAW/online-3/',
        'PAH_MODULE_PATH': 'D:/py_code/FLASH/PAH/',
        'DATA_H5_PATH': 'D:/data/FLASH/_processed/h5',
        'DATA_PARQUET_PATH': 'D:/data/FLASH/_processed/parquet',
    },
    'processor': {
        'N_CORES': psutil.cpu_count(),
        'CHUNK_SIZE': 1000000,
        'MAX_INTERVAL_SIZE': 30000,
    },
    'parameters': {
        'ToF_TIME_STEP': 0.0205761316872428,
        'ToF_energy_step': 1,

    }
}
# write dictionary to .ini structure
for section_name, section in entries.items():
    config.add_section(section_name)
    for key, val in section.items():
        config.set(section_name, key, str(val))

# write .ini structure to file.
with open('SETTINGS.ini', 'w') as configfile:  # save
    config.write(configfile)

print(' -> Setting file generated.')