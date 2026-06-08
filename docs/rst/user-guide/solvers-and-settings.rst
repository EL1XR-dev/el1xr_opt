Solvers & settings
==================

An external solver is required to solve the optimization problem formulated by the model. This section provides an overview of the supported solvers and how to configure them. The module `oM_ProblemSolving` manages the process of calling the selected solver.

Supported solvers
-----------------

The default solver is **HiGHS**. The supported set is HiGHS, Gurobi, CBC, CPLEX and
Ipopt; the choice is the ``--solver`` argument (or ``solver=`` to ``routine``). Which
solver fits depends on the model's problem class -- HiGHS and CBC handle LP/MILP, Gurobi
adds QP/SOCP, and Ipopt is for the NLP network analysis (see
:doc:`../concepts/features-and-modes`).

HiGHS (default)
~~~~~~~~~~~~~~~
HiGHS is open-source and is installed automatically on the first run (an AMPL solver
module fetched by ``ensure_ampl_solvers``). No manual step is needed.

CBC
~~~
CBC is open-source but is **not** auto-installed on a normal run. Install it explicitly
with the ``el1xr-install-solvers`` console script before selecting ``--solver cbc``.

Gurobi / CPLEX
~~~~~~~~~~~~~~
Gurobi and CPLEX are commercial and require a licence; install them yourself (for
Gurobi, ``pip install gurobipy`` or the conda channel). They are reached through Pyomo
once present.

Settings
--------

- **Model options and parameters** come from the case's ``oM_Data_Option_*.csv`` and
  ``oM_Data_Parameter_*.csv`` tables (unit-commitment binaries, ramps, number of power
  peaks, discount rate, reference nodes, and the feature flags).
- **Solver tuning** is applied per solver in ``oM_ProblemSolving`` -- for example the
  barrier method and a MIP gap for Gurobi, and the interior-point method with a time
  limit for HiGHS. The Benders subproblem solves additionally tighten the feasibility
  tolerance (see :doc:`decomposition`).

The ``oM_SolverSetup`` module detects available solvers and prepares them for use by
``oM_ProblemSolving``.

.. automodule:: el1xr_opt.Modules.oM_SolverSetup
    :members:
    :no-index: