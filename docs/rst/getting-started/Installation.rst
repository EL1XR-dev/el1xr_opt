Installation
============

Requirements
------------
- Python >= 3.11
- An LP/MILP solver: HiGHS (installed on the first run), Gurobi, CBC or CPLEX

Install the latest release from PyPI::

    pip install el1xr_opt

This documentation follows the ``main`` branch on GitHub, which can be ahead of the latest
release. A feature described here may need the version from GitHub, installed as below.
HiGHS is installed on the first run; see :doc:`../user-guide/solvers-and-settings` for the
other solvers.

Alternatively, install (editable) with the recommended `el1xr_opt/` layout::

    git clone https://github.com/EL1XR-dev/el1xr_opt.git
    cd el1xr_opt
    pip install -e .[dev]
