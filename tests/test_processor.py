import sys, os
sys.path.append(os.path.dirname(os.getcwd()) ) # add hextof-processor to path
import processor
from processor.DldFlashDataframeCreator import DldFlashProcessor
    
import pytest

@pytest.fixture
def processor_undefined_settings():
    # Create Class instance without defining settings file
    return DldFlashProcessor()

@pytest.fixture
def processor_valid_settings():
    # Create Class instance with tutorial.ini settings file
    return DldFlashProcessor(settings='tutorial.ini')

def test_undefined_settings(processor_undefined_settings):
    root_folder = os.path.dirname(os.path.dirname(processor.__file__))
    # Expect that SETTINGS.ini in root folder is chosen
    assert processor_undefined_settings._settings_file == os.path.join(root_folder,'SETTINGS.ini')

def test_valid_settings(processor_valid_settings):
    root_folder = os.path.dirname(os.path.dirname(processor.__file__))
    # Expect that tutorial.ini in settings folder under root is chosen
    assert processor_valid_settings._settings_file == os.path.join(root_folder,'settings/tutorial.ini')

def test_invalid_settings():
    # Expect that an exception is raised when invalid file is input
    with pytest.raises(FileNotFoundError):
        # Create Class instance with NONE.ini settings file
        DldFlashProcessor(settings='NONE.ini')