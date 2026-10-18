.. _contributing:

Contributing
============

Contributions to **el1xr_opt** are welcome: bug fixes, new features and improvements to the documentation. This page describes the process.

Contribution workflow
---------------------

A contribution follows these steps:

.. graphviz::
   :align: center
   :alt: The path of a contribution: issue, fork and branch, change, tests, docs and changelog, pre-push hook, pull request, CI, review and merge.

   digraph contrib {
     graph [rankdir=TB, nodesep=0.25, ranksep=0.22, fontname="Helvetica"];
     node  [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=10, fillcolor="#eef3fb", color="#4a6fa5"];
     edge  [color="#4a6fa5", arrowsize=0.7];
     issue  [label="Open an issue"];
     branch [label="Fork and\ncreate a branch"];
     change [label="Change the code;\na new option goes in\nthe FEATURES catalogue,\na new cost in the registry"];
     test   [label="Add tests:\nfast tier, and solve tier\nwhen a model must be solved"];
     docs   [label="Update the docs\nand the changelog"];
     hook   [label="Pre-push hook:\nflake8 + strict docs build"];
     pr     [label="Pull request to main", fillcolor="#e1bee7", color="#6a1b9a"];
     ci     [label="CI: fast, solve\nand docs jobs"];
     merge  [label="Review and merge", fillcolor="#c8e6c9", color="#2e7d32"];
     issue -> branch -> change -> test -> docs -> hook -> pr -> ci -> merge;
   }

1. **Open an Issue**: Before starting any work, please `open an issue <https://github.com/EL1XR-dev/el1xr_opt/issues>`_ on GitHub. The issue is where the proposed change is discussed and checked against the project's goals.

2. **Fork the Repository**: Create a fork of the `main repository <https://github.com/EL1XR-dev/el1xr_opt>`_ to the contributor's own GitHub account.

3. **Create a Feature Branch**: In the fork, create a new branch for the change. Use a descriptive name, such as ``feature/new-technology-support`` or ``bugfix/incorrect-calculation``.

   .. code-block:: bash

      git checkout -b feature/new-technology-support

4. **Make Changes**: Change the code, following the existing style and conventions (see :doc:`coding-style`).

5. **Commit the Changes**: Commit with a clear and descriptive commit message.

   .. code-block:: bash

      git commit -m "feat: Add support for new technology"

6. **Push to the Fork**: Push the branch to the fork.

   .. code-block:: bash

      git push origin feature/new-technology-support

7. **Submit a Pull Request**: Open a pull request from the branch to the ``main`` branch of the main repository, and reference the issue from the first step in its description.

Setting up the development environment
--------------------------------------

A local development environment is set up as follows:

1. **Clone the Repository**:

   .. code-block:: bash

      git clone https://github.com/<github-account>/el1xr_opt.git
      cd el1xr_opt

2. **Create a Virtual Environment**: It is highly recommended to use a virtual environment to manage project dependencies.

   .. code-block:: bash

      python -m venv venv
      source venv/bin/activate  # On Windows, use `venv\Scripts\activate`

3. **Install in Editable Mode**: Install the package in editable mode. This will also install all the necessary development dependencies.

   .. code-block:: bash

      pip install -e .

4. **Install Solvers**: The optimisation model needs at least one solver. HiGHS, the default, is installed on the first solve, or ahead of it with the following command (see :doc:`../user-guide/solvers-and-settings` for the others):

   .. code-block:: bash

      el1xr-install-solvers

Running the tests
-----------------

The test suite checks that a change has not broken anything. The fast tier needs no solver; the solve tier builds and solves models (see :doc:`testing`).

.. code-block:: bash

   pytest -m "not solve" tests/
   pytest -m solve tests/

Building the documentation
--------------------------

A change to the documentation is checked by building it locally.

1. **Navigate to the Documentation Directory**:

   .. code-block:: bash

      cd docs/rst

2. **Install Documentation Dependencies**:

   .. code-block:: bash

      pip install -r requirements.txt

   The diagrams are drawn by Graphviz, which is a program, not a Python package. Install it
   with the system's package manager, for example ``brew install graphviz`` on macOS,
   ``sudo apt-get install graphviz`` on Debian or Ubuntu, or ``conda install graphviz``.
   Without it the build warns on every diagram and fails with warnings treated as errors.

3. **Build the HTML Documentation**:

   .. code-block:: bash

      make html

The HTML files are written to ``_build/html``; ``_build/html/index.html`` opens the documentation in a web browser.