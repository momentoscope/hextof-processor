## Save dataset to dask parquet files

For faster access to these dataframes in extended offline analysis, it is convenient to store the datasets in dask parquet dataframes. This is done using
```python
processor.storeDataframes('filename')
```

This saves two folders in path/to/file: **name_el** and **name_mb**. These are the two datasets `processor.dd` and `processor.ddMicrobunches`. If `'filename'` is not specified, it uses either `'run{runNumber}'` or `'mb{firstMacrobunch}to{lastMacrobunch}'`, for example, `run18843`, or `mb90000000to900000500`.



Datasets in parquet format can be loaded back into the processor using the `readDataframes` method.
```python
processor = DldFlashProcessor()
processor.readDataframes('filename')
```


An optional parameter for both `storeDataframes` and `readDataframes` is `path=''`. If it is unspecified, (left as default None) the values from`DATA_PARQUET_DIR` or `DATA_H5_DIR` in **SETTINGS.ini** is used.

Alternatively, it is possible to store these datasets similarly in hdf5 format, using the same function,
```python
processor.storeDataframes('filename', format='hdf5')
```
However, this is NOT advised, since the parquet format outperforms the hdf5 in reading and data manipulation. This functionality is mainly kept for retro-compatibility with older datasets.