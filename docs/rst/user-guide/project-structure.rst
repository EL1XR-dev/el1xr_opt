Project structure
=================

Source layout
-------------
This project follows a `src/` layout:

::

    VY4E-OptModel/
    ├─ pyproject.toml
    ├─ src/
    │  └─ vy4e_optmodel/
    │     ├─ __init__.py
    │     ├─ data/
    │     ├─ model/
    │     ├─ optimization/
    │     ├─ scenarios/
    │     ├─ solvers/
    │     └─ results/
    └─ docs/

Imports resolve via the package name (e.g., ``vy4e_optmodel.model``).
