el1xr_opt
=========
.. image:: https://raw.githubusercontent.com/EL1XR-dev/el1xr_opt/refs/heads/main/docs/img/el1xr_opt_logo_v6.png
   :width: 120
   :align: right
   :alt: EL1XR logo

|

.. image:: https://badge.fury.io/py/el1xr_opt.svg
    :target: https://badge.fury.io/py/el1xr_opt
    :alt: PyPI

.. image:: https://img.shields.io/pypi/pyversions/el1xr_opt.svg
   :target: https://pypi.org/project/el1xr_opt/
   :alt: Python version

.. image:: https://img.shields.io/github/actions/workflow/status/EL1XR-dev/el1xr_opt/conda-build.yml
   :target: https://github.com/EL1XR-dev/el1xr_opt/actions/workflows/conda-build.yml   
   :alt: GitHub Actions Workflow Status

.. image:: https://img.shields.io/readthedocs/el1xr_opt
   :target: https://el1xr-opt.readthedocs.io/en/latest/
   :alt: Read the Docs

.. image:: https://app.codacy.com/project/badge/Grade/2b804a25f68749498c5207dcdd05ed67
   :target: https://app.codacy.com/gh/EL1XR-dev/el1xr_opt/dashboard?utm_source=gh&utm_medium=referral&utm_content=&utm_campaign=Badge_grade
   :alt: Codacy Badge

.. image:: https://img.shields.io/pepy/dt/el1xr_opt.svg
   :target: https://pepy.tech/project/el1xr_opt
   :alt: Downloads

**Electricity for Low-carbon Integration and eXchange of Resources (EL1XR)**

**el1xr_opt** is the core optimisation engine of the `EL1XR-dev` ecosystem. It provides a powerful and flexible modelling framework for designing and analysing integrated, zero-carbon energy systems, with support for electricity, heat, hydrogen, and energy storage technologies.

----

🚀 Features
-----------

- `Documentation <https://el1xr-opt.readthedocs.io/en/latest/>`_ via ReadTheDocs.
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

- **Python 3.11** or higher.
- A supported solver: **HiGHS, Gurobi, CBC, or CPLEX**. The recommended solvers can be installed automatically using the command below.

----

🚀 Installation
---------------

There are two ways to install **el1xr_opt**:

**Option 1: Install from PyPI (Recommended)**

1. Install the package from PyPI:

.. code-block:: bash

   pip install el1xr_opt

2. Install the required solvers:

.. code-block:: bash

   el1xr-install-solvers

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

3. Install the package in editable mode, which also installs the necessary dependencies:

.. code-block:: bash

   pip install -e .

4. Install the required solvers:

.. code-block:: bash

   el1xr-install-solvers

----

⚡ Quick Example
----------------

Run the included `Home1` example case with the following command from the root directory:

.. code-block:: bash

   el1xr-run --case Home1 --solver highs

This will run the optimisation and save the results in the `src/el1xr_opt/Home1/Results` directory.

----

Usage
-----

To run the optimisation model, use the ``el1xr-run`` command. If you run the script without arguments, it will prompt you for them interactively. Moreover, the model can be executed with explicit information as follows:

.. code-block:: bash

   python -m el1xr_opt --dir <folder_parent_case> --case <case_folder_name> --solver  <solver_name> --date <date_string> --rawresults <'Yes'-or-'No'> --plots <'Yes'-or-'No'>

For example:

.. code-block:: bash

   python -m el1xr_opt --dir data --case Home1 --solver highs --date "2025-09-30 20:26:00" --rawresults No --plots No

**Command-line Arguments**

- ``--dir``: Directory containing the case data. For the sample cases, this would be `src/el1xr_opt`.
- ``--case``: Name of the case to run (e.g., ``Home1``). Defaults to `Home1`.
- ``--solver``: Solver to use (e.g., ``highs``, ``gurobi``, ``cbc``, ``cplex``). Defaults to `highs`.
- ``--date``: Model run date in "YYYY-MM-DD HH:MM:SS" format. Defaults to the current time.
- ``--rawresults``: Save raw results (`True`/`False`). Defaults to `False`.
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
