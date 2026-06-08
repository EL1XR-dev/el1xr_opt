Quickstart
==========

Run a case from the command line
--------------------------------

The console script ``el1xr-run`` (installed with the package) is the simplest way to
run a case::

    el1xr-run --case Home1 --solver highs

Run with everything spelled out (equivalently ``python -m el1xr_opt``)::

    el1xr-run --dir data --case Home1 --solver highs --date "2025-09-30 20:26:00" \
              --rawresults False --plots False --duckdbresults True

**Arguments** (boolean flags take the strings ``True`` / ``False``):

- ``--dir`` -- parent directory holding the case folder (default ``data``).
- ``--case`` -- case name (default ``Home1``).
- ``--solver`` -- ``highs`` (default), ``gurobi``, ``cbc``, ``cplex`` or ``ipopt``.
- ``--date`` -- run date ``"YYYY-MM-DD HH:MM:SS"`` (default: now).
- ``--rawresults`` -- also write the CSV result tables (default ``False``).
- ``--plots`` -- generate plots (default ``False``).
- ``--duckdbresults`` -- write results to ``results.duckdb`` (default ``True``).
- ``--indlog`` -- per-step timing log (default ``False``).

If you run ``el1xr-run`` with no arguments it prompts for them interactively. Results
are written to ``<dir>/<case>/results.duckdb`` by default; see
:doc:`../user-guide/data-and-io`.

Run a case from Python
----------------------

::

    from el1xr_opt.Modules.oM_Sequence import routine
    from el1xr_opt.Modules.oM_LoadCase import load_case

    data = load_case(case="Home1")
    data["rawresults"] = "True"          # boolean options are the strings "True"/"False"
    model = routine(**data)

``load_case`` builds the argument dictionary (with the same defaults as the CLI) and
``routine`` builds and solves the model and returns it. The boolean options
(``rawresults``, ``plots``, ``duckdbresults``, ``indlog``) are compared as the strings
``"True"`` / ``"False"``, so set them as strings if you override them.
