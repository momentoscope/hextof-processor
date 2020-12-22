# -*- coding: utf-8 -*-
"""

@author: Steinn Ymir Agustsson, Davide Curcio, Maciej Dendzik
"""
import sys, os
import numpy as np


def gen_sector_correction(prc, energies, eref, tofVoltage=None, sampleBias=None, monoEnergy=None):
    """
    This function is helpful in generating the sector_correction list.
    This takes into account the time shift caused by the bit stealing hack
    plus is keeps track of the time shift due to detector misalignment by making sure
    all values of energies are at eref.

    Usage: use the function to create the sector_correction list and assign it to prc.SECTOR_CORRECTION
    or paste it into the settings with no brackets

    :param prc:
    :param energies:
    :param eref:
    :return:
    """

    if sampleBias is None:
        sampleBias = np.nanmean(prc.dd['sampleBias'].values)
    if monoEnergy is None:
        monoEnergy = np.nanmean(prc.dd['monochromatorPhotonEnergy'].values)
    if tofVoltage is None:
        tofVoltage = np.nanmean(prc.dd['tofVoltage'].values)

    # Here, the most basic sector_correction list is generated, where the bit stealing hack gets corrected
    n_sectors=prc.dd['dldSectorId'].values.compute().max().astype(int)+1
    sector_correction = np.floor(np.array(range(n_sectors))*np.power(2,prc.DLD_ID_BITS)/n_sectors)
    # e.g. for 3 stolen bits, 8 detector ids (new s8 data), this will look like [0,1,2,3,4,5,6,7]
    # e.g. for 1 stolen bit, 8 detector ids (old modified s8 data), this will look like [0,0,0,0,1,1,1,1]
    # e.g. for 1 stolen bit, 2 detector ids (old s8 data), this will look like [0,1]


    t_ref = energy2tof(eref, l=0.965, eoffset=-2.64-sampleBias+tofVoltage+monoEnergy)

    times=[]
    for ee in energies:
        times.append((energy2tof(ee, l=0.965, eoffset=-2.64-47+30+monoEnergy)-t_ref)/prc.TOF_STEP_TO_NS)

    sector_correction=sector_correction+np.array(times)
    # here the sectors are shifter by the required time to align the energies

    return sector_correction



# %% Energy calibration

