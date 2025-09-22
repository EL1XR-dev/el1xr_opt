VY4E-OptModel
=============

.. image:: https://raw.githubusercontent.com/VY4E/.github/f702b41f95871fa4c76195a16e9fb8572e3285d4/VY4E_avatar_transparent_v6.png
   :width: 120
   :align: right
   :alt: VY4E logo

**VY4E-OptModel** is the **core optimization engine** of the `VY4E <https://github.com/VY4E>`_ ecosystem.
It provides the fundamental modelling framework for **integrated zero-carbon energy systems**, supporting electricity, heat, hydrogen, and storage.

----

🚀 Features
-----------

- Modular formulation for multi-vector energy systems
- Compatible with **deterministic, stochastic, and equilibrium** approaches
- Flexible temporal structure: hours, days, representative periods
- Built on `JuMP <https://jump.dev>`_ / Pyomo (depending on module choice)
- Interfaces with ``VY4E-data`` (datasets) and ``VY4E-examples`` (notebooks)

----

📂 Structure
------------

- ``src/``: Core source code for the optimization model.
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

   git clone https://github.com/VY4E-nexus/VY4E-OptModel.git
   cd VY4E-OptModel

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

To run the optimization model, use the ``oM_Main.py`` script from the ``src`` directory.

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

Contributions are welcome! If you want to contribute to VY4E-OptModel, please follow these steps:

1. Fork the repository.
2. Create a new branch for your feature or bug fix.
3. Make your changes and commit them with a clear message.
4. Push your changes to your fork.
5. Create a pull request to the ``main`` branch of this repository.

----

📄 License
----------

This project is licensed under the terms of the `GNU General Public License v3.0 <LICENSE>`_.
