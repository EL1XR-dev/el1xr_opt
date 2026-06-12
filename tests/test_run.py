"""Solve-tier validation tests.

Each validation case is truncated to its first 168 load levels (one week) and
solved; the total system cost is checked against a stored golden value.
Every case is solved twice: once reading the CSV folder and once reading the
same case as a ``.duckdb`` file, so the two input paths are proven equivalent.

These tests build and solve a model, so they are marked ``solve`` and skipped
in the fast CI tier (``pytest -m "not solve"``).
"""
import contextlib
import datetime
import os
import shutil
import subprocess
import sys
import tempfile

import numpy as np
import pandas as pd
import pyomo.environ as pyo
import pytest

from el1xr_opt.Modules.oM_Sequence import routine
from el1xr_opt.Modules.oM_CsvToDuckDB import csv_case_to_duckdb

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TRUNC = 168  # load levels kept (one week). One week of operation is enough to
             # exercise the model in CI; full-year "proper" runs belong on a
             # bigger machine (see docs/computational_efficiency.md).

# label, parent dir, case, golden cost, relative tolerance.
# LP cases reproduce the cost exactly; EEM26 carries unit-commitment binaries,
# so its cost is only reproducible within the solver's MIP gap.
CASES = [
    ("home1", os.path.join(REPO, "src", "el1xr_opt"), "Home1", 431.6554910249504,  1e-6),
    ("grid1", os.path.join(REPO, "src", "el1xr_opt"), "Grid1", 2860.67528768213,   1e-6),
    ("eem26", os.path.join(REPO, "data", "EEM26"),    "Home1", 522.2614955498034,  2.5e-2),
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


# --- Sizing / tariff / frequency-market variant cases ------------------------
# These are small LP cases generated from the H2VPP base by
# data/sizing/make_sizing_cases.py and read as .duckdb input files. The fixture
# regenerates them so nothing has to be committed. Costs are reproducible (LP).
SIZING_DIR = os.path.join(REPO, "data", "sizing")
# The H2Tank / Electrolyser cases serve a 5 kgH2/h demand from three sources: a
# priced hydrogen import at the converter node (cheap at night, expensive in the
# day), the electrolyser (cheaper than the day import), and the tank (buys cheap
# night hydrogen and discharges it through the day). H2Tank sizes the tank and
# builds it fully; Electrolyser sizes the electrolyser and builds a small
# fraction. The build decisions themselves are asserted in
# test_h2_sizing_decisions, because the investment-cost share of the total cost
# is below the cost tolerance.
SIZING_CASES = [
    # FCR-active battery goldens re-baselined for C21b/C18: a candidate battery can no
    # longer sell FCR-down reserve on unbuilt capacity, so it earns slightly less reserve
    # revenue and the net cost rises a little. HomeBattNoFCR is unchanged (no FCR).
    pytest.param("HomeBatt",          44.27655530263448, id="HomeBatt"),
    pytest.param("HoodBatt",         -22.04188316124317, id="HoodBatt"),
    pytest.param("HomeBattNoTariff", 125.5265553026345,  id="HomeBattNoTariff"),
    pytest.param("HomeBattNoFCR",    122.8894702739726,  id="HomeBattNoFCR"),
    pytest.param("HomeBattFCRDonly",  67.90928111201895, id="HomeBattFCRDonly"),
    pytest.param("HomeBattFCRNonly",  56.98016352651909, id="HomeBattFCRNonly"),
    pytest.param("H2Tank",            6774.093295025795, id="H2Tank"),
    pytest.param("Electrolyser",      6774.089825257397, id="Electrolyser"),
]
SIZING_CASE_NAMES = ["HomeBatt", "HoodBatt", "HomeBattNoTariff", "HomeBattNoFCR",
                     "HomeBattFCRDonly", "HomeBattFCRNonly", "H2Tank", "Electrolyser",
                     "ElectrolyserStandby", "ElectrolyserFCR"]
SIZING_RTOL = 1e-5


@pytest.fixture(scope="session")
def sizing_cases_built():
    """Build the variant case files (<Case>.duckdb) from the H2VPP base.

    The cases are not committed (only the generator is), so they are rebuilt here
    once per test session. If they already exist locally the rebuild is skipped.
    """
    missing = [c for c in SIZING_CASE_NAMES
               if not os.path.isfile(os.path.join(SIZING_DIR, f"{c}.duckdb"))]
    if missing:
        subprocess.run([sys.executable, os.path.join(SIZING_DIR, "make_sizing_cases.py")],
                       check=True, cwd=REPO)
    return SIZING_DIR


@pytest.mark.solve
@pytest.mark.parametrize("case,expected", SIZING_CASES)
def test_sizing_case_from_duckdb(case, expected, sizing_cases_built):
    """Solve each variant case from its generated .duckdb and check the golden cost."""
    model = routine(dir=sizing_cases_built, case=case, solver="highs",
                    date=datetime.datetime.now().replace(second=0, microsecond=0),
                    rawresults="False", plots="False", indlog="False", duckdbresults="False")
    assert model is not None
    _assert_cost(float(pyo.value(model.eTotalSCost)), expected, SIZING_RTOL)


@pytest.mark.solve
@pytest.mark.parametrize("case,unit,full_build", [
    ("H2Tank", "PEMEL_01", True),
    ("Electrolyser", "AEL_01", False),
], ids=["H2Tank", "Electrolyser"])
def test_h2_sizing_decisions(case, unit, full_build, sizing_cases_built):
    """The hydrogen sizing cases make real investment decisions: the tank is worth
    building in full (its day/night arbitrage gain dwarfs its investment cost),
    the electrolyser is built at a small fraction (only the hours where producing
    beats the day import price), the demand is fully served, and the tank cycles.
    The cost goldens alone cannot see this: the investment-cost share of the
    total is below the cost tolerance."""
    model = routine(dir=sizing_cases_built, case=case, solver="highs",
                    date=datetime.datetime.now().replace(second=0, microsecond=0),
                    rawresults="False", plots="False", indlog="False", duckdbresults="False")
    assert model is not None
    frac = model.vHydGenInvest[unit]()
    if full_build:
        assert frac > 0.99, f"tank build fraction {frac:.4f}, expected full build"
    else:
        assert 0.01 < frac < 0.5, f"electrolyser build fraction {frac:.4f}, expected a small partial build"
    hns = sum(model.vHNS[idx]() for idx in model.vHNS)
    assert hns < 1e-6, f"hydrogen demand not fully served (HNS={hns:.4f} kgH2)"
    discharge = sum(model.vHydTotalOutput["period1", "sc01", n, "PEMEL_01"]() for n in model.n)
    assert discharge > 1.0, f"tank never discharged (total {discharge:.4f} kgH2)"


@pytest.mark.solve
def test_electrolyser_standby_selected(sizing_cases_built):
    """The three-state electrolyser sits in standby through the idle hour of the
    (0.09, 0, 0.09) demand burst to avoid a cold restart: standby is actively chosen,
    it draws only its standby power, and it makes no hydrogen while in standby."""
    model = routine(dir=sizing_cases_built, case="ElectrolyserStandby", solver="highs",
                    date=datetime.datetime.now().replace(second=0, microsecond=0),
                    rawresults="False", plots="False", indlog="False", duckdbresults="False")
    assert model is not None
    u = "AEL_01"
    standby = {n: model.vHydGenStandBy["period1", "sc01", n, u]() for n in model.n}
    assert sum(1 for v in standby.values() if v > 0.5) > 0, "standby state was never selected"
    # no hydrogen is produced while in standby
    for n in model.n:
        if standby[n] > 0.5:
            assert model.vHydTotalOutput["period1", "sc01", n, u]() < 1e-4, \
                f"electrolyser produced hydrogen while in standby at {n}"


def test_electrolyser_fcr_structure(sizing_cases_built):
    """Build (without solving) the ElectrolyserFCR case and check the electrolyser
    FCR wiring is structurally present: the e2h constraints are built, the
    electrolyser bid enters the finite FCR requirement caps, and the bus-level
    FCR-down endurance is tied to the hydrogen storage headroom."""
    from pyomo.core.expr.visitor import identify_variables

    from el1xr_opt.Modules.oM_Sequence import build_model

    model = build_model(sizing_cases_built, "ElectrolyserFCR",
                        datetime.datetime.now().replace(second=0, microsecond=0))
    u = "AEL_01"
    assert u in model.e2h
    assert model.Par["pHydGenNoFCRD"][u] == 0 and model.Par["pHydGenNoFCRN"][u] == 0

    # all electrolyser FCR constraint families are built with active rows
    for name in ["eEleRelationFreqDisUpBid2Conv", "eEleRelationFreqDisDownBid2Conv",
                 "eEleRelationFreqNorUpBid2Conv", "eEleRelationFreqNorDownBid2Conv",
                 "eEleSymmFreqNorConv",
                 "eEleFreqUpChargeHeadroomConv", "eEleFreqDownChargeHeadroomConv",
                 "eEleFreqUpChargeBoundConv", "eEleFreqDownChargeBoundConv",
                 "eEleFreqDownEnduranceConv"]:
        assert len(getattr(model, name)) > 0, f"{name} has no active rows"

    # the electrolyser bid is summed in the FCR-D requirement cap, whose right-hand
    # side is the finite requirement (no unbounded bids)
    cap = next(iter(model.eEleFreqContReserveDisUpward.values()))
    assert cap.upper is not None and float(cap.upper) < float("inf")
    cap_vars = {v.name for v in identify_variables(cap.body)}
    assert any("DisUpwardBid" in vn and u in vn for vn in cap_vars), \
        "electrolyser bid missing from the FCR-D upward requirement cap"

    # the FCR-down endurance couples the previous-step bids to the hydrogen
    # storage inventory headroom at the same bus
    end = next(iter(model.eEleFreqDownEnduranceConv.values()))
    end_vars = {v.name for v in identify_variables(end.body)}
    assert any(vn.startswith("vHydInventory") for vn in end_vars), \
        "endurance constraint not tied to the hydrogen storage inventory"
    assert any("DisDownwardBid" in vn and u in vn for vn in end_vars), \
        "electrolyser downward bid missing from the endurance constraint"

    # the e2h bid variables are free to move (not fixed to zero) when the unit opts in
    bid = model.vEleFreqContReserveDisUpwardBid
    e2h_bids = [bid[idx] for idx in bid if idx[-1] == u]
    assert e2h_bids and not any(v.fixed for v in e2h_bids)


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
        _assert_cost(obj, 431.6554910249504, 1e-6)
    finally:
        con.close()
