# -*- coding: utf-8 -*-
"""

@author: Steinn Ymir Agustsson
"""

from .misc import repr_byte_size, ravelledGaussian2D, gaussian2D, fit_2d_gaussian,\
    effective_gaussian_area, pulse_energy, fluence, absorbed_energy_density, fwhm_to_sigma, sigma_to_fwhm

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import dask
from dask.diagnostics import ProgressBar



def channel_report(dd):
    """ Generates a table containing relevant statistical quantities on all available channels [EXPENSIVE!!]

    Args:
        dd (dask.DataFrame): Table to analyse

    Returns:
        df (pandas.DataFrame): table with computed values
    Notes:
        Author: Steinn Ymir Agustsson <sagustss@uni-mainz.de>

    """
    print('creating channel report...')
    with ProgressBar():
        chan_dict = {}
        for chan in dd.columns:
            vals = dd[chan].compute()
            clean = vals[np.isfinite(vals)]
            chan_dict[chan] = {}
            chan_dict[chan]['min'] = min(clean)
            chan_dict[chan]['max'] = max(clean)
            chan_dict[chan]['amp'] = chan_dict[chan]['max'] - chan_dict[chan]['min']
            chan_dict[chan]['mean'] = np.mean(clean)
            chan_dict[chan]['std'] = np.std(clean)
            chan_dict[chan]['len'] = len(vals)
            chan_dict[chan]['len_nan'] = len(vals) - len(clean)
            chan_dict[chan]['max_loc'] = vals.idxmax()
            chan_dict[chan]['min_loc'] = vals.idxmin()
            


    df = pd.DataFrame.from_dict(chan_dict).T
    return df

def channel_statistics(dd,columns=None):
    """ Statistical overiview of the dataset.

    The report contains minimum, maximum, amplitude(max-min), mean and standard
    deviation of each column.

    Args:
        dd (dask.DataFrame): Table to analyse
        columns (list,None): list of columns to analyse, if None it checks all
            columns in the dataframe.
    Returns:
        df (pandas.DataFrame): table with computed values
    Notes:
        Author: Steinn Ymir Agustsson <sagustss@uni-mainz.de>

    """
    print('creating channel report...')
    chan_dict = {}
    if columns is None:
        columns = dd.columns
    for chan in columns:
        try:
            vals = dd[chan]
            chan_dict[chan] = {}
            chan_dict[chan]['min'] = vals.min()
            chan_dict[chan]['max'] = vals.max()
            chan_dict[chan]['amp'] = chan_dict[chan]['max'] - chan_dict[chan]['min']
            chan_dict[chan]['mean'] = vals.mean()
            chan_dict[chan]['std'] = vals.std()
            # chan_dict[chan]['len'] = vals.size
            # chan_dict[chan]['len_nan'] = vals.size - vals.isna().size

        except KeyError:
            print(f'No column {chan} in dataframe')

    with ProgressBar():
        d, = dask.compute(chan_dict)
    return pd.DataFrame.from_dict(d)

def binned_array_size(processor):
    """ Prints the expected size in memory of the binned array, computed with
    the current binning parameters"""

    voxels = np.prod([len(x) for x in processor.binAxesList])
    print(repr_byte_size(voxels.astype(np.float64) * 64.))


