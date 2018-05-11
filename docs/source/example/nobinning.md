## Processing data without binning

Sometimes it is not necessary to bin the electrons to extract the data. It is actually possible to directly extract data from the appropriate dataframe. This is useful if, for example, you just want to plot some parameters, not involving the number of electrons that happen to have such a value (this would require
binning).

Because of the structure of the dataframe, which is divided in dd and ddMicrobunches, it is possible to get electron-resolved data (the electron number will be on the x axis), or microbunch-resolved data (the microbunch ID, or `uBid`, will be on the x axis).

The data you can get from the dd dataframe (electron-resolved) includes:
```eval_rst
+--------------------------------+--------------------+
|        Proper name             |  Namestring        |
+================================+====================+
| x position of the electron     |  'dldPosX'         |
+--------------------------------+--------------------+
| y position of the electron     |  'dldPosY'         |
+--------------------------------+--------------------+
|       time of flight           |  'dldTime'         |
+--------------------------------+--------------------+
|pump probe delay stage reading  |  'delayStageTime'  |
+--------------------------------+--------------------+
|  beam arrival monitor jitter   |  'bam'             |
+--------------------------------+--------------------+
|        microbunch ID           |  'microbunchId'    |
+--------------------------------+--------------------+
|       which detector           |  'dldDetectorId'   |
+--------------------------------+--------------------+
|     electron bunch charge      |  'bunchCharge'     |
+--------------------------------+--------------------+
|pump laser optical diode reading|  'opticalDiode'    |
+--------------------------------+--------------------+
|  gas monitor detector reading  |                    |
|  before gas attenuator         | 'gmdTunnel'        |
+--------------------------------+--------------------+
|  gas monitor detector reading  |                    |
|  after gas attenuator          | 'gmdBda'           |
+--------------------------------+--------------------+
|        macrobunch ID           | 'macroBunchPulseId'|
+--------------------------------+--------------------+
```

The data you can get from the `ddMicrobunches` (uBID-resolved) dataframe includes:
```eval_rst
+---------------------------------+--------------------+
|           Proper name           |     Namestring     |
+=================================+====================+
| pump probe delay stage reading  |  'delayStageTime'  |
+---------------------------------+--------------------+
|   beam arrival monitor jitter   |       'bam'        |
+---------------------------------+--------------------+
|     auxillary channel 0         |       'aux0'       |
+---------------------------------+--------------------+
|     auxillary channel 1         |       'aux1'       |
+---------------------------------+--------------------+
|    electron bunch charge        |    'bunchCharge'   |
+---------------------------------+--------------------+
| pump laser optical diode reading|   'opticalDiode'   |
+---------------------------------+--------------------+
|        macrobunch ID            | 'macroBunchPulseId'|
+---------------------------------+--------------------+
```

Some of the values overlap, and in these cases, you can get the values either uBid-resolved or electron-resolved.

An example of how to retrieve values both from the `dd` and `ddMicrobunches` dataframes:
```python
bam_dd=processor.dd['bam'].values.compute()
bam_uBid=processor.ddMicrobunches['bam'].values.compute()
```
Be careful when reading the data not to include IDs that contain NaNs (usually at the beginning), otherwise this method will return all NaNs.

It is also possible to access the electron-resolved data on a `uBid` basis by using
```python
uBid=processor.dd['microbunchId'].values.compute()
value[int(uBid[j])]
```
or to plot the values as a function of `uBid` by using
```python
uBid=processor.dd['microbunchId'].values.compute()
MBid=processor.dd['macroBunchPulseId'].values.compute()
bam=processor.dd['bam'].values.compute()

pl.plot(uBid+processor.bam.shape[1]*MBid,bam)
```

The following code, as an example, averages `gmdTunnel` values for electrons that have the same `uBid` (it effectively also bins the electrons in `avgNorm` as a side effect):
```python
uBid=processor.dd['microbunchId'].values.compute()
pow=processor.dd['gmdBDA'].values.compute()

avgPow=np.zeros(500)
avgNorm=np.zeros(500)
for j in range(0,len(uBid)):
    if(uBid[j]>0 and uBid[j]<500 and pow[j]>0):
        avgNorm[int(uBid[j])]+=1
        avgPow1[int(uBid[j])]=(avgPow1[int(uBid[j])]*(avgNorm[int(uBid[j])])+pow[j])/(avgNorm[int(uBid[j])]+1.0)

```