el1xr_opt
=============
**Simplicity and Transparency:** *A modular optimization model for power‑system planning & operations*

What is it?
-----------
**el1xr_opt** is a Python library for optimization studies in power-system
**planning** and **operations**. It builds a multi-vector model -- **electricity,
hydrogen and heat** with storage and demand-side flexibility -- over a
period/scenario/load-level horizon, and solves it with Pyomo.

Key features
------------
- **Multi-vector**: electricity, hydrogen (electrolyser, fuel cell, storage) and a
  behind-the-meter heat sector (heat pump, boiler, thermal store, heat-to-power),
  coupled through the energy balances.
- **Time structure**: ``period → scenario → load level`` (hours or representative
  periods, with per-level durations).
- **Investment + operation**: optional capacity-sizing of candidate generators and
  storage, on the same discounted footing as operation.
- **Markets**: day-ahead energy, retail tariffs (energy, capacity and a top-N
  peak-demand charge), and frequency reserves (FCR-D / FCR-N).
- **Solve modes**: a single monolithic solve, or **Benders decomposition** (by
  scenario or by time window, with storage-boundary and peak-threshold linking).
- **Solvers**: HiGHS by default; Gurobi, CBC, CPLEX and Ipopt are also supported.
- **Input/output**: a case is a folder of CSV files **or** a single ``.duckdb`` file
  (read identically); results are written to ``results.duckdb`` by default, with CSV
  and plots available on request.

This documentation is organized around **getting started**, **user guide**,
**concepts**, and an **API reference** generated from the source docstrings.

Index
--------

.. toctree::
   :maxdepth: 2
   :caption: Get started

   getting-started/Installation
   getting-started/Quickstart
   getting-started/Projects
   getting-started/Papers
   getting-started/ContactUs


.. toctree::
   :maxdepth: 2
   :caption: User guide

   user-guide/project-structure
   user-guide/data-and-io
   user-guide/scenarios-and-stages
   user-guide/solvers-and-settings
   user-guide/decomposition
   user-guide/network-analysis
   user-guide/examples

.. toctree::
   :maxdepth: 2
   :caption: Concepts

   concepts/sets
   concepts/parameters
   concepts/variables
   concepts/objective-function
   concepts/constraints
   concepts/heat-sector
   concepts/community
   concepts/features-and-modes
   concepts/results-and-postprocessing
   concepts/future-developments

.. toctree::
   :maxdepth: 2
   :caption: API reference

   api/index

.. toctree::
   :maxdepth: 2
   :caption: Developer

   developer/contributing
   developer/coding-style
   developer/testing
   developer/changelog
