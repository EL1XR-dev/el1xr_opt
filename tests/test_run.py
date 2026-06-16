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
def test_cost_from_csv(label, d, case, expected, rtol, deterministic_highs):
    """Solve the case reading its CSV folder; check the golden cost."""
    with truncated_duration(d, case):
        model = routine(**_run_dict(d, case))
    assert model is not None
    _assert_cost(float(pyo.value(model.eTotalSCost)), expected, rtol)


@pytest.mark.solve
@pytest.mark.parametrize("label,d,case,expected,rtol", CASES, ids=CASE_IDS)
def test_cost_from_duckdb(label, d, case, expected, rtol, tmp_path, deterministic_highs):
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
def test_retail_buy_couples_to_grid_import():
    """C14: the commercial retail buy/sell must equal the physical grid import/export at the
    electricity reference node (eEleImportBuyLink / eEleExportSellLink), so the energy cost and
    the grid-transfer fee are charged on the same flow. Checked on the multi-node Grid1 case,
    where the retailer sits at the reference node and the assets are on other nodes reached
    over lines -- the case that would expose a retail balance that ignored the network."""
    d = os.path.join(REPO, "src", "el1xr_opt")
    with truncated_duration(d, "Grid1"):
        m = routine(**_run_dict(d, "Grid1"))
    assert m is not None
    assert len(m.eEleImportBuyLink) > 0 and len(m.eEleExportSellLink) > 0, \
        "C14 buy<->import coupling constraints were not built"
    p, sc = list(m.ps)[0]
    ref = list(m.endrf)
    imp = sum(m.vEleImport[p, sc, n, nd]() for n in m.n for nd in ref)
    buy = sum(m.vEleBuy[p, sc, n, er]() for n in m.n for er in m.er)
    exp = sum(m.vEleExport[p, sc, n, nd]() for n in m.n for nd in ref)
    sell = sum(m.vEleSell[p, sc, n, er]() for n in m.n for er in m.er)
    assert abs(imp - buy) < 1e-4, f"grid import {imp} != retail buy {buy} (C14)"
    assert abs(exp - sell) < 1e-4, f"grid export {exp} != retail sell {sell} (C14)"


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
    # Re-baselined again for audit C30: the FCR endurance constraints left the LAST load
    # level's bid with no energy backing, so a unit could over-bid reserve at end of horizon
    # for free. Backing the terminal bid removes that spurious revenue, so the four cases that
    # exploited it (HoodBatt, HomeBattFCRNonly, H2Tank, Electrolyser) cost a little more; the
    # others were not bidding at the last level and are unchanged. (C31 min-vs-avg and C46
    # per-unit ramp are latent here: the FCR-N up/down requirements are equal and these cases
    # have no thermal ramp units.)
    pytest.param("HomeBatt",          44.27655530263448, id="HomeBatt"),
    pytest.param("HoodBatt",         -19.98879641148733, id="HoodBatt"),
    pytest.param("HomeBattNoTariff", 125.5265553026345,  id="HomeBattNoTariff"),
    pytest.param("HomeBattNoFCR",    122.8894702739726,  id="HomeBattNoFCR"),
    pytest.param("HomeBattFCRDonly",  67.90928111201895, id="HomeBattFCRDonly"),
    pytest.param("HomeBattFCRNonly",  57.34981288056188, id="HomeBattFCRNonly"),
    # H2Tank / Electrolyser re-baselined for Phase B (B0+B2): factor2 eliminated (commitment costs
    # now in canonical SEK -- cold start 30, shut-down 5, no-load 0) plus the new per-kWh stack
    # degradation cost (0.07 SEK/kWh) on the electrolyser. Net +~2.68 SEK vs the pre-Phase-B golden.
    pytest.param("H2Tank",            6779.395958990599, id="H2Tank"),
    pytest.param("Electrolyser",      6779.392248118394, id="Electrolyser"),
]
SIZING_CASE_NAMES = ["HomeBatt", "HoodBatt", "HomeBattNoTariff", "HomeBattNoFCR",
                     "HomeBattFCRDonly", "HomeBattFCRNonly", "H2Tank", "Electrolyser",
                     "ElectrolyserStandby", "ElectrolyserFCR", "H2TankCompressor",
                     "ElectrolyserFCRCompressor"]
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
def test_sizing_case_from_duckdb(case, expected, sizing_cases_built, deterministic_highs):
    """Solve each variant case from its generated .duckdb and check the golden cost."""
    model = routine(dir=sizing_cases_built, case=case, solver="highs",
                    date=datetime.datetime.now().replace(second=0, microsecond=0),
                    rawresults="False", plots="False", indlog="False", duckdbresults="False")
    assert model is not None
    _assert_cost(float(pyo.value(model.eTotalSCost)), expected, SIZING_RTOL)


