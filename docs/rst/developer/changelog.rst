.. _changelog:

Changelog
=========

All notable changes to this project will be documented in this file.

The format is based on `Keep a Changelog <https://keepachangelog.com/en/1.0.0/>`_,
and this project adheres to `Semantic Versioning <https://semver.org/spec/v2.0.0.html>`_.

Unreleased
----------

### Added

- Feature catalogue and problem-class logic (``oM_Features.py``, architecture Stages A and B). One place that (i) lists the optional features and their option flags with safe defaults — so a case whose Option file predates a flag still runs instead of raising ``KeyError`` (``apply_flag_defaults``, replacing the scattered per-flag defaults); (ii) detects the model's mathematical class (LP / MILP / QP / MIQP / SOCP / MISOCP / NLP) from the built model and checks the chosen solver can handle it, logging which solvers and model-building libraries support that class (the capability matrices from the framework study); and (iii) provides a cost/revenue registry so a new cost-bearing feature registers its term (``register_cost`` / ``register_revenue``) instead of editing the objective-aggregation rules. The objective aggregation now sums the registry, seeded with the built-in terms in their original order, so existing results are unchanged. The problem class is the lever for choosing both the solver and (for a future migration) the build library: e.g. a MISOCP case rules out HiGHS and linopy. Tested by ``tests/test_features.py`` and ``tests/test_problem_class.py``.
- AC optimal power flow module (``oM_ACOPF.py``, Phase 5a). A standalone, single-phase analysis that runs on a network snapshot (the case's electricity-network branches plus nodal injections), decoupled from the main solve so it stays tractable. Two formulations: the second-order-cone (branch-flow / DistFlow) relaxation, solved with Gurobi and reporting the relaxation gap, and the exact polar NLP, solved with Ipopt and warm-started from the SOC solution. Validated against the IEEE 33-bus feeder (Baran & Wu): both reproduce the published base-case loss (~202.7 kW) and minimum voltage (~0.913 pu), and agree to 0.001 kW. Results (per-bus voltages and a summary) can be written to a DuckDB file. See ``tests/test_acopf.py`` and ``docs/scope_acopf_community.md``.
- AC OPF multi-snapshot sweep (``oM_ACOPF.run_acopf_sweep``, Phase 5b). Runs one AC OPF per snapshot and summarises voltage/loss violations across a horizon, writing the summary to DuckDB (``oM_Result_ACOPF_Sweep``); ``scaled_snapshots`` builds a load-profile set and ``snapshots_from_case`` pulls per-node demand from a case. On the IEEE 33-bus feeder over a 0.5x-1.3x load profile, losses rise and minimum voltage falls monotonically with load and the base snapshot matches the Phase-5a benchmark.
- Energy-community / virtual-sharing layer (``oM_Community.py``, Phase 6a). Retailers (members) in the same zone can share locally generated electricity before importing from or exporting to the grid, which avoids the retail buy/sell spread and lowers total community cost. It adds two per-member variables (``vEleShareIn``, ``vEleShareOut``), a per-zone pool-conservation constraint, and the matching terms in the retail balance. Enabled with the option flag ``IndBinCommunity``; off by default, so existing cases are unchanged (the four validation cases keep their exact costs). Validated by ``tests/test_community.py``, which builds a two-member community and checks that sharing is used and total cost does not increase.
- Green-hydrogen layer in ``oM_GreenHydrogen.py``: an optional hourly temporal-matching (RFNBO additionality) constraint that caps electrolyser electricity use by the available renewable generation (own units plus PPA-contracted units), enabled with the ``pParGreenH2Matching`` option; and electricity PPA settlement that defines the previously zeroed ``vTotalEleMrkPPACost`` for renewable units flagged ``pEleGenPPA``. Off by default, so existing cases are unchanged.
- Investment (capacity-sizing) layer in ``oM_Investment.py``: build-decision variables for candidate generators and storage, capacity-coupling constraints, and an investment-cost term in the objective. The investment cost is scaled by ``factor1`` (the MWh/kWh unit knob) like the capacities and per-energy operating costs, and weighted by the period discount factors, so it stays on the same unit and discounted footing as operation when switching between utility and home scales. The capacity-expansion formulation follows the openTEPES model (Ramos, Alvarez, and Lumbreras, *openTEPES: Open-source Transmission and Generation Expansion Planning*, SoftwareX 18, 2022, `doi:10.1016/j.softx.2022.101070 <https://doi.org/10.1016/j.softx.2022.101070>`_). For a sizing study the modeled load levels should represent a full year (via period weights and durations) so the annualized investment trades off against a full year of operation. The electrolyser electricity-input sizing is still pending review.
- Small hydrogen-VPP test case in ``data/H2VPP`` (24 load levels) that solve-tests the investment and green-hydrogen layers; solves in about one second. See ``data/H2VPP/README.md``.
- DuckDB input support. A case can now be read from a single ``<case>.duckdb`` file as well as from a CSV folder. The two backends (``oM_InputCSVSource``, ``oM_InputDuckDBSource``) share one interface (``oM_InputSource``: the ``InputSource`` base class, the ``open_source`` / ``resolve_source`` factory, and small shape helpers) and return identical DataFrames, so a DuckDB run reproduces a CSV run exactly. ``oM_InputData`` now reads through this interface instead of reading CSVs directly.
- ``oM_CsvToDuckDB`` converter and the ``el1xr-csv2duckdb`` command, which turns a CSV case folder into a ``<case>.duckdb`` file. The naming rules and the reserved ``__idx`` index columns it uses are described in ``oM_InputSchema``.
- DuckDB results are now written by default to ``<case>/results.duckdb`` (one table per set, parameter, variable and constraint dual, plus a ``oM_Result_RunMetadata`` headline table with the case, date, solver, objective and version). Controlled by the new ``--duckdbresults`` flag (default on); CSV results stay available via ``--rawresults``.
- Heat-sector scaffold (``oM_HeatSector``) and heat input stems in ``oM_InputSchema``. The architecture is now heat-ready (home/residential and district heating); the formulation itself is not built yet and is not called from the solve pipeline.
- Architecture diagram (``docs/img/el1xr_opt_architecture.svg``) and a new Architecture section in the README, plus a note on computational efficiency in ``docs/computational_efficiency.md``.
- Small variant validation cases generated from the H2VPP base by ``data/sizing/make_sizing_cases.py``: home and neighbourhood battery sizing, a power-tariff on/off pair, and frequency-market variants (FCR-D only, FCR-N only, both, none). They are short LP cases (reproducible cost), read as ``.duckdb`` input, and rebuilt by the test fixture rather than committed, so only the generator and its README are tracked. Two hydrogen cases (H2 tank, electrolyser) are included as feasibility cases; they do not yet size anything because the base case does not link the electrolyser as an electricity-to-hydrogen converter. See ``data/sizing/README.md``.

### Changed

- Continuous integration reworked into two tiers (``.github/workflows/ci.yml``), replacing the single ``conda-build.yml`` job. A fast tier lints and runs the no-solve tests on Linux, macOS and Windows for Python 3.11, 3.12 and 3.13; a solve tier runs the validation cases on the three operating systems for Python 3.12. Validation now covers four cases (Home1, Grid1, EEM26, H2VPP), each solved from both its CSV folder and its ``.duckdb`` file and checked against a golden cost.
- CI validation cases are solved over one week of operation (168 load levels) instead of a month. One week is enough to exercise the model in tests, and it cuts the full test-suite run from about six minutes to two. Full-year "proper" runs are meant for a larger machine, not CI.

### Fixed

- Corrected the ``model.psnesc`` index set in ``oM_InputData.py`` (it used ``model.psc`` instead of ``model.psn``, so it produced 3-tuples that could not be unpacked). The set is built only when investment candidates exist, so the error surfaced the first time a case included a candidate unit.
- Import the output modules (``oM_OutputData``, ``oM_OutputData_duckdb``) lazily inside ``routine`` instead of at the top of ``oM_Sequence``. This keeps the heavy plotting libraries out of the package import path, so the documentation build can import the package and generate the API reference without them, and it removes an import cycle that broke the docs build on Python 3.11.
- Build the ordered load-level list once in ``create_constraints`` instead of rebuilding it on every constraint-rule call. The slicing is identical, so results are unchanged; this removes a quadratic-scaling cost that showed up on cases with long storage cycles or long minimum up/down times.
- The solve tests back up and restore the ``Duration`` input file byte for byte, so running the test suite no longer leaves the tracked CSV cases reformatted.
- The DuckDB read and write paths use DuckDB's relational API (``connection.table(...)`` and ``from_df(...).create(...)``) instead of building SQL strings with table names, so no identifier is ever interpolated into a query. This removes the static-analysis "possible SQL injection" warnings and is the safer pattern. Removed the small-file ``block_size`` option (it only mattered for committing case files, which are now generated on the fly).
- Fixed the electricity-to-hydrogen (``e2h``) path, which had never run because no shipped case had an active hydrogen generator. Defined the missing ``model.hgr`` set (the hydrogen analogue of the electricity RES set ``egr``, empty since there is no hydrogen RES column) so the initial-output loop no longer raises ``AttributeError``; and guarded two electricity-storage code paths (variable inflow/outflow/inventory bounds in ``oM_InputData`` and the ``eEleTotalMaxChargeConditioned`` constraint in ``oM_ModelFormulation``) so electrolysers, which also consume electricity, are no longer treated as storage. With these fixes a case with an electrolyser builds and solves, and hydrogen storage can be sized.

[1.0.13] - 2025-11-13
---------------------

### Added
- `.gitignore` file to exclude Sphinx build artifacts.
- Detailed documentation on Pyomo model and CSV file naming conventions.
- Reusable helper functions in `oM_OutputData.py` for CSV export and plotting operations:

  - `save_to_csv()` function for consistent CSV export operations.
  - Plotting functions: `create_line_chart()`, `create_bar_chart()`, and `save_chart()`.
  - `create_and_save_duration_curve()` helper function for duration curves.
  - CSV writing functions: `_write_variable_to_csv()`, `_write_parameter_to_csv()`, `_write_constraint_to_csv()`.

### Changed
- Enhanced the developer `contributing.rst` guide with detailed setup and workflow instructions.
- Expanded the `coding-style.rst` guide with examples for formatting, docstrings, and type hints.
- Improved the `testing.rst` guide with clearer instructions and information on the CI pipeline.
- Restructured the changelog to follow the "Keep a Changelog" format.
- Refactored `oM_OutputData.py` to improve code organization and reduce duplication:

  - Replaced repetitive code blocks with reusable function calls.
  - Maintained backward compatibility with existing output files.

### Fixed
- Fixed dangerous default mutable argument in `save_chart()` function by changing default from `{}` to `None`.

[1.0.9] - 2024-09-15
--------------------
- Initial release of the project and documentation.