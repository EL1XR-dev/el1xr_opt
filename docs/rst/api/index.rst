API reference
=============

These pages are generated automatically from the docstrings in
``src/el1xr_opt``. Every time the documentation is built, Sphinx re-reads the
source modules and regenerates this section, so the API reference stays in step
with the code. Read the Docs rebuilds on every push, and a continuous-integration
job builds the docs on each pull request, so a broken or missing reference fails
the build before it is merged.

To document a function or class, write a docstring (NumPy or Google style) in the
source. It will appear here on the next build. To add a new module to the
reference, add one line to the ``autosummary`` list below.

.. autosummary::
   :toctree: generated
   :template: autosummary/module.rst

   el1xr_opt.el1xr_Main
   el1xr_opt.Modules.oM_LoadCase
   el1xr_opt.Modules.oM_InputSchema
   el1xr_opt.Modules.oM_InputSource
   el1xr_opt.Modules.oM_InputCSVSource
   el1xr_opt.Modules.oM_InputDuckDBSource
   el1xr_opt.Modules.oM_CsvToDuckDB
   el1xr_opt.Modules.oM_InputData
   el1xr_opt.Modules.oM_Investment
   el1xr_opt.Modules.oM_GreenHydrogen
   el1xr_opt.Modules.oM_HeatSector
   el1xr_opt.Modules.oM_ModelFormulation
   el1xr_opt.Modules.oM_ProblemSolving
   el1xr_opt.Modules.oM_SolverSetup
   el1xr_opt.Modules.oM_OutputData
   el1xr_opt.Modules.oM_OutputData_duckdb
   el1xr_opt.Modules.oM_Decomposition
   el1xr_opt.Modules.oM_Sequence
   el1xr_opt.Modules.utils.oM_Utils
