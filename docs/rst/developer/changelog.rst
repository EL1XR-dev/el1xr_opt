.. _changelog:

Changelog
=========

All notable changes to this project will be documented in this file.

The format is based on `Keep a Changelog <https://keepachangelog.com/en/1.0.0/>`_,
and this project adheres to `Semantic Versioning <https://semver.org/spec/v2.0.0.html>`_.

Unreleased
----------

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