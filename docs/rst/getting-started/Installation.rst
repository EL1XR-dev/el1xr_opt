Installation
============

Requirements
------------
- Python >= 3.10
- A MILP/MINLP solver (e.g., Gurobi, HiGHS, CBC)
- Sphinx (for docs)

Install (editable) with the recommended `src/` layout::

    git clone https://github.com/VY4E/VY4E-OptModel.git
    cd VY4E-OptModel
    pip install -e .[dev]

Optional extras::

    pip install .[docs]   # build documentation
    pip install .[plot]   # plotting and post-processing
