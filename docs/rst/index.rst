VY4E‑OptModel
=============

.. image:: ../img/VY4E-OptModel_logo_v4.png
   :alt: VY4E‑OptModel
   :align: right
   :width: 88

*A modular optimization model for power‑system planning & operations*

“Simplicity and Transparency”

What is it?
-----------
**VY4E-OptModel** is a Python library for optimization studies in power-system
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
   ``vy4e_optmodel`` (e.g., ``optmodel`` or ``vy4e``).

Contents
--------

.. toctree::
   :maxdepth: 2
   :caption: Get started

   getting-started/Installation
   getting-started/Quickstart
   getting-started/Projects
   getting-started/Papers
   getting-started/ContactUS

.. toctree::
   :maxdepth: 2
   :caption: User guide

   user-guide/project-structure
   user-guide/data-and-io
   user-guide/scenarios-and-stages
   user-guide/solvers-and-settings
   user-guide/examples

.. toctree::
   :maxdepth: 2
   :caption: Concepts

   concepts/model-sets
   concepts/decision-variables
   concepts/objective-and-costs
   concepts/constraints
   concepts/results-and-postprocessing

.. toctree::
   :maxdepth: 2
   :caption: Developer

   developer/contributing
   developer/coding-style
   developer/testing
   developer/changelog

API reference
-------------
The sections below are rendered automatically from the Python modules in ``src/``.
If you change the package name, make the same change to the ``:toctree:`` entries
or to the value of ``automodule``/``autosummary`` directives.

Core package
~~~~~~~~~~~~

.. autosummary::
   :toctree: api
   :recursive:

   vy4e_optmodel.oM_Main
   vy4e_optmodel.Modules.oM_InputData
   vy4e_optmodel.Modules.oM_ModelFormulation
   vy4e_optmodel.Modules.oM_OutputData
   vy4e_optmodel.Modules.oM_ProblemSolving

Indices and tables
------------------

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