@pytest.mark.solve
@pytest.mark.parametrize("case", ["HomeBattFCRDonly", "Electrolyser", "H2TankCompressor"])
def test_sizing_factor1_invariant(case, sizing_cases_built):
    """C38: factor1 is a true unit conversion, so the optimum is invariant under it. This guards
    the paths the main invariance test (Home1) does not exercise: FCR-D/FCR-N provision and its
    storage SoC-endurance backing, the electricity PPA settlement, the electrolyser, and the
    investment/sizing layer. Solving each case at FACTOR1=1 and FACTOR1=2 must give the same total
    cost. (Regression guard for the unscaled MaxStorage in the endurance constraints and the
    unscaled PPA price, both fixed in audit C38.)"""
    import el1xr_opt.Modules.oM_InputData as _ID

    def _cost(f1):
        _ID.FACTOR1 = f1
        try:
            m = routine(dir=sizing_cases_built, case=case, solver="highs",
                        date=datetime.datetime.now().replace(second=0, microsecond=0),
                        rawresults="False", plots="False", indlog="False", duckdbresults="False")
        finally:
            _ID.FACTOR1 = 1.0
        return float(pyo.value(m.eTotalSCost))

    c1 = _cost(1.0)
    c2 = _cost(2.0)
    assert abs(c2 - c1) <= 1e-5 * max(1.0, abs(c1)), \
        f"{case}: factor1 must leave the optimum invariant: cost {c1} (f1=1) vs {c2} (f1=2)"


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
def test_compressor_sizing_decision(sizing_cases_built):
    """Phase 1 compressor sizing, end to end: the compressor on the hydrogen tank is
    built to a positive fraction, the tank's charge flow never exceeds the built
    compressor throughput (the duty bound holds in the solution), and the tank
    actually charges -- so the compressor is sized to the realized charging duty."""
    model = routine(dir=sizing_cases_built, case="H2TankCompressor", solver="highs",
                    date=datetime.datetime.now().replace(second=0, microsecond=0),
                    rawresults="False", plots="False", indlog="False", duckdbresults="False")
    assert model is not None
    assert len(model.hgcompc) == 1, "exactly one compressor-sizing candidate expected"
    u = next(iter(model.hgcompc))
    frac = model.vHydCompInvest[u]()
    assert 0.0 < frac <= 1.0 + 1e-6, f"compressor build fraction {frac:.4f}, expected a positive build"
    built = model.Par["pHydGenCompressorNameplate"][u] * model.factor1 * frac
    peak = 0.0
    for idx in model.vHydTotalCharge:
        if idx[-1] == u:
            ch = model.vHydTotalCharge[idx]()
            peak = max(peak, ch)
            assert ch <= built + 1e-4, f"charge {ch:.4f} exceeds built compressor throughput {built:.4f}"
    assert peak > 1e-3, f"tank never charged (peak {peak:.4f}), compressor sizing not exercised"


def test_compressor_tied_to_candidate_tank(sizing_cases_built):
    """A compressor only makes sense if the tank it injects into is built. When that tank
    is itself an investment candidate (H2TankCompressor: PEMEL_01 is both), the build
    coupling vHydCompInvest <= vHydGenInvest is added. When the compressor sits on an
    EXISTING tank (ElectrolyserFCRCompressor: the candidate is the electrolyser, the tank
    exists), no coupling row is built -- the compressor keeps its own free build decision."""
    from pyomo.core.expr.visitor import identify_variables

    from el1xr_opt.Modules.oM_Sequence import build_model
    date = datetime.datetime.now().replace(second=0, microsecond=0)

    m = build_model(sizing_cases_built, "H2TankCompressor", date)
    assert len(m.eHydCompInvestLink) == 1, "coupling expected when the tank is a candidate"
    row = next(iter(m.eHydCompInvestLink.values()))
    names = {v.name.split("[")[0] for v in identify_variables(row.body)}
    assert "vHydCompInvest" in names and "vHydGenInvest" in names

    m2 = build_model(sizing_cases_built, "ElectrolyserFCRCompressor", date)
    assert len(m2.eHydCompInvestLink) == 0, \
        "no coupling expected when the compressor sits on an existing tank"


