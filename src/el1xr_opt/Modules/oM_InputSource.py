"""el1xr_opt input source — the ``InputSource`` interface and ``open_source`` factory.

The model reads its input through one of two backends:

  * ``CSVSource``    — a directory of ``oM_Dict_*`` / ``oM_Data_*`` CSV files
                       (the historical layout).
  * ``DuckDBSource`` — a single ``<case>.duckdb`` file holding the same tables.

``open_source(path)`` looks at the path and returns the right backend: a
directory gives a ``CSVSource``, a ``.duckdb`` file gives a ``DuckDBSource``.
Both backends return identical DataFrames, so the rest of the model does not
know or care which one was used.

The duckdb backend is imported lazily, so a checkout without ``duckdb``
installed can still build the CSV path.
"""
from __future__ import annotations

import abc
import os
from pathlib import Path

import pandas as pd


class InputSource(abc.ABC):
    """Abstract input source. Implementations: ``CSVSource``, ``DuckDBSource``."""

    case_name: str

    @abc.abstractmethod
    def list_data_stems(self) -> set:
        """Stems of the data tables present (no ``oM_Data_`` prefix, no ``_<case>.csv`` suffix)."""

    @abc.abstractmethod
    def read_dict(self, stem: str) -> pd.DataFrame:
        """Return the dimension dict for ``stem`` as a plain DataFrame (no index).

        Returns an empty DataFrame if the dict is absent.
        """

    @abc.abstractmethod
    def read_data(self, stem: str) -> pd.DataFrame:
        """Return a data table with its leading unnamed columns set as a nameless index.

        This is the exact shape ``oM_InputData`` expects: the same DataFrame the
        old ``pd.read_csv`` + ``set_index(unnamed columns)`` code produced.
        Raises ``FileNotFoundError`` if the stem is absent.
        """

    def close(self) -> None:  # default no-op
        pass

    def __enter__(self) -> "InputSource":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


def open_source(path: str | os.PathLike) -> InputSource:
    """Return a ``CSVSource`` for a directory or a ``DuckDBSource`` for a ``.duckdb`` file."""
    p = Path(path).expanduser()
    if p.is_dir():
        from .oM_InputCSVSource import CSVSource  # lazy: keeps duckdb-free trees importing this module
        return CSVSource(p)
    if p.is_file() and p.suffix == ".duckdb":
        from .oM_InputDuckDBSource import DuckDBSource, _HAS_DUCKDB
        if not _HAS_DUCKDB:
            raise ImportError("duckdb is required to read a .duckdb input; install it with `pip install duckdb`")
        return DuckDBSource(p)
    raise ValueError(f"{p}: not a CSV case directory or a .duckdb file")


def resolve_source(dir_name: str | os.PathLike, case_name: str) -> InputSource:
    """Pick the input for ``(dir_name, case_name)``.

    Prefers the CSV case folder ``<dir_name>/<case_name>`` when it holds the
    case's ``oM_Data_Parameter`` file (so CSV stays the default whenever a real
    case folder is present), otherwise falls back to the DuckDB file
    ``<dir_name>/<case_name>.duckdb``. Checking for the Parameter file rather
    than just the folder means an empty results folder of the same name does not
    shadow a ``.duckdb`` input.
    """
    from .oM_InputSchema import data_filename

    case_dir = os.path.join(dir_name, case_name)
    if os.path.isfile(os.path.join(case_dir, data_filename("Parameter", case_name))):
        return open_source(case_dir)
    db_path = os.path.join(dir_name, f"{case_name}.duckdb")
    if os.path.isfile(db_path):
        return open_source(db_path)
    raise FileNotFoundError(
        f"no CSV case folder with data at '{case_dir}' and no DuckDB file '{db_path}'"
    )


def finalize_data_index(df: pd.DataFrame, idx_cols: list) -> pd.DataFrame:
    """Move ``idx_cols`` into the index and clear their names (the model expects a nameless index)."""
    if idx_cols:
        df = df.set_index(idx_cols)
        df.index.names = [None] * len(idx_cols)
    return df


def df_to_set_values(df: pd.DataFrame) -> list:
    """Convert a dict DataFrame into the values a Pyomo ``Set(initialize=...)`` accepts.

      * one column   -> ``[v1, v2, ...]``
      * two+ columns -> ``[(a, b, ...), ...]`` (relation / membership)
    """
    if df.shape[1] == 0:
        return []
    if df.shape[1] == 1:
        return df.iloc[:, 0].tolist()
    return [tuple(row) for row in df.itertuples(index=False, name=None)]
