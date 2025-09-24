el1xr_opt
=============

.. image:: https://raw.githubusercontent.com/EL1XR-dev/el1xr_opt/refs/heads/main/docs/img/el1xr_opt_logo_v6.png
   :width: 120
   :align: right
   :alt: EL1XR logo

**el1xr_opt** is the **core optimization engine** of the `EL1XR-dev <https://github.com/EL1XR-dev>`_.
It provides the fundamental modelling framework for **integrated zero-carbon energy systems**, supporting electricity, heat, hydrogen, and storage.

----

🚀 Features
-----------

- Modular formulation for multi-vector energy systems
- Compatible with **deterministic, stochastic, and equilibrium** approaches
- Flexible temporal structure: hours, days, representative periods
- Built on `JuMP <https://jump.dev>`_ / Pyomo (depending on module choice)
- Interfaces with ``EL1XR-data`` (datasets) and ``EL1XR-examples`` (notebooks)

----

📂 Structure
------------

- ``src/``: Core source code for the optimisation model.
- ``data/``: Sample case studies.
- ``docs/``: Documentation and formulation notes.
- ``tests/``: Validation and regression tests.

----

📦 Prerequisites
----------------

- **Python 3.12** or higher.
- A supported solver: **Gurobi, CBC, or CPLEX**. Make sure the solver is installed and accessible in your system's PATH.

----

🚀 Installation
---------------

1. Clone the repository:

.. code-block:: bash

   git clone https://github.com/EL1XR-dev/el1xr_opt.git
   cd el1xr_opt

2. Create and activate a virtual environment (recommended):

.. code-block:: bash

   python -m venv venv
   source venv/bin/activate  # On Windows use `venv\Scripts\activate`

3. Install the required Python packages:

.. code-block:: bash

   pip install -r requirements.txt

----

Usage
-----

To run the optimisation model, use the ``oM_Main.py`` script from the ``src`` directory.

.. code-block:: bash

   python src/oM_Main.py --case <case_name> --solver <solver_name>

**Command-line Arguments**

- ``--dir``: Directory containing the case data (defaults to the current directory).
- ``--case``: Name of the case to run (e.g., ``Home1``).
- ``--solver``: Solver to use (e.g., ``gurobi``, ``cbc``, ``cplex``).
- ``--date``: Model run date in "YYYY-MM-DD HH:MM:SS" format.
- ``--rawresults``: Save raw results (``True``/``False``).
- ``--plots``: Generate plots (``True``/``False``).

----

🤝 Contributing
---------------

Contributions are welcome! If you want to contribute to **el1xr_opt**, please follow these steps:

1. Fork the repository.
2. Create a new branch for your feature or bug fix.
3. Make your changes and commit them with a clear message.
4. Push your changes to your fork.
5. Create a pull request to the ``main`` branch of this repository.

----

📄 License
----------

This project is licensed under the terms of the `GNU General Public License v3.0 <LICENSE>`_.
