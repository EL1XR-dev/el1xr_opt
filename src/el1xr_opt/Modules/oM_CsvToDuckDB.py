"""Convert a CSV case folder into a single ``<case>.duckdb`` file.

The DuckDB file holds the same tables as the CSV folder and can be fed to the
model in place of the folder. Use it from the command line:

    el1xr-csv2duckdb --dir data/EEM26 --case Home1

which writes ``data/EEM26/Home1.duckdb``. Reading it back through the model
produces the same results as reading the CSV folder.
"""
from __future__ import annotations

import argparse
import os

import pandas as pd

from .oM_InputCSVSource import CSVSource
from .oM_InputSchema import (
    DB_DATA_PREFIX,
    DB_DICT_PREFIX,
    META_KEY_CASE,
    META_TABLE,
    idx_name,
)


def _write_table(con, name: str, df: pd.DataFrame) -> None:
    con.register("_tmp_df", df)
    con.execute(f'CREATE TABLE "{name}" AS SELECT * FROM _tmp_df')
    con.unregister("_tmp_df")


def _flatten_data(df: pd.DataFrame) -> pd.DataFrame:
    """Turn the nameless index into ``__idx0``, ``__idx1``, ... value columns."""
    n = df.index.nlevels
    flat = df.reset_index()
    rename = {flat.columns[i]: idx_name(i) for i in range(n)}
    return flat.rename(columns=rename)


def csv_case_to_duckdb(dir_name: str, case_name: str, db_path: str | None = None,
                       overwrite: bool = True, block_size: int | None = None) -> str:
    """Write ``<dir_name>/<case_name>.duckdb`` from the CSV case folder. Returns the path.

    ``block_size`` (e.g. 16384, the DuckDB minimum) sets the storage block size.
    Small cases waste a lot of space at the default 256 KB block size because
    every table reserves at least one block; a small block size keeps a committed
    case file small. Leave it as ``None`` for the default.
    """
    import duckdb

    src = CSVSource(os.path.join(dir_name, case_name))
    if db_path is None:
        db_path = os.path.join(dir_name, f"{case_name}.duckdb")
    if os.path.exists(db_path):
        if not overwrite:
            raise FileExistsError(db_path)
        os.remove(db_path)

    if block_size is not None:
        con = duckdb.connect()
        con.execute(f"ATTACH '{db_path}' AS _out (BLOCK_SIZE {int(block_size)})")
        con.execute("USE _out")
    else:
        con = duckdb.connect(db_path)
    try:
        con.execute(f'CREATE TABLE "{META_TABLE}" ("Key" VARCHAR, "Value" VARCHAR)')
        con.execute(f'INSERT INTO "{META_TABLE}" VALUES (?, ?)', [META_KEY_CASE, case_name])

        for stem in sorted(src.list_dict_stems()):
            _write_table(con, f"{DB_DICT_PREFIX}{stem}", src.read_dict(stem))

        for stem in sorted(src.list_data_stems()):
            _write_table(con, f"{DB_DATA_PREFIX}{stem}", _flatten_data(src.read_data(stem)))
        con.execute("CHECKPOINT")
    finally:
        con.close()
    return db_path


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description="Convert a CSV case folder to a .duckdb file.")
    parser.add_argument("--dir", required=True, help="Parent directory holding the case folder.")
    parser.add_argument("--case", required=True, help="Case name (the folder inside --dir).")
    parser.add_argument("--out", default=None, help="Output .duckdb path (default: <dir>/<case>.duckdb).")
    args = parser.parse_args(argv)
    path = csv_case_to_duckdb(args.dir, args.case, db_path=args.out)
    print(f"Wrote {path}")


if __name__ == "__main__":
    main()