def test_compressor_fcr_coupling_structure(sizing_cases_built):
    """Phase 2: with both an FCR electrolyser and a sized compressor at a node, the FCR-down
    rate coupling is built, tying the electrolyser's down-bids to the spare compressor
    throughput (the built compressor rate minus the baseline charge flow)."""
    from pyomo.core.expr.visitor import identify_variables

    from el1xr_opt.Modules.oM_Sequence import build_model
    m = build_model(sizing_cases_built, "ElectrolyserFCRCompressor",
                    datetime.datetime.now().replace(second=0, microsecond=0))
    assert "PEMEL_01" in m.hgcompc and "AEL_01" in m.e2h
    assert len(m.eEleFreqDownCompressorRate) > 0
    names = {v.name.split("[")[0]
             for v in identify_variables(next(iter(m.eEleFreqDownCompressorRate.values())).body)}
    assert "vEleFreqContReserveDisDownwardBid" in names
    assert "vEleFreqContReserveNorBid" in names
    assert "vHydCompInvest" in names
    assert "vHydTotalCharge" in names


@pytest.mark.solve
def test_compressor_fcr_coupling_solves(sizing_cases_built):
    """Phase 2 end to end: the combined FCR + compressor-sizing case solves, the compressor
    is built, the FCR-down rate constraint is active, and it holds in the solution (the extra
    production a held down-bid would make fits the spare compressor throughput at the node)."""
    model = routine(dir=sizing_cases_built, case="ElectrolyserFCRCompressor", solver="highs",
                    date=datetime.datetime.now().replace(second=0, microsecond=0),
                    rawresults="False", plots="False", indlog="False", duckdbresults="False")
    assert model is not None
    assert model.vHydCompInvest["PEMEL_01"]() > 0.0, "compressor not built"
    assert len(model.eEleFreqDownCompressorRate) > 0
    # every rate-constraint row is satisfied in the solution
    for idx in model.eEleFreqDownCompressorRate:
        con = model.eEleFreqDownCompressorRate[idx]
        body = pyo.value(con.body)
        if con.upper is not None:
            assert body <= float(pyo.value(con.upper)) + 1e-4
        if con.lower is not None:
            assert body >= float(pyo.value(con.lower)) - 1e-4


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


@pytest.mark.solve
def test_electrolyser_pwl_efficiency(sizing_cases_built, tmp_path):
    """B1: with the piecewise-linear part-load efficiency flag on, the electrolyser uses the
    PWL conversion instead of the constant ProductionFunction. Verify the curve is built and
    correct (full load reproduces the constant PF, the curve genuinely varies away from it),
    the linear conversion is skipped for the PWL unit, the case solves, and the SOS2 condition
    holds in the solution (weights nonzero on at most two adjacent breakpoints per hour)."""
    import shutil

    import duckdb

    src = os.path.join(sizing_cases_built, "ElectrolyserStandby.duckdb")
    dst = os.path.join(str(tmp_path), "ElectrolyserStandby.duckdb")
    shutil.copy(src, dst)
    con = duckdb.connect(dst)
    cols = [r[0] for r in con.execute(
        "SELECT column_name FROM information_schema.columns WHERE table_name='data_Option'").fetchall()]
    if "IndBinElectrolyserPWL" not in cols:
        con.execute("ALTER TABLE data_Option ADD COLUMN IndBinElectrolyserPWL INTEGER")
    con.execute("UPDATE data_Option SET IndBinElectrolyserPWL = 1")
    con.close()

    model = routine(dir=str(tmp_path), case="ElectrolyserStandby", solver="highs",
                    date=datetime.datetime.now().replace(second=0, microsecond=0),
                    rawresults="False", plots="False", indlog="False", duckdbresults="False")
    assert model is not None
    u = "AEL_01"

    # the PWL is active for the electrolyser and its variables are built
    assert u in model.hpwl, f"PWL not enabled for {u}; hpwl={list(model.hpwl)}"
    assert hasattr(model, "vHydGenPWLWeight"), "PWL weight variable not built"
    # the constant-efficiency conversion is skipped for the PWL unit
    assert not any(idx[-1] == u for idx in model.eAllEnergy2Hyd), \
        "the linear conversion is still built for the PWL electrolyser"

    # curve correctness: full-load breakpoint reproduces the constant PF; the curve genuinely
    # varies away from it (real part-load efficiency, not a trivial reproduction)
    pf = float(model.Par["pHydGenProductionFunction"][u])
    se = [x / y for (x, y) in model.pwl_curve[u]]   # specific energy [kWh/kgH2] per breakpoint
    assert abs(se[-1] - pf) < 1e-6, "full-load PWL point must reproduce ProductionFunction"
    assert max(abs(s - pf) for s in se) > 0.01 * pf, "PWL curve must vary from the constant PF"

    # SOS2 in the solution: at most two adjacent breakpoints carry weight in any hour
    for n in model.n:
        nz = [k for k in model.pwlbp if model.vHydGenPWLWeight["period1", "sc01", n, u, k]() > 1e-6]
        assert len(nz) <= 2 and (len(nz) < 2 or nz[1] == nz[0] + 1), \
            f"SOS2 (adjacency) violated at {n}: nonzero breakpoints {nz}"


