"""Solve-tier validation tests.

Each validation case is truncated to its first 744 load levels (about a month)
and solved; the total system cost is checked against a stored golden value.
Every case is solved twice: once reading the CSV folder and once reading the
same case as a ``.duckdb`` file, so the two input paths are proven equivalent.

These tests build and solve a model, so they are marked ``solve`` and skipped
in the fast CI tier (``pytest -m "not solve"``).
"""
import contextlib
import datetime
import os
import shutil
import tempfile

import numpy as np
import pandas as pd
import pyomo.environ as pyo
import pytest

from el1xr_opt.Modules.oM_Sequence import routine
from el1xr_opt.Modules.oM_CsvToDuckDB import csv_case_to_duckdb

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TRUNC = 744  # load levels kept (~1 month)

# label, parent dir, case, golden cost, relative tolerance.
# LP cases reproduce the cost exactly; EEM26 carries unit-commitment binaries,
# so its cost is only reproducible within the solver's MIP gap.
CASES = [
    ("home1", os.path.join(REPO, "src", "el1xr_opt"), "Home1", 182.9440915402727,  1e-6),
    ("grid1", os.path.join(REPO, "src", "el1xr_opt"), "Grid1", 7847.932381485619,  1e-6),
    ("eem26", os.path.join(REPO, "data", "EEM26"),    "Home1", 787.0389607235827,  2.5e-2),
    ("h2vpp", os.path.join(REPO, "data", "H2VPP"),    "Home1", 354.0527479052698,  1e-6),
]
CASE_IDS = [c[0] for c in CASES]


@contextlib.contextmanager
def truncated_duration(d, case, n=TRUNC):
    """Temporarily blank the Duration of all load levels past ``n`` and restore it.

    The original file is backed up and restored byte for byte, so running the
    tests never leaves the tracked input files reformatted.
    """
    path = os.path.join(d, case, f"oM_Data_Duration_{case}.csv")
    fd, backup = tempfile.mkstemp(suffix=".csv")
    os.close(fd)
    shutil.copy2(path, backup)
    try:
        df = pd.read_csv(path, index_col=[0, 1, 2])
        df.iloc[n:, df.columns.get_loc("Duration")] = np.nan
        df.to_csv(path)
        yield
    finally:
        shutil.move(backup, path)


def _run_dict(d, case):
    return dict(
        dir=d, case=case, solver="highs",
        date=datetime.datetime.now().replace(second=0, microsecond=0),
        rawresults="False", plots="False", indlog="False", duckdbresults="False",
    )


def _assert_cost(actual, expected, rtol):
    rel = abs(actual - expected) / abs(expected)
    assert rel <= rtol, f"cost {actual!r} differs from golden {expected!r} by rel {rel:.2e} > {rtol:.1e}"


@pytest.mark.solve
@pytest.mark.parametrize("label,d,case,expected,rtol", CASES, ids=CASE_IDS)
def test_cost_from_csv(label, d, case, expected, rtol):
    """Solve the case reading its CSV folder; check the golden cost."""
    with truncated_duration(d, case):
        model = routine(**_run_dict(d, case))
    assert model is not None
    _assert_cost(float(pyo.value(model.eTotalSCost)), expected, rtol)


@pytest.mark.solve
@pytest.mark.parametrize("label,d,case,expected,rtol", CASES, ids=CASE_IDS)
def test_cost_from_duckdb(label, d, case, expected, rtol, tmp_path):
    """Solve the same (truncated) case from a .duckdb file; check the golden cost."""
    work = tmp_path / label
    os.makedirs(work / case)  # output folder for results
    with truncated_duration(d, case):
        csv_case_to_duckdb(d, case, db_path=str(work / f"{case}.duckdb"))
    data = _run_dict(str(work), case)
    model = routine(**data)
    assert model is not None
    _assert_cost(float(pyo.value(model.eTotalSCost)), expected, rtol)


@pytest.mark.solve
def test_duckdb_output_written(tmp_path):
    """Solving with duckdbresults on writes results.duckdb with the headline tables."""
    import duckdb

    d, case = os.path.join(REPO, "src", "el1xr_opt"), "Home1"
    work = tmp_path / "out"
    src_case = work / case
    shutil.copytree(os.path.join(d, case), src_case)
    with truncated_duration(str(work), case):
        data = _run_dict(str(work), case)
        data["duckdbresults"] = "True"
        routine(**data)
    db = src_case / "results.duckdb"
    assert db.exists(), "results.duckdb was not written"
    con = duckdb.connect(str(db), read_only=True)
    try:
        tables = {r[0] for r in con.execute("SELECT table_name FROM information_schema.tables").fetchall()}
        assert "oM_Result_RunMetadata" in tables
        assert "vEleTotalOutput" in tables
        meta = con.execute('SELECT "Key","Value" FROM "oM_Result_RunMetadata"').df()
        keys = set(meta["Key"])
        assert {"case", "objective", "solver"} <= keys
        obj = float(meta.loc[meta["Key"] == "objective", "Value"].iloc[0])
        _assert_cost(obj, 182.9440915402727, 1e-6)
    finally:
        con.close()
