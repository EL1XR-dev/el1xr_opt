.. VY4E-OptModel documentation master file, created by Erik Alvarez

VY4E‑OptModel
=============
*A modular optimization model for power‑system planning & operations*

“*Simplicity and Transparency*”

**VY4E** is an open-source model distributed as a Python library, designed to provide optimal planning, operation, and management strategies for multi-vector energy systems. It supports both stand-alone and grid-connected systems in participating in electricity markets, ensuring the seamless integration of new assets and efficient system scheduling.
It targets distribution planning and operational studies with support for flexibility options (BESS, H2, DSM), multi‑stage/scenario formulations, and solver‑agnostic backends.

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

   vy4e_optmodel
   vy4e_optmodel.data
   vy4e_optmodel.model
   vy4e_optmodel.optimization
   vy4e_optmodel.scenarios
   vy4e_optmodel.solvers
   vy4e_optmodel.results
   vy4e_optmodel.cli

Indices and tables
------------------

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
