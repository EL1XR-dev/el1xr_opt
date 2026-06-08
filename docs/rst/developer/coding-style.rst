.. _coding-style:

Coding Style
============

To maintain consistency and readability across the codebase, we follow a standardized coding style. All contributions should adhere to these guidelines.

Code Formatting
---------------

``black`` (code formatting) and ``isort`` (import sorting) are **recommended** for new
code, but they are not enforced -- the only lint the CI runs is a flake8 syntax check
(``flake8 --select=E9,F63,F7,F82``), which catches syntax errors and undefined names,
not style. So a contribution can pass locally and still fail CI on an E9/F-class error;
run that flake8 check before pushing.

.. code-block:: bash

   # the lint CI enforces (syntax / undefined-name errors only)
   flake8 . --select=E9,F63,F7,F82

   # optional, recommended formatting
   black .
   isort .

Docstrings
----------

We follow the `NumPy/SciPy docstring standard <https://numpydoc.readthedocs.io/en/latest/format.html>`_. A typical docstring includes:

- A brief one-line summary.
- An extended description (optional).
- A parameters section.
- A returns section.

Here is an example of a well-documented function:

.. code-block:: python

   def example_function(param1, param2):
       """
       A one-line summary of the function.

       A more detailed explanation of what the function does and how it
       works.

       Parameters
       ----------
       param1 : int
           Description of the first parameter.
       param2 : str
           Description of the second parameter.

       Returns
       -------
       bool
           Description of the return value.
       """
       # Function logic here
       return True

Type Hints
----------

`Type hints <https://docs.python.org/3/library/typing.html>`_ are encouraged for new
code to improve clarity and allow static analysis. The existing modules are largely
untyped (procedural ``oM_*`` builders), so this is aspirational, not a requirement.

Example with type hints:

.. code-block:: python

   def greet(name: str) -> str:
       """
       Returns a greeting message.

       Parameters
       ----------
       name : str
           The name to include in the greeting.

       Returns
       -------
       str
           The formatted greeting message.
       """
       return f"Hello, {name}!"

Pyomo Model Naming Conventions
------------------------------

Model components use a single-letter prefix and CamelCase (no underscore), with the
energy vector in the name:

- **Parameters** start with ``p`` -- for example ``pEleMaxPower``, ``pParNumberPowerPeaks``.
- **Variables** start with ``v`` -- for example ``vEleTotalOutput``, ``vHydInventory``.
- **Constraints** start with ``e`` -- for example ``eEleBalance``, ``eHydInventory``.
- **Sets** are short lowercase names -- for example ``psn`` (period, scenario, load level),
  ``egs`` (electricity storage), ``e2h`` (electrolysers).

This convention makes it easier to identify the type of a model component just by its name.