.. _testing:

Testing
=======

Running the tests is a crucial step to ensure your changes work and have not introduced
regressions. The suite lives under ``tests/`` and is run with ``pytest``.

Two test tiers
--------------

Tests are split with a pytest marker:

- **Fast tier** -- import, data-reading and formulation tests that need **no solver**.
  Run them with::

     pytest -m "not solve" tests/

- **Solve tier** -- tests that build and solve a model, so they need an LP/MIP solver
  (HiGHS is enough). They take longer (minutes). Run them with::

     pytest -m solve --timeout=1800 tests/

Run the whole suite (fast + solve) with ``pytest tests/``.

What the suite covers
---------------------

There are many test files, not one. Highlights:

- ``test_run.py`` -- the golden validation cases (Home1, Grid1, EEM26, H2VPP) plus the
  small sizing / tariff / frequency-market variant cases. Each case is solved twice --
  once from its CSV folder and once from a generated ``.duckdb`` file -- so the two
  input paths are proven to give the same cost. The two hydrogen sizing cases are
  marked ``xfail`` (see the model notes).
- ``test_data_sources.py`` -- CSV vs DuckDB read parity (fast tier).
- ``test_heat_sector.py``, ``test_community.py``, ``test_features.py``,
  ``test_problem_class.py`` -- the heat, community and feature/problem-class layers.
- ``test_benders*.py`` -- the Benders decomposition (generic, el1xr, temporal),
  validated against the monolith.
- ``test_acopf.py``, ``test_lindist3flow.py`` -- the network-analysis modules (the AC
  OPF tests need Gurobi/Ipopt and skip otherwise).
- ``test_formulation_fixes.py`` -- regression guards for the audited formulation fixes.

Adding new tests
----------------

Add a test with each new feature or bug fix. Mark a test ``@pytest.mark.solve`` if it
builds and solves a model; leave it unmarked if it does not need a solver, so it runs in
the fast tier. New tests can go in an existing file or a new ``tests/test_*.py``.

Checking the docs locally
-------------------------

The documentation build treats warnings as errors (``-W``), and the API pages are
generated from the source docstrings, so a malformed docstring -- an indented block
that is not a literal block, a bad cross-reference -- fails the build. Build it the
same way CI does to catch that before you push::

   python -m sphinx -b html -W --keep-going docs/rst /tmp/el1xr-docs

A tip when writing docstrings: an indented "name -- description" block needs to be a
reStructuredText literal block (end the line before it with ``::``) or a proper list,
otherwise docutils reports "Unexpected indentation" and the build fails.

Pre-push hook
-------------

A hook under ``.githooks/`` runs the fast CI gate -- the flake8 syntax check and the
strict docs build -- before each push, so a syntax error or a broken docstring is
caught locally instead of in CI. Enable it once per clone::

   git config core.hooksPath .githooks

It uses the project virtualenv (``.venv``) if present. Skip it for a single push with
``git push --no-verify``.

Continuous integration
----------------------

GitHub Actions runs two jobs on every pull request (``.github/workflows/ci.yml``):

- **fast** -- a flake8 syntax check (``--select=E9,F63,F7,F82``) and the fast tier
  (``pytest -m "not solve"``), across Linux/macOS/Windows and Python 3.11/3.12/3.13.
- **solve** -- the solve tier on the four validation cases, each from CSV and DuckDB,
  checked against stored golden costs, on the three OSes at Python 3.12.

A separate workflow builds the documentation with warnings treated as errors, so a
broken cross-reference or a stale API entry fails the build.
