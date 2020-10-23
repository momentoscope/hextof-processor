# -*- coding: utf-8 -*-

"""
@author: Steinn Ymir Agustsson
"""
import matplotlib.pyplot as plt
import numpy as np
from ipywidgets import widgets, interactive_output

cmaps = ['viridis', 'plasma', 'inferno', 'magma', 'Greys', 'Purples', 'Blues', 'Greens', 'Oranges', 'Reds',
         'YlOrBr', 'YlOrRd', 'OrRd', 'PuRd', 'RdPu', 'BuPu',
         'GnBu', 'PuBu', 'YlGnBu', 'PuBuGn', 'BuGn', 'YlGn', 'binary', 'gist_yarg', 'gist_gray', 'gray', 'bone', 'pink',
         'spring', 'summer', 'autumn', 'winter', 'cool', 'Wistia',
         'hot', 'afmhot', 'gist_heat', 'copper', 'PiYG', 'PRGn', 'BrBG', 'PuOr', 'RdGy', 'RdBu',
         'RdYlBu', 'RdYlGn', 'Spectral', 'coolwarm', 'bwr', 'seismic', 'Pastel1', 'Pastel2', 'Paired', 'Accent',
         'Dark2', 'Set1', 'Set2', 'Set3',
         'tab10', 'tab20', 'tab20b', 'tab20c', 'flag', 'prism', 'ocean', 'gist_earth', 'terrain', 'gist_stern',
         'gnuplot', 'gnuplot2', 'CMRmap', 'cubehelix', 'brg', 'hsv',
         'gist_rainbow', 'rainbow', 'jet', 'nipy_spectral', 'gist_ncar']
    
def isnotebook():
    try:
        shell = get_ipython().__class__.__name__
        if shell == 'ZMQInteractiveShell':
            return True  # Jupyter notebook or qtconsole
        elif shell == 'TerminalInteractiveShell':
            return False  # Terminal running IPython
        else:
            return False  # Other type (?)
    except NameError:
        return False  # Probably standard Python interpreter

