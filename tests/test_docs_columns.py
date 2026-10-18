"""The input column reference (docs/rst/user-guide/input-columns.rst) covers every column of the shipped cases."""
import csv
import glob
import os

import pytest

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
COLS = os.path.join(REPO, "docs", "rst", "user-guide", "columns")
CASES = ["src/el1xr_opt/Home1", "src/el1xr_opt/Grid1", "data/Home1", "data/H2VPP/Home1", "data/EEM26/Home1"]
# data table -> (reference file, value of its Table column, or None when the file has one table)
TABLES = {
    "ElectricityGeneration": ("generation", "electricity"), "HydrogenGeneration": ("generation", "hydrogen"),
    "ElectricityDemand": ("demand", "electricity"), "HydrogenDemand": ("demand", "hydrogen"),
    "ElectricityRetail": ("retail", "electricity"), "HydrogenRetail": ("retail", "hydrogen"),
    "ElectricityNetwork": ("network", "electricity"), "HydrogenNetwork": ("network", "hydrogen"),
    "Parameter": ("parameter", None),
}


def _documented(name, table):
    """Columns listed for ``table`` in the reference file ``name`` and its unused list."""
    out = set()
    for path in (f"{name}.csv", f"{name}_unused.csv"):
        for row in csv.DictReader(open(os.path.join(COLS, path))):
            if table is None or row["Table"] in (table, "both"):
                out.add(row["Column"])
    return out


@pytest.mark.parametrize("stem", sorted(TABLES))
def test_every_column_is_documented(stem):
    name, table = TABLES[stem]
    known = _documented(name, table)
    missing = {}
    for case in CASES:
        for f in glob.glob(os.path.join(REPO, case, f"oM_Data_{stem}_*.csv")):
            header = next(csv.reader(open(f)))
            cols = {h for h in header if h and not h.startswith("Unnamed")}
            if cols - known:
                missing[case] = sorted(cols - known)
    assert not missing, f"columns of {stem} missing from docs/rst/user-guide/columns/{name}*.csv: {missing}"
