"""el1xr_opt input schema — the naming rules shared by every input backend.

A case is a set of CSV files (or one ``.duckdb`` file) that follow two simple
naming rules:

  * ``oM_Dict_<Stem>_<Case>.csv``  — a dimension list. One column is a plain set
    (e.g. the list of periods); two or more columns are a relation / membership
    table (e.g. node-to-zone).
  * ``oM_Data_<Stem>_<Case>.csv``  — a data table. The first one or more columns
    are an unnamed index (period, scenario, load level, or an entity name) and
    the remaining columns carry the values.

The DuckDB backend stores each table with the same values but needs to remember
which leading columns were the (unnamed) index. It does that by renaming those
columns to a reserved prefix, ``__idx0``, ``__idx1``, ... . On read, any column
with that prefix is moved back into the index and its name is cleared again, so
the DataFrame is identical to the one the CSV backend produces.

Because the index handling is generic, a new data table — including the heat
sector tables listed below — is picked up automatically with no schema change.
Adding a new *set* still needs one line in ``set_definitions`` inside
``oM_InputData.data_processing`` (that map is model-specific and stays there).
"""
from __future__ import annotations

# File-name building blocks.
DICT_PREFIX = "oM_Dict_"
DATA_PREFIX = "oM_Data_"

# Reserved column prefix used by the DuckDB backend to carry the unnamed index
# levels of a data table. Chosen so it never clashes with a real entity name.
IDX_PREFIX = "__idx"

# Single-row data tables. They have one unnamed index row label ("Options" /
# "Parameter") and one column per indicator; downstream code reads them by
# column with ``.iloc[0]``. Listed here for documentation and for the converter.
SINGLE_ROW_DATA_STEMS = ("Option", "Parameter")

# Name and keys of the metadata table written into every ``.duckdb`` file.
META_TABLE = "oM_schema_metadata"
META_KEY_CASE = "source_case"

# DuckDB table-name prefixes (kept distinct so dict and data tables never
# collide, and so the metadata table is easy to skip when listing).
DB_DICT_PREFIX = "dict_"
DB_DATA_PREFIX = "data_"

# ---------------------------------------------------------------------------
# Heat sector (scaffolding). The model today covers electricity and hydrogen.
# These are the dict/data stems a heat-bearing case is expected to carry, by
# analogy with the electricity and hydrogen sectors. They load through the
# generic backends with no further change; the formulation that consumes them
# lives in oM_HeatSector (scaffold). Verify the exact column names against a
# real heat case before relying on them.
# ---------------------------------------------------------------------------
HEAT_DICT_STEMS = ("HeatGeneration", "HeatDemand", "HeatRetail")
HEAT_DATA_STEMS = (
    "HeatGeneration", "HeatDemand", "HeatRetail", "HeatNetwork",
    "VarMaxHeatDemand", "VarMinHeatDemand",
)


def dict_filename(stem: str, case: str) -> str:
    """CSV file name for a dimension dict."""
    return f"{DICT_PREFIX}{stem}_{case}.csv"


def data_filename(stem: str, case: str) -> str:
    """CSV file name for a data table."""
    return f"{DATA_PREFIX}{stem}_{case}.csv"


def idx_name(level: int) -> str:
    """Reserved DuckDB column name for index level ``level``."""
    return f"{IDX_PREFIX}{level}"


def is_idx_col(col: object) -> bool:
    """True if ``col`` is a reserved index column written by the converter."""
    return isinstance(col, str) and col.startswith(IDX_PREFIX)