def test_electrolyser_canonical_costs_and_degradation(sizing_cases_built):
    """B0+B2: factor2 is eliminated (the model holds no factor2 attribute), so the electrolyser
    commitment costs are used directly in the canonical currency (cold start 30, shut-down 5,
    no-load 0), and a per-kWh stack-degradation cost enters the generation cost on the
    electrolyser's productive electricity. With no-load removed the electrolyser leaves the hgt
    no-load set, so this also checks its shut-down cost is still billed (the e2h shut-down term)."""
    from pyomo.core.expr.visitor import identify_variables

    from el1xr_opt.Modules.oM_Sequence import build_model

    model = build_model(sizing_cases_built, "Electrolyser",
                        datetime.datetime.now().replace(second=0, microsecond=0))
    u = "AEL_01"
    assert not hasattr(model, "factor2"), "factor2 should be eliminated (single canonical currency)"
    assert abs(float(model.Par["pHydGenStartUpCost"][u]) - 30.0) < 1e-9, "cold-start cost not canonical"
    assert abs(float(model.Par["pHydGenShutDownCost"][u]) - 5.0) < 1e-9, "shut-down cost not canonical"
    assert float(model.Par["pHydGenConstantVarCost"][u]) == 0.0 and u not in model.hgt, \
        "no-load cost should be 0 and the electrolyser out of the hgt no-load set"
    assert abs(float(model.Par["pHydGenDegradationCost"][u]) - 0.07) < 1e-9, "degradation cost not read"

    p, sc = list(model.ps)[0]
    n = list(model.n)[0]
    gcost_vars = {v.name for v in identify_variables(model.eTotalHydGCost[p, sc, n].body)}
    assert any("vEleTotalCharge" in nm and u in nm for nm in gcost_vars), \
        "degradation must put the electrolyser productive electricity into the generation cost"
    sucost_vars = {v.name for v in identify_variables(model.eTotalHydSUCost[p, sc].body)}
    assert any("vHydGenShutDown" in nm and u in nm for nm in sucost_vars), \
        "the electrolyser shut-down cost must still be billed via the e2h shut-down term"


def test_currency_label(sizing_cases_built, tmp_path):
    """The currency is a configurable label only -- the model works in a single canonical unit,
    so no numbers change with it. It defaults to SEK and is settable via the dfParameter
    'Currency' column (used for the objective print and the cost-result column header)."""
    import shutil

    import duckdb

    from el1xr_opt.Modules.oM_Sequence import build_model
    date = datetime.datetime.now().replace(second=0, microsecond=0)

    # default currency is SEK
    m = build_model(sizing_cases_built, "Electrolyser", date)
    assert m.Par["pParCurrency"] == "SEK"

    # settable via the dfParameter Currency column
    dst = os.path.join(str(tmp_path), "Electrolyser.duckdb")
    shutil.copy(os.path.join(sizing_cases_built, "Electrolyser.duckdb"), dst)
    con = duckdb.connect(dst)
    cols = [r[0] for r in con.execute(
        "SELECT column_name FROM information_schema.columns WHERE table_name='data_Parameter'").fetchall()]
    if "Currency" not in cols:
        con.execute("ALTER TABLE data_Parameter ADD COLUMN Currency VARCHAR")
    con.execute("UPDATE data_Parameter SET Currency = 'EUR'")
    con.close()
    m2 = build_model(str(tmp_path), "Electrolyser", date)
    assert m2.Par["pParCurrency"] == "EUR"


