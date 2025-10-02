Solvers & settings
==================

An external solver is required to solve the optimization problem formulated by the model. This section provides an overview of the supported solvers and how to configure them. The module `oM_ProblemSolving` manages the process of calling the selected solver.

Supported solvers
-----------------

The model supports the following solvers:

Gurobi
~~~~~~
Gurobi is a commercial solver that requires a license. It is not installed automatically and must be installed separately by the user. You can find installation instructions on the official `Gurobi website <https://www.gurobi.com/documentation/>`_.

Example installation commands:

.. code-block:: bash

   # Using pip
   pip install gurobipy

   # Using conda
   conda config --add channels http://conda.anaconda.org/gurobi
   conda install gurobi

HiGHS & CBC
~~~~~~~~~~~
HiGHS and CBC are open-source solvers. They are downloaded and installed automatically by functions within the `oM_SolverSetup` module if they are not already present in your environment. No manual installation is typically required.

Configuration
-------------
The solver configuration is managed by the `oM_SolverSetup` module, which is responsible for detecting available solvers and preparing them for use by the `oM_ProblemSolving` module.

.. automodule:: el1xr_opt.Modules.oM_SolverSetup
    :members: