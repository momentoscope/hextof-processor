# -*- coding: utf-8 -*-
"""The utilities module"""
from . import calibration, dfops, io, misc

try:
    from . import diagnostics
except:
    pass

# Can create problems due to ipywidgets import
try:
    from . import vis
except:
    pass