def plot_channels(processor):
    """ Generates a plot of each available channel.

    Useful for diagnostics on data conditions

    Args:
        processor (DldProcessor): processor instance

    """
    cols = processor.dd.columns
    f, ax = plt.subplots(len(cols) // 2, 2, figsize=(15, 20))
    for i, chan in enumerate(processor.dd.columns):
        vals = processor.dd[chan].compute()
        clean = vals[np.isfinite(vals)]
        start, stop, mean = clean.min(), clean.max(), clean.mean()

        if np.abs((start - mean) / (stop - mean)) > 5:
            start = stop - 2 * mean
        elif np.abs((stop - mean) / (start - mean)) > 5:
            stop = start + 2 * mean

        step = max((stop - start) / 1000, 1)
        x = processor.addBinning(chan, start, stop, step)
        res = processor.computeBinnedData()
        ax[i // 2, i % 2].set_title(chan, fontsize='x-large')
        if len(res) > 1:
            try:
                ax[i // 2, i % 2].plot(x, res)
            except ValueError:
                ax[i // 2, i % 2].plot(x, res[:-1])
        processor.resetBins()


def plot_GMD_vs_bunches(self):
    """ not sure what this was done for...
    """

    f, ax = plt.subplots(1, 2)
    self.resetBins()
    ubId = self.addBinning('dldMicrobunchId', 1, 500, 1)
    result_ubId = self.computeBinnedData()
    ax[0].plot(ubId, result_ubId / max(result_ubId), label='Photoelectron count')
    ax[0].set_title('Microbunch')

    self.resetBins()

    MbId_values = self.dd['macroBunchPulseId'].compute()
    clean = MbId_values[np.isfinite(MbId_values)]
    start, stop, mean = clean.min(), clean.max(), clean.mean()
    if np.abs((start - mean) / (stop - mean)) > 5:
        start = stop - 2 * mean
    elif np.abs((stop - mean) / (start - mean)) > 5:
        stop = start + 2 * mean
    step = max((stop - start) / 1000, 1)

    MbId = self.addBinning('macroBunchPulseId', start, stop, step)
    result_MbId = self.computeBinnedData()
    ax[1].plot(MbId, result_MbId / max(result_MbId), label='Photoelectron count')
    ax[1].set_title('Macrobunch')

    gmd_values = np.nan_to_num(self.dd['gmdBda'].compute())
    ubId_values = self.dd['dldMicrobunchId'].compute()

    gmd_ubId = np.zeros_like(ubId)
    for g, ub in zip(gmd_values, ubId_values):
        ub_idx = int(ub)
        if 0 < ub_idx < len(gmd_ubId):
            gmd_ubId[ub_idx] += g

    gmd_MbId = np.zeros_like(MbId)
    for g, Mb in zip(gmd_values, MbId_values):
        Mb_idx = int(Mb)
        if 0 < Mb_idx < len(gmd_MbId):
            gmd_MbId[Mb_idx] += g

    ax[0].plot(ubId, gmd_ubId / max(gmd_ubId), label='GMD')
    ax[1].plot(MbId, gmd_MbId / max(gmd_MbId) + 1, label='GMD')
    for a in ax:
        a.legend()
        a.grid()

def fit_spot_size(data,guess=None,l_bound=None,u_bound=None,
                  px_to_um=None,optical_diode_mean=None,
                  photoemission_order=None,optical_transmission=1,od_2_uj=1,
                  reflectivity=None,penetration_depth=None,
                  figsize=(8,8),
                 sigma_is_fwhm=False):
    """ Fit a 2D gaussian to the spatial view of the pump laser
    
    params:
        guess: guess parameters for the fit.
            the order of the parameters is: 
            ['amplitude',    'xo',    'yo',  'sigma_x',  'sigma_y', 'theta', 'offset']
            where:
            - amplitude: amplitude of the 2D gaussian
            - x0,y0 coordinates (in pixel units) of the center of the gaussian
            - simga_x,sigma_y sigma of the two perpendicular gaussians along the major and minor axis
            - theta: angle between the x axis and the major axis of the 2D gaussian
            - offset: constant offset
            the default values are [30., 275., 215., 30., 70., 3., 0]
        l_bound: lower bounds for the fit, same order as guess
            default values: [0., 170., 150., 5., 5., 0., -np.inf]
        u_bound: upper bounds for the fit, same order as guess
            default values: [np.inf, 330., 250., 170., 200., 5., np.inf]

        optical_diode_mean: mean value of the optical diode, used for fluence evaluation.
            any value can be passed, and the fluence evaluation will use that.
            if None, it tries to evaluate the mean optical diode value from data, if 
            data was binned along optical diode also.
        photoemission_order: the order of the photoemission process: see Dendzik et al supplementary
        optical_transmission:transmission factor of the microscope
            to account for losses from the laser power measurement 
            point to the sample position, typically 0.7
        od_2_uj: conversion from optical diode values to microjoule, obtained with calibration tables.
            The old laser system had 4.0926e-06, currently the values are already reported in uJ.
            Therefore the conversion factor 1 as defauly.
        figsize: size of the output figure
        sigma_is_fwhm: if true, it interpretates the parameter sigma of the gaussian as FWHM
    returns:
        popt: fit parameters of the 2D gaussian    
    """
    try:
        res = data.sum('opticalDiode')
    except:
        res = data
    #calibration:

    #px_to_um = 0.6 # pixel size in micrometers. if =1 will report in pixels.
    # px_to_um = 1.0673331251301068#450/len(res.dldPosX) # FoV in micrometers over number of pixels in X or Y direction. if =1 will report in pixels.
    if px_to_um is None:
        px_to_um = 1
        unit = 'px'
    else:
        unit= 'μm'
    # fit parameters
    labels =  ['amplitude',    'xo',    'yo',  'sigma_x',  'sigma_y', 'theta', 'offset'] # name of parameter
    if guess is None:
        guess =   [        30.,    275.,    215.,        30.,        70.,     3.,        0] # starting guess
    if l_bound is None:
        l_bound = [         0.,    170.,    150.,        5.,         5.,      0.,  -np.inf] # lower bounds (can use np.inf)
    if u_bound is None:
        u_bound = [     np.inf,    330.,    250.,        170.,       200.,     5.,   np.inf] # upper bounds
    if sigma_is_fwhm:
        guess[3] = fwhm_to_sigma(guess[3])
        guess[4] = fwhm_to_sigma(guess[4])
        l_bound[3] = fwhm_to_sigma(l_bound[3])
        l_bound[4] = fwhm_to_sigma(l_bound[4])        
        u_bound[3] = fwhm_to_sigma(u_bound[3])
        u_bound[4] = fwhm_to_sigma(u_bound[4])
    # ---- nothing to change below ----
    x = np.linspace(0, res.shape[0] - 1, res.shape[0])
    y = np.linspace(0, res.shape[1] - 1, res.shape[1])
    meshgrid = np.meshgrid(x, y)
    bounds = [l_bound,u_bound]
    popt,perr  = fit_2d_gaussian(res,guess=guess,bounds=bounds)
    data_fitted = gaussian2D(meshgrid, *popt).reshape(res.shape)
    print(*popt)
    # -- nothing to change below --
    fig = plt.figure(figsize=figsize)
    #[left, bottom, width, height]
    img_ax = fig.add_axes([.1,.3,.5,.5],xticklabels=[], yticklabels=[])
    xproj_ax = fig.add_axes([.1,.1,.5,.2], yticklabels=[])
    yproj_ax = fig.add_axes([.6,.3,.2,.5], xticklabels=[])
    img_ax.set_title('Spot size evaluation on run {}'.format(runNumber))
    yproj_ax.yaxis.set_label_position("right")
    yproj_ax.yaxis.set_ticks_position("right")
    xproj_ax.set_xticklabels(np.arange(0,max(x)*px_to_um,5))
    yproj_ax.set_yticklabels(np.arange(0,max(y)*px_to_um,5))

    xproj_ax.set_xlabel('X')
    yproj_ax.set_ylabel('Y')
    for ax in [img_ax, yproj_ax, xproj_ax]:
        ax.tick_params(axis="both",direction="in",bottom=True, top=True, left=True, right=True,which='both')

    img_ax.imshow(res,cmap='terrain')#gray_r
    img_ax.contour(data_fitted,cmap='inferno')#,colors='nipy_spectral')
    xproj_ax.plot(x,res.sum(axis=0))
    xproj_ax.plot(x,data_fitted.sum(0))
    xproj_ax.set_xlim(min(x),max(x))
    yproj_ax.plot(-res.sum(axis=1),y)
    yproj_ax.plot(-data_fitted.sum(1),y)
    yproj_ax.set_ylim(min(y),max(y))

    FWHM_x = sigma_to_fwhm(px_to_um * popt[3])
    FWHM_y = sigma_to_fwhm(px_to_um * popt[4])
    eff_area = effective_gaussian_area(popt[3],popt[4],photoemission_order=photoemission_order,sigma_is_fwhm=False)
    
    report_label = "Parameters:\n"
    report_label += f'Gaussian FWHM\nx={FWHM_x:.2f} {unit} | y={FWHM_y:.2f} {unit}\n'
    report_label += f'Area: {eff_area:.2f} {unit}$^2$\n'

    if optical_diode_mean is not None:
        optical_diode_value = optical_diode_mean
    else:
        try:
            optical_diode_mean = res.opticalDiode.mean().value
        except:
            optical_diode_value = None
            
    if optical_diode_value is not None:

        report_label += f'OD mean: {optical_diode_value:.2f}\n'

        pe  = pulse_energy(optical_diode_value,od_2_uj=od_2_uj,T=optical_transmission)
        report_label += f'Pulse energy: {1000*pe:.3f} nJ\n'
        fl  = fluence(pe,eff_area)
        report_label += f'Fluence: {fl:.3f} mJ/cm²\n'

    t = img_ax.text(res.shape[0]*1.02,res.shape[1]*1.02,report_label,color='Black',va='top',)#fontsize='small',)

    if False: # set True to save figure
        fig.savefig('spotsize evaluation run {}.pdf'.format(runNumber), dpi=None, facecolor='w', edgecolor='w',
            orientation='portrait', papertype=None, format=None,
            transparent=False, bbox_inches=None, pad_inches=0.1,
            frameon=None, metadata=None)
    return popt
