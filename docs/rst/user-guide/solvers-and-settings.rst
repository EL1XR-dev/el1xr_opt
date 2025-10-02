Solvers & settings
==================

Supported solvers
-----------------
This project supports the following solvers, which are managed via ``amplpy``:

- HiGHS
- CBC

.. note::
    If a required solver is not found in your environment, the program will
    attempt to install it automatically.

Configuration
-------------
The solver selection and configuration is managed by the ``oM_SolverSetup``
module. For detailed information on the available functions and their
parameters, please refer to the API documentation below.

.. automodule:: el1xr_opt.Modules.oM_SolverSetup
    :members: pick_solver, ensure_ampl_solvers