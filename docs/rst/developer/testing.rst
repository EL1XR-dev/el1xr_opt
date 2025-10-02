.. _testing:

Testing
=======

Running the test suite is a crucial step to ensure that your changes are working correctly and have not introduced any regressions.

Running Tests
-------------

The main test script for this project is ``tests/test_run.py``. To run the test suite, use the following command from the root directory of the project:

.. code-block:: bash

   python -m pytest tests/test_run.py

This command will execute the test case defined in the script, which typically involves running a small-scale optimization problem and verifying the results.

Adding New Tests
----------------

When adding a new feature or fixing a bug, it is highly encouraged to add a corresponding test case. This helps to:

- Verify that your code works as expected.
- Protect against future regressions.
- Document the expected behavior of the code.

New tests can be added to the ``tests/test_run.py`` file or in new test files within the ``tests/`` directory.

Continuous Integration (CI)
---------------------------

The project uses GitHub Actions for Continuous Integration. The CI pipeline automatically runs the test suite and builds the documentation for every pull request. This ensures that all changes merged into the main branch are validated.