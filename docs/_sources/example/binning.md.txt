## Binning multidimensional data

In order to get n-dimensional numpy array from the generated datasets, it is necessary to bin data along the desired axes. An example starting from loading parquet data is in the following,
```python
processor = DldFlashProcessor()
processor.runNumber = 18843
processor.readDataframes('path/to/file/name')
```

This can be also done from direct raw data read with `readData` To create the bin array structure, run
```python
processor.addBinning('dldPosX',480,980,10)
processor.addBinning('dldPosY',480,980,10)
```

This adds binning along the kx and ky directions, from point 480 to point 980 with bin size of 10. Bins can be created defining start and end points and either step size or number of steps. The resulting array can be obtained using
```python
result = processor.ComputeBinnedData()
```

where the resulting numpy array with float64-typed values will have the axes in the same order as binning assignments. Other binning axes commonly used are,
```eval_rst
+-----------------------+---------------------+----------------+--------+
|      Proper name      |     Namestring      | Typical values |  Units |
+=======================+=====================+================+========+
|    ToF delay (ns)     |      'dldTime'      |  620,670,10 *  |    ns  |
+-----------------------+---------------------+----------------+--------+
| Pump-probe time delay |  'pumpProbeDelay'   |    -10,10,1    |    ps  |
+-----------------------+---------------------+----------------+--------+
|     Separate DLDs     |   'dldDetectors'    |     -1,2,1     |    ID  |
+-----------------------+---------------------+----------------+--------+
| Microbunch (pulse) ID |   'microbunchId'    |   0,500,1 **   |    ID  |
+-----------------------+---------------------+----------------+--------+
|   Auxiliary channel   |      'dldAux'       |                |        |
+-----------------------+---------------------+----------------+--------+
| Beam arrival monitor  |        'bam'        |                |    fs  |
+-----------------------+---------------------+----------------+--------+
|   FEL bunch charge    |    'bunchCharge'    |                |        |
+-----------------------+---------------------+----------------+--------+
|     Macrobunch ID     | 'macroBunchPulseId' |                |    ID  |
+-----------------------+---------------------+----------------+--------+
|  Laser diode reading  |   'opticalDiode'    | 1000,2000,100  |        |
+-----------------------+---------------------+----------------+--------+
|           ?           |     'gmdTunnel'     |                |        |
+-----------------------+---------------------+----------------+--------+
|           ?           |      'gmdBda'       |                |        |
+-----------------------+---------------------+----------------+--------+
```

\* ToF delay bin size needs to be multiplied by `processor.TOF_STEP_TO_NS` in order to avoid artifacts.

\** binning on microbunch works only when not binning on any other dimension

Binning is created using np.linspace (formerly was done with `np.arange`). The implementation allows to choose between setting a step size (`useStepSize=True, default`) or using a number of bins (`useStepSize=False`).

In general, it is not possible to satisfy all 3 parameters: start, end, steps. For this reason, you can choose to give priority to the step size or to the interval size. In the case of `forceEnds=False`, the steps parameter is given priority and the end parameter is redefined, so the interval can actually be larger than expected. In the case of `forceEnds = true`, the stepSize is not enforced, and the interval is divided by the closest step that divides it cleanly. This of course only has meaning when choosing steps that do not cleanly divide the interval.