""" The following functions convert between binding energy (Eb) in eV (negative convention)
    and time of flight (ToF) in ns.

    The formula used is based on the ToF for an electron with a kinetic energy Ek. Then the
    binding energy Eb is given by
    
    .. math::

        -E_b = E_k + W - hv - V = \\frac{1}{2} mv^2 + W - hv - V

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

    .. math::

        -E_b = E_k + W - hv - V = \\frac{1}{2} mv^2 + W - hv - V


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

    Parameters:
        t: float
            The time of flight
        toffset: float
            The time offset from thedld clock start to when the fastest photoelectrons reach the detector
        eoffset: float
            The energy offset given by W-hv-V
        l: float
            the effective length of the drift section

    Return:
        e: float
            The binding energy

    Authors:
        Davide Curcio <davide.curcio@phys.au.dk>
    """

    from configparser import ConfigParser
    settings = ConfigParser()
    if os.path.isfile(os.path.join(os.path.dirname(__file__), 'SETTINGS.ini')):
        settings.read(os.path.join(os.path.dirname(__file__), 'SETTINGS.ini'))
    else:
        settings.read(
            os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'SETTINGS.ini'))

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

    .. math::

        -E_b = E_k + W - hv - V = \\frac{1}{2} mv^2 + W - hv - V


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

    Parameters:
        e: float
            The binding energy
        toffset: float
            The time offset from thedld clock start to when the fastest photoelectrons reach the detector
        eoffset: float
            The energy offset given by W-hv-V
        l: float
            the effective length of the drift section

    Return:
        t: float
            The time of flight

    Authors:
        Davide Curcio <davide.curcio@phys.au.dk>
    """

    from configparser import ConfigParser
    settings = ConfigParser()
    if os.path.isfile(os.path.join(os.path.dirname(__file__), 'SETTINGS.ini')):
        settings.read(os.path.join(os.path.dirname(__file__), 'SETTINGS.ini'))
    else:
        settings.read(
            os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'SETTINGS.ini'))

    if toffset is None:
        toffset = float(settings['processor']['ET_CONV_T_OFFSET'])
    if eoffset is None:
        eoffset = float(settings['processor']['ET_CONV_E_OFFSET'])
    if l is None:
        l = float(settings['processor']['ET_CONV_L'])
    t = l * np.sqrt(0.5 * 1e18 * 9.10938e-31 / 1.602177e-19 / (e + eoffset)) + toffset
    return t


def e2t(e, toffset=None, eoffset=None, l=0.77):
    """ Same as energy2tof, but different name for retrocompatibility

    Parameters:
        e: float
            The binding energy
        toffset: float
            The time offset from thedld clock start to when the fastest photoelectrons reach the detector
        eoffset: float
            The energy offset given by W-hv-V
        l: float
            the effective length of the drift section

    Return:
        t: float
            The time of flight

    Authors:
        Davide Curcio <davide.curcio@phys.au.dk>
    """

    return energy2tof(e, toffset, eoffset, l)


def t2e(t, toffset=None, eoffset=None, l=0.77):
    """ Same as tof2energy, but different name for retrocompatibility

    Parameters:
        t: float
            The time of flight
        toffset: float
            The time offset from thedld clock start to when the fastest photoelectrons reach the detector
        eoffset: float
            The energy offset given by W-hv-V
        l: float
            the effective length of the drift section

    Return:
        e: float
            The binding energy

    Authors:
        Davide Curcio <davide.curcio@phys.au.dk>
    """

    return tof2energy(t, toffset, eoffset, l)


# %% Detector calibration

# ==================
# Methods by Mac! Built for the April 2018 beamtime, where a four quadrant detector was used.
# ==================

def shiftQuadrants(self, shiftQ1=0.231725, shiftQ2=-0.221625, shiftQ3=0.096575, shiftQ4=-0.106675, xCenter=1350,
                   yCenter=1440):
    """ Apply corrections to the dataframe. (Maciej Dendzik)

    Each quadrant of DLD is shifted in DLD time by shiftQn.
    xCenter and yCenter are used to define the center of the division.
    
    +-----------+-----------+
    |    Q2     |     Q4    |
    +-----------+-----------+
    |    Q1     |     Q3    |
    +-----------+-----------+

    This picture is upside-down in ``plt.imshow`` because it starts from 0 in top right corner.
    """
    # Q1
    # daskdataframe.where(condition,value) keeps the data where condition is True
    # and changes them to value otherwise.
    cond = ((self.dd['dldPosX'] > xCenter) | (self.dd['dldPosY'] > yCenter))
    self.dd['dldTime'] = self.dd['dldTime'].where(cond, self.dd['dldTime'] + shiftQ1)
    cond = ((self.dd['dldPosX'] > xCenter) | (self.dd['dldPosY'] < yCenter))
    self.dd['dldTime'] = self.dd['dldTime'].where(cond, self.dd['dldTime'] + shiftQ2)
    cond = ((self.dd['dldPosX'] < xCenter) | (self.dd['dldPosY'] > yCenter))
    self.dd['dldTime'] = self.dd['dldTime'].where(cond, self.dd['dldTime'] + shiftQ3)
    cond = ((self.dd['dldPosX'] < xCenter) | (self.dd['dldPosY'] < yCenter))
    self.dd['dldTime'] = self.dd['dldTime'].where(cond, self.dd['dldTime'] + shiftQ4)


def filterCircleDLDPos(self, xCenter=1334, yCenter=1426, radius=1250):
    """ Apply corrections to the dataframe. (Maciej Dendzik)

    Filters events with dldPosX and dldPosY within the radius from (xCenter,yCenter).

    """

    self.dd = self.dd[
        (((self.dd['dldPosX'] - xCenter) ** 2 + (self.dd['dldPosY'] - yCenter) ** 2) ** 0.5 <= radius)]


def correctOpticalPath(self, poly1=-0.00020578, poly2=4.6813e-7, xCenter=1334, yCenter=1426):
    """ Apply corrections to the dataframe. (Maciej Dendzik)

    Each DLD time is subtracted with a polynomial poly1*r + poly2*r^2,
    where r=sqrt((posx-xCenter)^2+(posy-yCenter)^2)

    This function makes corrections to the time of flight which take into account
    the path difference between the center of the detector and the edges of the detector.

    """
    # Q1
    # daskdataframe.where(condition,value) keeps the data where condition is True
    # and changes them to value otherwise.

    self.dd['dldTime'] = self.dd['dldTime'] - \
                         (poly1 * ((self.dd['dldPosX'] - xCenter) ** 2 + (
                                 self.dd['dldPosY'] - yCenter) ** 2) ** 0.5 + \
                          poly2 * ((self.dd['dldPosX'] - xCenter) ** 2 + (self.dd['dldPosY'] - yCenter) ** 2))
    