def orthoslices_3D(data, normalize=True, continuous_update=False, **kwargs):
    if not isnotebook:
        print('Function not suited for working outside of Jupyter notebooks!')
    else:
        get_ipython().magic('matplotlib notebook')
        get_ipython().magic('matplotlib notebook')

    e_range, x_range, y_range = data.shape
    dmin = np.amin(data)
    dmax = np.amax(data)

    w_e = widgets.IntSlider(value=e_range // 2, min=0, max=e_range - 1, step=1, description='Energy:',
                            disabled=False, continuous_update=continuous_update, orientation='horizontal', readout=True,
                            readout_format='d')
    w_kx = widgets.IntSlider(value=x_range // 2, min=0, max=x_range - 1, step=1, description='kx:',
                             disabled=False, continuous_update=continuous_update, orientation='horizontal',
                             readout=True,
                             readout_format='d')
    w_ky = widgets.IntSlider(value=y_range // 2, min=0, max=y_range - 1, step=1, description='ky:', disabled=False,
                             continuous_update=continuous_update, orientation='horizontal', readout=True,
                             readout_format='d')
    w_clim = widgets.FloatRangeSlider(value=[.1, .9], min=0, max=1, step=0.001, description='Contrast:', disabled=False,
                                      continuous_update=continuous_update, orientation='horizontal', readout=True,
                                      readout_format='.1f')
    w_cmap = widgets.Dropdown(options=cmaps, value='terrain', description='colormap:', disabled=False)
    w_bin = widgets.BoundedIntText(value=1, min=1, max=min(data.shape), step=1, description='resample:', disabled=False)
    w_interpolate = widgets.Checkbox(value=True, description='Interpolate', disabled=False)
    w_grid = widgets.Checkbox(value=False, description='Grid', disabled=False)
    w_trackers = widgets.Checkbox(value=True, description='Trackers', disabled=False)
    w_trackercol = widgets.ColorPicker(concise=False, description='tracker line color', value='orange')

    ui_pos = widgets.HBox([w_e, w_kx, w_ky])
    ui_color = widgets.HBox([widgets.VBox([w_clim, w_cmap]),
                             widgets.VBox([w_bin, w_interpolate, w_grid]),
                             widgets.VBox([w_trackers, w_trackercol]),
                             ])

    children = [ui_pos, ui_color]
    tab = widgets.Tab(children=children, )
    tab.set_title(0, 'data select')
    tab.set_title(1, 'colormap')

    figsize = kwargs.pop('figsize', (5, 5))
    fig = plt.figure(figsize=figsize, **kwargs)
    plt.tight_layout()
    # [left, bottom, width, height]
    # fig.locator_params(nbins=4)

    # cbar_ax = fig.add_axes([.05,.4,.05,4], xticklabels=[], yticklabels=[])
    # cbar_ax.yaxis.set_major_locator(plt.LinearLocator(5))

    img_ax = fig.add_axes([.15, .4, .4, .4], xticklabels=[], yticklabels=[])
    img_ax.xaxis.set_major_locator(plt.LinearLocator(5))
    img_ax.yaxis.set_major_locator(plt.LinearLocator(5))

    xproj_ax = fig.add_axes([.15, .1, .4, .28], xticklabels=[], yticklabels=[])
    xproj_ax.set_xlabel('$k_x$')
    xproj_ax.xaxis.set_major_locator(plt.LinearLocator(5))

    yproj_ax = fig.add_axes([.57, .4, .28, .4], xticklabels=[], yticklabels=[])
    yproj_ax.yaxis.set_label_position("right")
    yproj_ax.set_ylabel('$k_y$')
    yproj_ax.yaxis.set_major_locator(plt.LinearLocator(5))

    for ax in [img_ax, yproj_ax, xproj_ax]:  # ,cbar_ax]:
        ax.tick_params(axis="both", direction="in", bottom=True, top=True, left=True, right=True, which='both')

    clim_ = 0.01, .99

    e_img = norm_img(data[data.shape[0] // 2, :, :])
    y_img = norm_img(data[:, data.shape[1] // 2, :])
    x_img = norm_img(data[:, :, data.shape[2] // 2].T)
    e_plot = img_ax.imshow(e_img, cmap='terrain', aspect='auto', interpolation='gaussian',
                           clim=clim_, )  # origin='lower')
    x_plot = yproj_ax.imshow(x_img, cmap='terrain', aspect='auto', interpolation='gaussian',
                             clim=clim_, )  # origin='lower')
    y_plot = xproj_ax.imshow(y_img, cmap='terrain', aspect='auto', interpolation='gaussian',
                             clim=clim_, )  # origin='lower')

    pe_x = img_ax.axvline(x_range / 2, c='orange')
    pe_y = img_ax.axhline(y_range / 2, c='orange')
    px_x = xproj_ax.axvline(x_range / 2, c='orange')
    px_e = xproj_ax.axhline(e_range / 2, c='orange')
    py_y = yproj_ax.axhline(y_range / 2, c='orange')
    py_e = yproj_ax.axvline(e_range / 2, c='orange')

    def update(e, kx, ky, clim, cmap, binning, interpolate, grid, trackers, trackerscol):
        if normalize:
            e_img = norm_img(data[e, :, :][::binning, ::binning])
            y_img = norm_img(data[:, ky, :][::binning, ::binning])
            x_img = norm_img(data[:, :, kx][::binning, ::binning])
        else:
            e_img = data[e, :, :][::binning, ::binning]
            y_img = data[:, ky, :][::binning, ::binning]
            x_img = data[:, :, kx][::binning, ::binning]
        for axis, plot, img in zip([img_ax, yproj_ax, xproj_ax], [e_plot, x_plot, y_plot], [e_img, x_img.T, y_img]):

            plot.set_data(img)
            plot.set_clim(clim)
            plot.set_cmap(cmap)
            axis.grid(grid)
            if interpolate:
                plot.set_interpolation('gaussian')
            else:
                plot.set_interpolation(None)
            if trackers:
                pe_x.set_xdata(kx)
                pe_x.set_color(trackerscol)
                pe_y.set_ydata(ky)
                pe_y.set_color(trackerscol)
                px_x.set_xdata(kx)
                px_x.set_color(trackerscol)
                px_e.set_ydata(e)
                px_e.set_color(trackerscol)
                py_y.set_ydata(ky)
                py_y.set_color(trackerscol)
                py_e.set_xdata(e)
                py_e.set_color(trackerscol)

    interactive_plot = interactive_output(update, {'e': w_e,
                                                   'kx': w_kx,
                                                   'ky': w_ky,
                                                   'clim': w_clim,
                                                   'cmap': w_cmap,
                                                   'binning': w_bin,
                                                   'interpolate': w_interpolate,
                                                   'grid': w_grid,
                                                   'trackers': w_trackers,
                                                   'trackerscol': w_trackercol, });
    display(interactive_plot, tab)
    # display(tab)

    # return fig


def orthoslices_4D(data, axis_order=['E', 'kx', 'ky', 'kz'], normalize=True, continuous_update=True, **kwargs):
    if not isnotebook:
        raise EnvironmentError('Function not suited for working outside of Jupyter notebooks!')
    else:
        get_ipython().magic('matplotlib notebook')
        get_ipython().magic('matplotlib notebook')

    assert len(data.shape) == 4, 'Data should be 4-dimensional, but data has {} dimensions'.format(data.shape)

    # make controls for data slicers
    # slicers = []
    # for shape, name in zip(data.shape, axis_order):
    #     slicers.append(widgets.IntSlider(value=shape // 2,
    #                                      min=0,
    #                                      max=shape - 1,
    #                                      step=1,
    #                                      description=name,
    #                                      disabled=False,
    #                                      continuous_update=False,
    #                                      orientation='horizontal',
    #                                      readout=True,
    #                                      readout_format='d'
    #                                      ))

    e_range, x_range, y_range, z_range = data.shape

    w_e = widgets.IntSlider(value=e_range // 2, min=0, max=e_range - 1, step=1, description='Energy:',
                            disabled=False, continuous_update=continuous_update, orientation='horizontal', readout=True,
                            readout_format='d')
    w_kx = widgets.IntSlider(value=x_range // 2, min=0, max=x_range - 1, step=1, description='kx:',
                             disabled=False, continuous_update=continuous_update, orientation='horizontal',
                             readout=True,
                             readout_format='d')
    w_ky = widgets.IntSlider(value=y_range // 2, min=0, max=y_range - 1, step=1, description='ky:', disabled=False,
                             continuous_update=continuous_update, orientation='horizontal', readout=True,
                             readout_format='d')
    w_kz = widgets.IntSlider(value=z_range // 2, min=0, max=z_range - 1, step=1, description='kz:', disabled=False,
                             continuous_update=continuous_update, orientation='horizontal', readout=True,
                             readout_format='d')

    slicers = [w_e, w_kx, w_ky, w_kz]
    ui_slicers = widgets.HBox(slicers)

    # make controls for graphics appearance
    w_clim = widgets.FloatRangeSlider(value=[.1, .9], min=0, max=1, step=0.001, description='Contrast:', disabled=False,
                                      continuous_update=True, orientation='horizontal', readout=True,
                                      readout_format='.1f')
    w_cmap = widgets.Dropdown(options=cmaps, value='terrain', description='colormap:', disabled=False)
    w_bin = widgets.BoundedIntText(value=1, min=1, max=min(data.shape), step=1, description='resample:', disabled=False)
    w_interpolate = widgets.Checkbox(value=True, description='Interpolate', disabled=False)
    w_grid = widgets.Checkbox(value=False, description='Grid', disabled=False)
    w_trackers = widgets.Checkbox(value=True, description='Trackers', disabled=False)
    w_trackercol = widgets.ColorPicker(concise=False, description='tracker line color', value='orange')
    ui_color = widgets.HBox([widgets.VBox([w_clim, w_cmap]),
                             widgets.VBox([w_bin, w_interpolate, w_grid]),
                             widgets.VBox([w_trackers, w_trackercol]),
                             ])

    tab = widgets.Tab(children=[ui_slicers, ui_color], )
    tab.set_title(0, 'Data slicing')
    tab.set_title(1, 'Graphics')

    figsize = kwargs.pop('figsize', (5, 5))
    fig = plt.figure(figsize=figsize, **kwargs)
    plt.tight_layout()

    img_ax = fig.add_axes([.15, .4, .4, .4], xticklabels=[], yticklabels=[])
    img_ax.xaxis.set_major_locator(plt.LinearLocator(5))
    img_ax.yaxis.set_major_locator(plt.LinearLocator(5))

    xproj_ax = fig.add_axes([.15, .1, .4, .28], xticklabels=[], yticklabels=[])
    xproj_ax.set_xlabel('$k_x$')
    xproj_ax.xaxis.set_major_locator(plt.LinearLocator(5))

    yproj_ax = fig.add_axes([.57, .4, .28, .4], xticklabels=[], yticklabels=[])
    yproj_ax.yaxis.set_label_position("right")
    yproj_ax.set_ylabel('$k_y$')
    yproj_ax.yaxis.set_major_locator(plt.LinearLocator(5))

    for ax in [img_ax, yproj_ax, xproj_ax]:  # ,cbar_ax]:
        ax.tick_params(axis="both", direction="in", bottom=True, top=True, left=True, right=True, which='both')

    clim_ = 0.01, .99

    e_img = norm_img(data[data.shape[0] // 2, :, :, data.shape[3] // 2])
    y_img = norm_img(data[:, data.shape[1] // 2, :, data.shape[3] // 2])
    x_img = norm_img(data[:, :, data.shape[2] // 2, data.shape[3] // 2].T)
    e_plot = img_ax.imshow(e_img, cmap='terrain', aspect='auto', interpolation='gaussian',
                           clim=clim_, )  # origin='lower')
    x_plot = yproj_ax.imshow(x_img, cmap='terrain', aspect='auto', interpolation='gaussian',
                             clim=clim_, )  # origin='lower')
    y_plot = xproj_ax.imshow(y_img, cmap='terrain', aspect='auto', interpolation='gaussian',
                             clim=clim_, )  # origin='lower')

    pe_x = img_ax.axvline(x_range / 2, c='orange')
    pe_y = img_ax.axhline(y_range / 2, c='orange')
    px_x = xproj_ax.axvline(x_range / 2, c='orange')
    px_e = xproj_ax.axhline(e_range / 2, c='orange')
    py_y = yproj_ax.axhline(y_range / 2, c='orange')
    py_e = yproj_ax.axvline(e_range / 2, c='orange')

    def update(e, kx, ky, kz, clim, cmap, binning, interpolate, grid, trackers, trackerscol):
        if normalize:
            e_img = norm_img(data[e, :, :, kz][::binning, ::binning])
            y_img = norm_img(data[:, ky, :, kz][::binning, ::binning])
            x_img = norm_img(data[:, :, kx, kz][::binning, ::binning])
        else:
            e_img = data[e, :, :, kz][::binning, ::binning]
            y_img = data[:, ky, :, kz][::binning, ::binning]
            x_img = data[:, :, kx, kz][::binning, ::binning]
        for axis, plot, img in zip([img_ax, yproj_ax, xproj_ax], [e_plot, x_plot, y_plot], [e_img, x_img.T, y_img]):

            plot.set_data(img)
            plot.set_clim(clim)
            plot.set_cmap(cmap)
            axis.grid(grid)
            if interpolate:
                plot.set_interpolation('gaussian')
            else:
                plot.set_interpolation(None)
            if trackers:
                pe_x.set_xdata(kx)
                pe_x.set_color(trackerscol)
                pe_y.set_ydata(ky)
                pe_y.set_color(trackerscol)
                px_x.set_xdata(kx)
                px_x.set_color(trackerscol)
                px_e.set_ydata(e)
                px_e.set_color(trackerscol)
                py_y.set_ydata(ky)
                py_y.set_color(trackerscol)
                py_e.set_xdata(e)
                py_e.set_color(trackerscol)

    interactive_plot = interactive_output(update, {'e': w_e,
                                                   'kx': w_kx,
                                                   'ky': w_ky,
                                                   'kz': w_kz,
                                                   'clim': w_clim,
                                                   'cmap': w_cmap,
                                                   'binning': w_bin,
                                                   'interpolate': w_interpolate,
                                                   'grid': w_grid,
                                                   'trackers': w_trackers,
                                                   'trackerscol': w_trackercol, });
    display(interactive_plot, tab)
    # display(tab)

    # return fig


def norm_img(data, mode='max'):
    out = np.nan_to_num(data)
    out -= np.amin(out)
    if mode == 'max':
        out /= np.amax(out)
    elif mode == 'mean':
        out /= np.amean(out)
    return out


def det_to_k(x, x0, d):
    ''' Detector pixel coordinate to momentum coordinate (in pixel)'''
    kx = (x - x0)
    while np.abs(kx) > d / 2:
        kx -= np.sign(kx) * d
    return kx


def reduce_to_first_bz(x, x0, reciprocal_lattice_vector):
    kx = (x - x0)
    while np.abs(kx) > reciprocal_lattice_vector / 2:
        kx -= np.sign(kx) * reciprocal_lattice_vector
    return kx


def to_reduced_scheme(x, aoi_k):
    """ obtain momentum coordinate in the reduced scheme.

    Follow Bloch theorem."""
    return aoi_k / 2 - (x + aoi_k / 2) % aoi_k


def to_k_parallel(x, x0, aoi_px, aoi_k):
    return (x - x0) * aoi_k / aoi_px


def to_k_parallel_reduced(x, x0, w_px, w):
    """ Transform pixel to momentum and correct to the reduced brillouin scheme"""
    kx = (x - x0) * w / w_px
    return kx - (kx + w / 2) // w


def to_k_perpendicular(xy, xy0, kf=37.285, aoi_px=219, aoi_k=2.215):
    d = point_distance(xy, xy0)
    px_to_k = aoi_k / aoi_px
    return kf * (1 - np.cos(np.arcsin(d * px_to_k / kf)))


def k_par(px, bz_w_px=219, bz_w=2.215):
    ''' Pixel to momentum converter
    bz_w_px: Brillouin zone width in pixel
    bz_w: Brillouin zone width in inverse Angstroms'''
    return


def d_to_kz(d, kf=37.285, bz_w_px=219, bz_w=2.215):
    ''' Evaluate k_z from Ewald sphere radius
    d: distance in pixels from the center of momentum space on the detector
    kf: photon momentum
    bz_w_px: Brillouin zone width in pixels
    bz_w: Brillouin zone width in inverse Angstroms'''
    return kf * (1 - np.cos(np.arcsin(k_par(d, bz_w_px, bz_w) / kf)))


def point_distance(pt1, pt2):
    return np.sqrt(np.power(pt2[0] - pt1[0], 2) + np.power(pt2[1] - pt1[1], 2))


def get_k_xyz(pt, k_center=(179, 737), reciprocal_lattice_vector=(218, 218), reciprocal_unit_cell=(2.215, 2.215, 1),
              kf=37.285):
    """ return the kx,ky,kz coordinates of a point.
    param:
        pt: tuple(float,float)
            point to evaluate (row,col)
        k_center:
            center of momentum space
        reciprocal_lattice_vector: float
            distance between 2 gamma points - BZ width
        kf: float
            final momentum from energy of photoemission photon

    given distance from gamma point and size of the brillouin zone"""
    y_c, x_c = k_center
    y_w, x_w = reciprocal_lattice_vector
    y, x = pt

    kx = k_par(det_to_k(x, x_c, reciprocal_lattice_vector[1]), bz_w_px=reciprocal_lattice_vector[1],
               bz_w=reciprocal_unit_cell[1])
    ky = k_par(det_to_k(y, y_c, reciprocal_lattice_vector[0]), bz_w_px=reciprocal_lattice_vector[0],
               bz_w=reciprocal_unit_cell[0])
    d = point_distance(pt, k_center)
    kz = d_to_kz(d, kf=kf, bz_w_px=np.mean(reciprocal_lattice_vector))
    return kx, ky, kz


def slice_to_ev(ToF, ToF_to_ev, t0):
    return (ToF - t0) * ToF_to_ev
