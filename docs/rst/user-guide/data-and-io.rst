Data & I/O
==========

Data formats
------------
The model is data-driven, with all inputs defined in a collection of CSV files
located in a dedicated case directory. These files define the model's sets (e.g.,
periods, technologies, nodes) and parameters (e.g., costs, capacities, efficiencies).

Loaders
-------
.. autofunction:: el1xr_opt.Modules.oM_LoadCase.load_case

Writers
-------
.. automodule:: el1xr_opt.Modules.oM_OutputData
    :members: saving_rawdata, saving_results
