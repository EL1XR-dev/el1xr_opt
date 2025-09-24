el1xr_opt
=========

.. image:: https://raw.githubusercontent.com/EL1XR-dev/el1xr_opt/refs/heads/main/docs/img/el1xr_opt_logo_v6.png
   :width: 120
   :align: right
   :alt: EL1XR logo

**el1xr_opt** is the core optimization engine of the `EL1XR-dev` ecosystem. It provides a powerful and flexible modelling framework for designing and analyzing integrated, zero-carbon energy systems, with support for electricity, heat, hydrogen, and energy storage technologies.

----

🚀 Features
-----------

- Modular formulation for multi-vector energy systems
- Compatible with **deterministic, stochastic, and equilibrium** approaches
- Flexible temporal structure: hours, days, representative periods
- Built on `Pyomo <https://pyomo.readthedocs.io/en/stable/>`_
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

There are two ways to install **el1xr_opt**:

**Option 1: Install from PyPI (Recommended)**

You can install the latest stable release from PyPI:

.. code-block:: bash

   pip install el1xr_opt

**Option 2: Install from Source (for Developers)**

If you want to work with the latest development version or contribute to the project, you can install it from the source:

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

⚡ Quick Example
----------------

Run the included `Home1` example case with the following command from the root directory:

.. code-block:: bash

   python src/el1xr_opt/oM_Main.py --dir data --case Home1 --solver gurobi

This will run the optimization and save the results in the `data/Home1` directory.

----

Usage
-----

To run the optimisation model, use the ``oM_Main.py`` script from the ``src`` directory. If you run the script without arguments, it will prompt you for them interactively.

.. code-block:: bash

   python src/el1xr_opt/oM_Main.py --case <case_name> --solver <solver_name>

**Command-line Arguments**

- ``--dir``: Directory containing the case data. For the sample cases, this would be `data`.
- ``--case``: Name of the case to run (e.g., ``Home1``). Defaults to `Home1`.
- ``--solver``: Solver to use (e.g., ``gurobi``, ``cbc``, ``cplex``). Defaults to `gurobi`.
- ``--date``: Model run date in "YYYY-MM-DD HH:MM:SS" format. Defaults to the current time.
- ``rawresults``: Save raw results (`True`/`False`). Defaults to `False`.
- ``--plots``: Generate plots (`True`/`False`). Defaults to `False`.

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
