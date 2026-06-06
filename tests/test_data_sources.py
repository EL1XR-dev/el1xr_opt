"""Fast, no-solve tests for the CSV / DuckDB input backends.

These never build or solve a Pyomo model, so they run on every OS and Python
version in CI. They check that:

  * ``open_source`` / ``resolve_source`` pick the right backend, and
  * a case read through DuckDB is identical, table by table, to the same case
    read through CSV (this is what guarantees a DuckDB run matches a CSV run).
"""
import os

import pandas as pd
import pytest

from el1xr_opt.Modules.oM_InputCSVSource import CSVSource
from el1xr_opt.Modules.oM_InputDuckDBSource import DuckDBSource
from el1xr_opt.Modules.oM_InputSource import open_source, resolve_source, df_to_set_values
from el1xr_opt.Modules.oM_CsvToDuckDB import csv_case_to_duckdb

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# (label, parent dir, case name) for every real validation case.
CASES = [
    ("home1", os.path.join(REPO, "src", "el1xr_opt"), "Home1"),
    ("grid1", os.path.join(REPO, "src", "el1xr_opt"), "Grid1"),
    ("eem26", os.path.join(REPO, "data", "EEM26"),    "Home1"),
    ("h2vpp", os.path.join(REPO, "data", "H2VPP"),    "Home1"),
]
CASE_IDS = [c[0] for c in CASES]


@pytest.fixture(scope="module")
def converted(tmp_path_factory):
    """Convert every case to a .duckdb file once for the whole module."""
    out = {}
    for label, d, case in CASES:
        db = csv_case_to_duckdb(d, case, db_path=str(tmp_path_factory.mktemp(label) / f"{case}.duckdb"))
        out[label] = (d, case, db)
    return out


@pytest.mark.parametrize("label,d,case", CASES, ids=CASE_IDS)
def test_read_parity(label, d, case, converted):
    """Every dict and data table reads identically from CSV and from DuckDB."""
    _, _, db = converted[label]
    csv = CSVSource(os.path.join(d, case))
    dbs = DuckDBSource(db)
    try:
        assert csv.list_data_stems() == dbs.list_data_stems()
        for stem in sorted(csv.list_dict_stems()):
            pd.testing.assert_frame_equal(
                csv.read_dict(stem), dbs.read_dict(stem), check_dtype=False, obj=f"dict:{stem}"
            )
        for stem in sorted(csv.list_data_stems()):
            pd.testing.assert_frame_equal(
                csv.read_data(stem), dbs.read_data(stem), check_dtype=False, obj=f"data:{stem}"
            )
    finally:
        dbs.close()


@pytest.mark.parametrize("label,d,case", CASES, ids=CASE_IDS)
def test_case_name_detected(label, d, case, converted):
    """Both backends agree on the case name."""
    _, _, db = converted[label]
    dbs = DuckDBSource(db)
    try:
        assert CSVSource(os.path.join(d, case)).case_name == case
        assert dbs.case_name == case
    finally:
        dbs.close()


def test_open_source_factory(converted):
    """A directory opens a CSVSource; a .duckdb file opens a DuckDBSource."""
    d, case, db = converted["home1"]
    src_csv = open_source(os.path.join(d, case))
    assert isinstance(src_csv, CSVSource)
    src_db = open_source(db)
    try:
        assert isinstance(src_db, DuckDBSource)
    finally:
        src_db.close()
    with pytest.raises(ValueError):
        open_source(os.path.join(d, "does_not_exist.txt"))


def test_resolve_source_prefers_csv_then_duckdb(tmp_path):
    """An empty same-named folder must not shadow a .duckdb input."""
    d, case = os.path.join(REPO, "src", "el1xr_opt"), "Home1"
    # CSV folder present -> CSVSource.
    assert isinstance(resolve_source(d, case), CSVSource)
    # Only a .duckdb present (empty results folder of the same name) -> DuckDBSource.
    work = tmp_path / "case_dir"
    work.mkdir()
    os.makedirs(work / case)  # looks like an output folder, has no Parameter file
    csv_case_to_duckdb(d, case, db_path=str(work / f"{case}.duckdb"))
    src = resolve_source(str(work), case)
    try:
        assert isinstance(src, DuckDBSource)
    finally:
        src.close()


def test_df_to_set_values():
    assert df_to_set_values(pd.DataFrame({"a": [1, 2]})) == [1, 2]
    assert df_to_set_values(pd.DataFrame({"a": ["x"], "b": ["y"]})) == [("x", "y")]
    assert df_to_set_values(pd.DataFrame()) == []
