Data & I/O
==========

Data formats
------------
The model is data-driven, with all inputs defined in a collection of CSV files
located in a dedicated case directory. These files define the model's sets (e.g.,
periods, technologies, nodes) and parameters (e.g., costs, capacities, efficiencies).

CSV File Naming Conventions
~~~~~~~~~~~~~~~~~~~~~~~~~~~

The input CSV files follow a specific naming convention to distinguish between
different types of data:

- **``oM_Dict...``**: Files starting with this prefix are used to define the model's
  sets and dictionaries. These typically contain lists of technologies, nodes,
  or other categorical data.

- **``oM_Data...``**: Files starting with this prefix contain the numerical data
  for the model's parameters, such as costs, efficiencies, or time series data.

This convention helps in organizing the input data and is used by the data loading
functions to correctly process the files.

Loaders
-------
.. autofunction:: el1xr_opt.Modules.oM_LoadCase.load_case

Writers
-------
.. automodule:: el1xr_opt.Modules.oM_OutputData
    :members: saving_rawdata, saving_results
