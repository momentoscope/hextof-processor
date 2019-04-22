# -*- coding: utf-8 -*-
"""

@author: Steinn Ymir Agustsson
"""
import sys, os
import numpy as np

def main():
    pass


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


def tof2energy(t, toffset=None, eoffset=None, l=None):
    """ Transform ToF to eV.

    The functions (tof2energy and energy2tof) convert between binding energy (:math:`E_b`) in eV (negative convention)
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
        l : float
            the effective length of the drift section

    :Return:
        e : float
            The binding energy

    :Authors:
        Davide Curcio <davide.curcio@phys.au.dk>
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
    if l is None:
        l = float(settings['processor']['ET_CONV_L'])
    e = 0.5 * 1e18 * 9.10938e-31 * l * l / (((t) - toffset) * ((t) - toffset)) / 1.602177e-19 - eoffset
    return e


def energy2tof(e, toffset=None, eoffset=None, l=None):
    """ Transform eV to time of flight (ToF).

    The functions (tof2energy and energy2tof) convert between binding energy (:math:`E_b`) in eV (negative convention)
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
        l : float
            the effective length of the drift section

    :Return:
        t : float
            The time of flight

    :Authors:
        Davide Curcio <davide.curcio@phys.au.dk>
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
    if l is None:
        l = float(settings['processor']['ET_CONV_L'])
    t = l * np.sqrt(0.5 * 1e18 * 9.10938e-31 / 1.602177e-19 / (e + eoffset)) + toffset
    return t


if __name__ == '__main__':
    main()