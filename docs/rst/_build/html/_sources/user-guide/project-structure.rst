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
    │     ├─ __main__.py
    │     ├─ el1xr_Main.py
    │     ├─ Grid1/
    │     ├─ Home1/
    │     └─ Modules/
    │        ├─ __init__.py
    │        ├─ oM_InputData.py
    │        ├─ oM_LoadCase.py
    │        ├─ oM_ModelFormulation.py
    │        ├─ oM_OutputData.py
    │        ├─ oM_ProblemSolving.py
    │        ├─ oM_Sequence.py
    │        └─ oM_SolverSetup.py
    └─ docs/

Imports resolve via the package name (e.g., ``el1xr_opt.Modules``).