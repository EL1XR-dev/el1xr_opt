el1xr_opt
=============
**Simplicity and Transparency:** *A modular optimization model for power‑system planning & operations*

What is it?
-----------
**el1xr_opt** is a Python library for optimization studies in power-system
**planning** and **operations**, supporting multi-vector flexibility (BESS, H₂, DSM),
multi-stage/**scenario** formulations, and multiple solvers via Pyomo.

Key features
------------
- **Modular `src/` layout**: ``data``, ``model``, ``optimization``, ``scenarios``,
  ``solvers``, ``results``.
- **Flexible time structure**: ``period → scenario → stage`` (hours or representative periods).
- **Technologies**: batteries, hydrogen subsystems, DSM, and transmission elements.
- **Solver-agnostic**: Gurobi, HiGHS, or CBC.
- **Reproducible I/O**: CSV/Parquet data, YAML/JSON settings.

This documentation is organized around **getting started**, **how‑to guides**, **concepts**,
and **API reference** generated from the source code under ``src/``.

.. note::
   Update the package import path below if your top‑level package differs from
   ``el1xr_opt`` (e.g., ``optmodel`` or ``el1xr``).

Core package
~~~~~~~~~~~~

.. autosummary::
   :toctree: api
   :recursive:

   el1xr_opt.oM_Main
   el1xr_opt.Modules.oM_InputData
   el1xr_opt.Modules.oM_ModelFormulation
   el1xr_opt.Modules.oM_OutputData
   el1xr_opt.Modules.oM_ProblemSolving