def test_compressor_sizing_structure(sizing_cases_built, tmp_path):
    """Phase 1 compressor sizing: the compressor is an independent investment decision.
    Off by default (no candidate set), and when a unit carries a CompressorInvestCost the
    build variable, the throughput duty bound (tying the charge flow to the build fraction),
    and the capex term in the total investment cost are all present."""
    import shutil

    import duckdb
    from pyomo.core.expr.visitor import identify_variables

    from el1xr_opt.Modules.oM_Sequence import build_model
    date = datetime.datetime.now().replace(second=0, microsecond=0)

    # default: no CompressorInvestCost column -> empty candidate set, nothing added
    m0 = build_model(sizing_cases_built, "H2Tank", date)
    assert len(m0.hgs) > 0, "H2Tank should have a hydrogen storage unit"
    assert len(m0.hgcompc) == 0

    # add the compressor sizing columns to the hydrogen generation table
    dst = os.path.join(str(tmp_path), "H2Tank.duckdb")
    shutil.copy(os.path.join(sizing_cases_built, "H2Tank.duckdb"), dst)
    con = duckdb.connect(dst)
    cols = [r[0] for r in con.execute(
        "SELECT column_name FROM information_schema.columns WHERE table_name='data_HydrogenGeneration'").fetchall()]
    for col in ("CompressorNameplate", "CompressorInvestCost"):
        if col not in cols:
            con.execute(f"ALTER TABLE data_HydrogenGeneration ADD COLUMN {col} DOUBLE")
    con.execute("UPDATE data_HydrogenGeneration SET CompressorNameplate = 10.0, CompressorInvestCost = 1000.0")
    con.close()

    m = build_model(str(tmp_path), "H2Tank", date)
    # the storage unit is now a compressor-sizing candidate, with a build variable
    assert len(m.hgcompc) > 0
    assert len(m.vHydCompInvest) > 0
    # the duty bound has active rows and ties the charge flow to the build fraction
    assert len(m.eHydInvestMaxCompressor) > 0
    duty_vars = {v.name for v in identify_variables(next(iter(m.eHydInvestMaxCompressor.values())).body)}
    assert any(vn.startswith("vHydTotalCharge") for vn in duty_vars)
    assert any(vn.startswith("vHydCompInvest") for vn in duty_vars)
    # the compressor capex enters the total investment cost
    icost_vars = {v.name for v in identify_variables(m.eTotalICost.body)}
    assert any(vn.startswith("vHydCompInvest") for vn in icost_vars)

    # guard: a positive CompressorInvestCost with a zero nameplate fails loudly
    bad_dir = os.path.join(str(tmp_path), "bad")
    os.makedirs(bad_dir, exist_ok=True)
    bad = os.path.join(bad_dir, "H2Tank.duckdb")
    shutil.copy(os.path.join(sizing_cases_built, "H2Tank.duckdb"), bad)
    con = duckdb.connect(bad)
    for col in ("CompressorNameplate", "CompressorInvestCost"):
        if col not in cols:
            con.execute(f"ALTER TABLE data_HydrogenGeneration ADD COLUMN {col} DOUBLE")
    con.execute("UPDATE data_HydrogenGeneration SET CompressorNameplate = 0.0, CompressorInvestCost = 1000.0")
    con.close()
    with pytest.raises(ValueError, match="CompressorNameplate"):
        build_model(bad_dir, "H2Tank", date)


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
def test_electrolyser_fcr_solves(sizing_cases_built):
    """Base ElectrolyserFCR solves to a sane (small) objective. This is the regression
    guard the missing solve test would have caught: the case was infeasible (no hydrogen
    import to back the demand) and the solver only returned a penalty-laden pseudo-solution,
    which surfaced later as the compressor case failing to build the compressor."""
    model = routine(dir=sizing_cases_built, case="ElectrolyserFCR", solver="highs",
                    date=datetime.datetime.now().replace(second=0, microsecond=0),
                    rawresults="False", plots="False", indlog="False", duckdbresults="False")
    assert model is not None
    # the electrolyser FCR endurance path is built and the solve is feasible (a real cost,
    # not the large penalty value an infeasible case returns)
    assert len(model.eEleFreqDownEnduranceConv) > 0
    assert 0.0 < float(pyo.value(model.eTotalSCost)) < 1.0e4


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
