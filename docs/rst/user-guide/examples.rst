Examples
========

The repository ships two kinds of example cases: two small cases inside the package, and the
case studies in the ``data/`` folder that the tests and the papers use. Each case is a folder
of CSV files (or one ``.duckdb`` file) named after the case; see :doc:`data-and-io`.

Cases in the package
--------------------

These two cases are installed with the package, in ``src/el1xr_opt/``. Both have 8736 hourly
load levels and one electricity retailer.

.. list-table::
   :widths: 15 85
   :header-rows: 1

   * - Case
     - Content
   * - ``Home1``
     - Two nodes, joined by two electricity lines and one hydrogen pipe. One electricity unit
       (``EV_01``), one electricity demand (``EleD_01``), an electrolyser (``AEL_01``) and a
       hydrogen store (``PEMEL_01``) with one hydrogen demand (``HydD1``). It is the case the
       command line runs by default. A copy is in ``data/Home1``.
   * - ``Grid1``
     - Home1 with a third node on a third line. Three electricity units (``EV_01``,
       ``BESS_02``, ``Solar_02``), two electricity demands, the same electrolyser and hydrogen
       store, and one hydrogen demand.

Case studies in ``data/``
-------------------------

.. list-table::
   :widths: 25 75
   :header-rows: 1

   * - Folder
     - Content
   * - ``data/H2VPP/Home1``
     - A small hydrogen virtual-power-plant case: ten EVs, a battery, ten solar units, an
       electrolyser and a hydrogen store, with candidate units for sizing. It solves in about
       one second, and many solve tests use it. See ``data/H2VPP/README.md``.
   * - ``data/sizing``
     - Small variants of H2VPP (battery sizing, electrolyser, hydrogen tank, compressor,
       tariff and FCR on or off), written by ``make_sizing_cases.py`` and used by the test
       suite. See ``data/sizing/README.md``.
   * - ``data/EEM26``
     - The base microgrid of the EEM26 study, with the scripts that create and run its cases.
   * - ``data/H2VPPFCR``
     - The wind, battery, electrolyser and tank plant of the hydrogen-VPP FCR paper, in SE3
       with 2025 prices. ``build_case.py`` writes the case and ``run_year.py`` solves it. See
       ``data/H2VPPFCR/README.md``.

Running an example
------------------

Run a case by its folder and name. ``--dir`` is the folder that holds the case folder::

    el1xr-run --dir src/el1xr_opt --case Home1 --solver highs
    el1xr-run --dir src/el1xr_opt --case Grid1 --solver highs
    el1xr-run --dir data/H2VPP --case Home1 --solver highs

The results are written to ``results.duckdb`` in the case folder; see
:doc:`../concepts/results-and-postprocessing`. The same runs from Python are shown in
:doc:`../getting-started/Quickstart`.
