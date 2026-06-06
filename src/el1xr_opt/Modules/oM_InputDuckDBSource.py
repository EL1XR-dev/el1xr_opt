"""el1xr_opt DuckDB backend — reads a single ``<case>.duckdb`` file.

The file is produced by ``oM_CsvToDuckDB`` and holds one table per input
table plus a small metadata table. Data tables store their (originally unnamed)
index levels in reserved ``__idx0``, ``__idx1``, ... columns; on read those
columns are moved back into a nameless index so the DataFrame matches what the
CSV backend returns.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from .oM_InputSchema import (
    DB_DATA_PREFIX,
    DB_DICT_PREFIX,
    IDX_PREFIX,
    META_KEY_CASE,
    META_TABLE,
    is_idx_col,
)
from .oM_InputSource import InputSource, finalize_data_index

try:
    import duckdb  # noqa: F401
    _HAS_DUCKDB = True
except ImportError:  # pragma: no cover - exercised only in duckdb-free trees
    _HAS_DUCKDB = False


class DuckDBSource(InputSource):
    def __init__(self, db_path) -> None:
        import duckdb
        self.db_path = Path(db_path)
        self._con = duckdb.connect(str(self.db_path), read_only=True)
        row = self._con.execute(
            f'SELECT "Value" FROM "{META_TABLE}" WHERE "Key" = ?', [META_KEY_CASE]
        ).fetchone()
        if not row or not row[0]:
            raise ValueError(
                f"{self.db_path}: metadata table '{META_TABLE}' has no '{META_KEY_CASE}'"
            )
        self.case_name = str(row[0])
        names = self._con.execute(
            "SELECT table_name FROM information_schema.tables"
        ).fetchall()
        self._tables = {r[0] for r in names}

    @property
    def dir_name(self) -> str:
        return str(self.db_path.parent)

    def close(self) -> None:
        if self._con is not None:
            self._con.close()
            self._con = None

    def list_data_stems(self) -> set:
        return {
            t[len(DB_DATA_PREFIX):]
            for t in self._tables
            if t.startswith(DB_DATA_PREFIX)
        }

    def read_dict(self, stem: str) -> pd.DataFrame:
        table = f"{DB_DICT_PREFIX}{stem}"
        if table not in self._tables:
            return pd.DataFrame()
        return self._con.execute(f'SELECT * FROM "{table}"').df()

    def read_data(self, stem: str) -> pd.DataFrame:
        table = f"{DB_DATA_PREFIX}{stem}"
        if table not in self._tables:
            raise FileNotFoundError(f"oM_Data_{stem}_*.csv not present in {self.db_path}")
        df = self._con.execute(f'SELECT * FROM "{table}"').df()
        idx_cols = sorted(
            (c for c in df.columns if is_idx_col(c)),
            key=lambda c: int(c[len(IDX_PREFIX):]),
        )
        return finalize_data_index(df, idx_cols)
