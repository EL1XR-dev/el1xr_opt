Quickstart
==========

From the command line
---------------------

The console script ``el1xr-run`` (installed with the package) runs a case. This runs the
``Home1`` case that ships with the package::

    el1xr-run --dir "" --case Home1 --solver highs --date "" --rawresults False --plots False

Run a case in another folder, here the copy in the repository's ``data`` folder (equivalently
``python -m el1xr_opt``)::

    el1xr-run --dir data --case Home1 --solver highs --date "2025-09-30 20:26:00" \
              --rawresults False --plots False --duckdbresults True

**Arguments** (the yes-or-no options take the strings ``True`` / ``False``):

- ``--dir``: parent directory holding the case folder (default: the package folder, which
  holds the ``Home1`` and ``Grid1`` cases).
- ``--case``: case name (default ``Home1``).
- ``--solver``: ``highs`` (default), ``gurobi``, ``cbc``, ``cplex`` or ``ipopt``.
- ``--date``: run date ``"YYYY-MM-DD HH:MM:SS"`` (default: now).
- ``--rawresults``: also write the CSV result tables (default ``False``).
- ``--plots``: generate plots (default ``False``).
- ``--duckdbresults``: write results to ``results.duckdb`` (default ``True``).
- ``--indlog``: per-step timing log (default ``True``).

An argument from ``--dir`` to ``--plots`` that is left out is asked for interactively;
pressing Enter takes the default. An empty value, such as ``--dir ""``, takes the default
without asking. ``el1xr-run`` exits with code 0 when the run finishes and 1 when it fails.
Results are written to ``<dir>/<case>/results.duckdb`` by default; see
:doc:`../user-guide/data-and-io`.

From Python
-----------

::

    from el1xr_opt.Modules.oM_Sequence import routine
    from el1xr_opt.Modules.oM_LoadCase import load_case

    data = load_case(case="Home1")
    data["rawresults"] = "True"          # boolean options are the strings "True"/"False"
    model = routine(**data)

``load_case`` builds the argument dictionary (its default case is ``Grid1``, and a date is
given as ``"YYYY-MM-DD HH:MM"``) and
``routine`` builds and solves the model and returns it. The yes-or-no options
(``rawresults``, ``plots``, ``duckdbresults``, ``indlog``) are compared as the strings
``"True"`` / ``"False"``, so they are set as strings when overridden.
