.. _contributing:

Contributing
============

We welcome contributions to **el1xr_opt**! Whether you're fixing a bug, adding a new feature, or improving documentation, your help is appreciated. This guide will walk you through the process.

Contribution Workflow
---------------------

To contribute to the project, please follow these steps:

1. **Open an Issue**: Before starting any work, please `open an issue <https://github.com/EL1XR-dev/el1xr_opt/issues>`_ on GitHub. This allows for discussion of the proposed changes and ensures that your work aligns with the project's goals.

2. **Fork the Repository**: Create a fork of the `main repository <https://github.com/EL1XR-dev/el1xr_opt>`_ to your own GitHub account.

3. **Create a Feature Branch**: In your forked repository, create a new branch for your changes. Use a descriptive name, such as ``feature/new-technology-support`` or ``bugfix/incorrect-calculation``.

   .. code-block:: bash

      git checkout -b your-branch-name

4. **Make Changes**: Make your desired changes to the codebase. Ensure that your code follows the existing style and conventions.

5. **Commit Your Changes**: Commit your changes with a clear and descriptive commit message.

   .. code-block:: bash

      git commit -m "feat: Add support for new technology"

6. **Push to Your Fork**: Push your changes to your forked repository.

   .. code-block:: bash

      git push origin your-branch-name

7. **Submit a Pull Request**: Open a pull request from your branch to the ``main`` branch of the main repository. In the pull request description, reference the issue you created in the first step.

Setting Up the Development Environment
--------------------------------------

To set up your local development environment, follow these steps:

1. **Clone the Repository**:

   .. code-block:: bash

      git clone https://github.com/your-username/el1xr_opt.git
      cd el1xr_opt

2. **Create a Virtual Environment**: It is highly recommended to use a virtual environment to manage project dependencies.

   .. code-block:: bash

      python -m venv venv
      source venv/bin/activate  # On Windows, use `venv\Scripts\activate`

3. **Install in Editable Mode**: Install the package in editable mode. This will also install all the necessary development dependencies.

   .. code-block:: bash

      pip install -e .

4. **Install Solvers**: The optimization model requires at least one solver. You can install the recommended open-source solvers (HiGHS and CBC) with the following command:

   .. code-block:: bash

      el1xr-install-solvers

Running the Tests
-----------------

To ensure that your changes have not introduced any regressions, please run the test suite.

.. code-block:: bash

   python -m pytest tests/test_run.py

Building the Documentation
--------------------------

If you make changes to the documentation, you should build it locally to ensure that it renders correctly.

1. **Navigate to the Documentation Directory**:

   .. code-block:: bash

      cd docs/rst

2. **Install Documentation Dependencies**:

   .. code-block:: bash

      pip install -r requirements.txt

3. **Build the HTML Documentation**:

   .. code-block:: bash

      make html

The generated HTML files will be in the ``_build/html`` directory. You can open ``_build/html/index.html`` in your web browser to view the documentation.