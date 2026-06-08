Project structure
=================

Source layout
-------------
This project follows a `src/` layout:

::

    el1xr_opt/
    ├─ pyproject.toml
    ├─ src/
    │  └─ el1xr_opt/
    │     ├─ __init__.py
    │     ├─ __main__.py            # CLI entry point (python -m el1xr_opt)
    │     ├─ el1xr_Main.py          # argument parsing / el1xr-run
    │     ├─ Grid1/  Home1/         # sample cases
    │     └─ Modules/
    │        ├─ oM_Sequence.py            # build_model / routine: orchestrates the run
    │        ├─ oM_LoadCase.py            # builds the argument dict
    │        ├─ oM_InputSource.py         # source abstraction (open_source / resolve_source)
    │        ├─ oM_InputCSVSource.py      #   CSV folder reader
    │        ├─ oM_InputDuckDBSource.py   #   .duckdb reader
    │        ├─ oM_InputSchema.py         #   table/column schema
    │        ├─ oM_CsvToDuckDB.py         # el1xr-csv2duckdb converter
    │        ├─ oM_InputData.py           # data_processing: sets and parameters
    │        ├─ oM_ModelFormulation.py    # core constraints and objective
    │        ├─ oM_Investment.py          # capacity-sizing layer
    │        ├─ oM_GreenHydrogen.py       # RFNBO matching + PPA
    │        ├─ oM_HeatSector.py          # heat pump / boiler / store / heat-to-power
    │        ├─ oM_Community.py           # virtual energy sharing
    │        ├─ oM_Features.py            # flag catalogue, problem class, cost registry
    │        ├─ oM_Decomposition.py       # Benders (monolithic alternative)
    │        ├─ oM_ACOPF.py oM_LinDist3Flow.py  # decoupled network analysis
    │        ├─ oM_ProblemSolving.py oM_SolverSetup.py  # solve + solver setup
    │        ├─ oM_OutputData.py oM_OutputData_duckdb.py  # CSV / DuckDB results
    │        └─ utils/
    ├─ data/   # case studies (H2VPP, EEM26, sizing variants)
    ├─ tests/
    └─ docs/

Imports resolve via the package name (e.g., ``el1xr_opt.Modules``).