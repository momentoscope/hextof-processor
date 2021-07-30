## Compiling Doniach-Sunjic gaussian broadened

For this, you will need boost. The setup file is intended for python 3.7, please adjust this to your needs.
If using conda, install boost
```
conda install -c anaconda boost
```
Then, compile the extension, navigate to the processor/utilities/XPSdoniachs folder and run:
```
 python setup.py build_ext --inplace
```
This should compile. Then, to import the Doniach-Sunjic functions, run
```python
from processor.utilities.XPSdoniachs import XPSdoniachs_ext
```
This will let you use the following functions, programmed after J.J.Joyce, M.Del Giudice and J.H.Weaver,
"Quantitative Analysis of Synchrotron Radiation Photoemission Core Level Data",
J.Electr.Spectrosc.Relat.Phenom. 49(1989)31-45. - integration by Simpson's rule:
```python
XPSdoniachs_ext.dsgn
XPSdoniachs_ext.dsgnmEad2
XPSdoniachs_ext.dsgnmBad2
```
The first one, dsgn, is a single DS function convoluted with a gaussian with a linear background. It has 7 parameters:
- w[0] is the bg offset
- w[1] is the bg slope

- w[2] L - first lineshape parameter, this is the Lorentzian FWHM
- w[3] A - second lineshape parameter, this is the asymmetry parameter
- w[4] G - third lineshape parameter, this is the Gaussian FWHM

- w[5] this is the intensity
- w[6] this is the binding energy, with asymmetry towards the left, fermi edge on the right

The second one, dsgnmEad2, is a multiple DS function. It is the same as dsgn, but ou can include multiple peaks
by adding 5 additional parameters per peak after w[6]. The binding energy is relative to the first peak.

The third one, dsgnmBad2, is a multiple DS function. It is the same as dsgn, but ou can include multiple peaks
by adding 5 additional parameters per peak after w[6]. The binding energy is absolute.

### XPSdoniachs Usage

The usage is a little complicated due to the nature of boost. The functions require 2 inputs: a float, for the energy
to calculate the DS at, and a "vector of double" object, for the input parameters. You can create this and add elements
to it by
```python
pp = XPSdoniachs.XPSdoniachs_ext.VectorOfDouble()
pp.extend(val)
```
After this, you can call
```python
XPSdoniachs.XPSdoniachs_ext.dsgn(x,pp)
```

Here is an example of how you can use this with lmfit
```python
from processor.utilities.XPSdoniachs import XPSdoniachs_ext as dsg
from lmfit import Model

def ds(x,bg0,bg1,l,a,g,i,e):
    pi=[bg0,bg1,l,a,g,i,e]
    y = np.zeros_like(x)
    pp = dsg.VectorOfDouble()
    pp.extend(i for i in pi)
    try:
        for i in range(len(x)):
            y[i] = dsg.dsgn(x.values[i],pp)
        return y
    except AttributeError:
        for i in range(len(x)):
            y[i] = dsg.dsgnmEad2(x[i],pp)
        return y

dsmodel = Model(ds)
print('parameter names: {}'.format(dsmodel.param_names))
print('independent variables: {}'.format(dsmodel.independent_vars))
params = dsmodel.make_params(bg0=0.,bg1=0.,l=0.4,a=0.15,g=0.4,i=2000,e=-284.4)

result = dsmodel.fit(data, params, x=data_x)
print(result.fit_report())
plt.figure()
plt.plot(res.energy, res.sel(dldSectorId=(0.5)), 'bo')
plt.plot(res.energy, result.init_fit, 'k--', label='initial fit')
plt.plot(res.energy, result.best_fit, 'r-', label='best fit')
plt.legend(loc='best')
plt.show()
```