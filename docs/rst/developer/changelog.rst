.. _changelog:

Changelog
=========

All notable changes to this project will be documented in this file.

The format is based on `Keep a Changelog <https://keepachangelog.com/en/1.0.0/>`_,
and this project adheres to `Semantic Versioning <https://semver.org/spec/v2.0.0.html>`_.

Unreleased
----------

### Added

- Green-hydrogen layer in ``oM_GreenHydrogen.py``: an optional hourly temporal-matching (RFNBO additionality) constraint that caps electrolyser electricity use by the available renewable generation (own units plus PPA-contracted units), enabled with the ``pParGreenH2Matching`` option; and electricity PPA settlement that defines the previously zeroed ``vTotalEleMrkPPACost`` for renewable units flagged ``pEleGenPPA``. Off by default, so existing cases are unchanged.
- Investment (capacity-sizing) layer in ``oM_Investment.py``: build-decision variables for candidate generators and storage, capacity-coupling constraints, and an investment-cost term in the objective. The investment cost is scaled by ``factor1`` (the MWh/kWh unit knob) like the capacities and per-energy operating costs, and weighted by the period discount factors, so it stays on the same unit and discounted footing as operation when switching between utility and home scales. The capacity-expansion formulation follows the openTEPES model (Ramos, Alvarez, and Lumbreras, *openTEPES: Open-source Transmission and Generation Expansion Planning*, SoftwareX 18, 2022, `doi:10.1016/j.softx.2022.101070 <https://doi.org/10.1016/j.softx.2022.101070>`_). For a sizing study the modeled load levels should represent a full year (via period weights and durations) so the annualized investment trades off against a full year of operation. The electrolyser electricity-input sizing is still pending review.
- Small hydrogen-VPP test case in ``data/H2VPP`` (24 load levels) that solve-tests the investment and green-hydrogen layers; solves in about one second. See ``data/H2VPP/README.md``.

### Fixed

- Corrected the ``model.psnesc`` index set in ``oM_InputData.py`` (it used ``model.psc`` instead of ``model.psn``, so it produced 3-tuples that could not be unpacked). The set is built only when investment candidates exist, so the error surfaced the first time a case included a candidate unit.
- Import the output modules (``oM_OutputData``, ``oM_OutputData_duckdb``) lazily inside ``routine`` instead of at the top of ``oM_Sequence``. This keeps the heavy plotting libraries out of the package import path, so the documentation build can import the package and generate the API reference without them, and it removes an import cycle that broke the docs build on Python 3.11.

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