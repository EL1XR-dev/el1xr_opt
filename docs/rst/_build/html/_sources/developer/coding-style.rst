.. _coding-style:

Coding Style
============

To maintain consistency and readability across the codebase, we follow a standardized coding style. All contributions should adhere to these guidelines.

Code Formatting
---------------

We use ``black`` for code formatting and ``isort`` for import sorting. This ensures a uniform style without any need for manual adjustments.

- **black**: The uncompromising code formatter.
- **isort**: A Python utility to sort imports alphabetically and automatically separate them into sections.

Before committing your changes, please run these tools to format your code:

.. code-block:: bash

   # Format code with black
   black .

   # Sort imports with isort
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

We use `type hints <https://docs.python.org/3/library/typing.html>`_ throughout the codebase to improve code clarity and allow for static analysis. Please add type hints to all new functions and methods.

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

To ensure clarity and consistency within the `Pyomo` model, we follow a specific naming convention for model components:

- **Parameters**: Names should start with the prefix ``p_``. For example, ``p_demand``.
- **Variables**: Names should start with the prefix ``v_``. For example, ``v_generation``.
- **Constraints**: Names should start with the prefix ``e_``. For example, ``e_balance``.

This convention makes it easier to identify the type of a model component just by its name.