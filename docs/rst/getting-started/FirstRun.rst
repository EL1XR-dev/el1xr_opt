A first case, from input to results
===================================

This page solves the ``Home1`` case that ships with the package and reads its results. The
steps take a few minutes and need only the package and HiGHS, which is installed on the first
solve.

Copy of the case
----------------

The case is copied to a working folder, so the package folder stays unchanged:

.. code-block:: bash

   python -c "import el1xr_opt, shutil, pathlib; shutil.copytree(pathlib.Path(el1xr_opt.__file__).parent / 'Home1', 'cases/Home1')"

The folder ``cases/Home1`` now holds the CSV files of the case. The data files are described
in :doc:`../user-guide/data-and-io`, and the case itself in :doc:`../user-guide/examples`.

Solution
--------

.. code-block:: bash

   el1xr-run --dir cases --case Home1 --solver highs --date "2025-01-01 00:00:00" --rawresults False --plots False

The solve takes about half a minute for the 8736 hourly load levels of the case. The command
exits with code 0 and writes ``cases/Home1/results.duckdb``. The arguments are listed in
:doc:`Quickstart`.

Results
-------

``results.duckdb`` holds one table per set, parameter, variable and constraint dual, and a
table of run metadata. The `DuckDB <https://duckdb.org>`_ package, installed with el1xr_opt,
reads it:

.. code-block:: python

   import duckdb

   con = duckdb.connect("cases/Home1/results.duckdb", read_only=True)
   print(con.sql("SELECT Key, Value FROM oM_Result_RunMetadata").df())
   buy = con.sql("""
       SELECT index_2 AS load_level, SUM(value) AS bought
       FROM vEleBuy GROUP BY load_level ORDER BY load_level
   """).df()
   print(buy.head())

The first table gives the case, the solver and the objective (4713.8 for this case, in the
currency of the case). The second gives the electricity bought from the market at each load
level. A variable table has one column per index (``index_0`` for the period, ``index_1``
for the scenario, ``index_2`` for the load level, ``index_3`` for the unit or retailer), and
the columns ``value``, ``lb`` and ``ub``.

The variables are named as in :doc:`../concepts/variables`. When the case sets ``Factor1``
or ``MoneyBase`` to values other than 1, quantities and money in ``results.duckdb`` are scaled;
:doc:`../user-guide/data-and-io` gives the conversion.

Next steps
----------

- A change to the case, for example a battery's ``MaximumStorage`` in
  ``oM_Data_ElectricityGeneration_Home1.csv``, followed by a new solve.
- The CSV result files and plots, with ``--rawresults True`` and ``--plots True``:
  :doc:`../concepts/results-and-postprocessing`.
- The formulation behind the results: :doc:`HowItWorks`, then the Concepts pages.
