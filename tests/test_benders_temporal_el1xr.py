"""Stage D -- el1xr storage-boundary temporal mechanics against the monolith.

Temporal block splitting cuts one operating horizon into contiguous time blocks
coupled by the storage inventory carried across the boundary. This test validates
that mechanic on the real el1xr model: solve the monolith, then split the horizon
into two windows and fix the boundary inventory (and investment) to the monolith's
values -- the outgoing inventory on window 1's last level, the incoming inventory
replacing window 2's first-level balance -- and check the two windows reproduce the
monolith's **per-level** operating cost exactly.

It checks the per-level cost, not the full objective, on purpose. el1xr's
per-scenario aggregate costs (peak demand, fixed network charge, energy tax;
``vTotalEleNCost`` / ``vTotalEleXCost``, the ``"ps"`` cost kind) depend on the whole
horizon, so they do not decompose by time window -- splitting would double-count
them. The full solve (``test_el1xr_temporal_benders_matches_monolithic``) handles
that: the fixed network charge is counted once in the master, and on this case the
peak / net-use-var / energy-tax costs are zero (no grid import). The per-level test
here isolates and checks the storage-boundary mechanics on their own. See
``docs/decomposition.md``.

Needs an LP/dual solver; skipped otherwise.
"""
import datetime
import os
import shutil
import sys
import tempfile

import pytest

import pandas as pd
from pyomo.environ import SolverFactory, Constraint, Param, value

sys.path.insert(0, os.path.dirname(__file__))
import _make_2scenario as gen
from el1xr_opt.Modules.oM_Sequence import build_model
from el1xr_opt.Modules.oM_Decomposition import el1xr_temporal_benders, BendersConfig

TRUNC = 6
SPLIT = 3
_PSN_COST = ("vTotalEleMCost", "vTotalHydMCost", "vTotalEleOCost", "vTotalHydOCost")
_PSN_REV = ("vTotalEleMRev", "vTotalHydMRev")


def _solver():
    for s in ("gurobi", "appsi_highs"):
        try:
            if SolverFactory(s).available(exception_flag=False):
                return s
        except Exception:
            pass
    return None


_SOLVER = _solver()
pytestmark = pytest.mark.skipif(_SOLVER is None, reason="needs an LP/dual solver")


def _levels(n):
    return [f"t{ i + 1:04d}" for i in range(n)]


def _build_window(work_src, case, date, level_names):
    work = tempfile.mkdtemp(prefix="win_")
    dst = os.path.join(work, case)
    shutil.copytree(os.path.join(work_src, case), dst)
    dpath = os.path.join(dst, f"oM_Data_Duration_{case}.csv")
    dur = pd.read_csv(dpath)
    lvl = dur.columns[2]
    dur.loc[~dur[lvl].isin(level_names), "Duration"] = float("nan")
    dur.to_csv(dpath, index=False)
    return build_model(work, case, date)


def _recourse_perlevel(m):
    p, sc = list(m.ps)[0]
    tot = 0.0
    for name in _PSN_COST:
        v = getattr(m, name)
        tot += sum(float(value(v[p, sc, n])) for n in m.n)
    for name in _PSN_REV:
        v = getattr(m, name)
        tot -= sum(float(value(v[p, sc, n])) for n in m.n)
    return float(value(m.Par['pDiscountFactor'][p])) * tot


@pytest.mark.solve
def test_el1xr_temporal_boundary_matches_monolithic_perlevel():
    work = tempfile.mkdtemp(prefix="tel1xr_")
    gen.build(work, n_scenarios=1, trunc=TRUNC)
    date = datetime.datetime.now().replace(second=0, microsecond=0)
    opt = SolverFactory(_SOLVER)

    full = build_model(work, "Home1", date)
    opt.solve(full)
    p, sc = list(full.ps)[0]
    mono = _recourse_perlevel(full)
    xe = {g: float(value(full.vEleGenInvest[g])) for g in full.egc}
    xh = {g: float(value(full.vHydGenInvest[g])) for g in full.hgc}
    blvl = _levels(TRUNC)[SPLIT - 1]
    invE = {egs: float(value(full.vEleInventory[p, sc, blvl, egs])) for egs in full.egs}
    invH = {hgs: float(value(full.vHydInventory[p, sc, blvl, hgs])) for hgs in full.hgs}

    def fix_invest(m):
        for g in m.egc:
            m.vEleGenInvest[g].fix(xe[g])
        for g in m.hgc:
            m.vHydGenInvest[g].fix(xh[g])

    # window 1: outgoing inventory fixed at its last level
    w1 = _build_window(work, "Home1", date, _levels(SPLIT))
    fix_invest(w1)
    for egs in w1.egs:
        if (p, sc, blvl, egs) in w1.vEleInventory:
            w1.vEleInventory[p, sc, blvl, egs].fix(invE[egs])
    for hgs in w1.hgs:
        if (p, sc, blvl, hgs) in w1.vHydInventory:
            w1.vHydInventory[p, sc, blvl, hgs].fix(invH[hgs])
    opt.solve(w1)
    R1 = _recourse_perlevel(w1)

    # window 2: incoming inventory replaces the first-level balance
    a = _levels(TRUNC)[SPLIT]
    w2 = _build_window(work, "Home1", date, _levels(TRUNC)[SPLIT:])
    fix_invest(w2)
    w2._sin_e = Param(list(w2.egs), mutable=True, initialize=lambda m, g: invE.get(g, 0.0))
    w2._sin_h = Param(list(w2.hgs), mutable=True, initialize=lambda m, g: invH.get(g, 0.0))
    w2._rep_e = Constraint(list(w2.egs), rule=lambda m, egs: Constraint.Skip if (p, sc, a, egs) not in m.eEleInventory else (
        m._sin_e[egs] + m.Par['pDuration'][p, sc, a] * (
            m.vEleEnergyInflows[p, sc, a, egs] - m.vEleEnergyOutflows[p, sc, a, egs]
            - m.vEleTotalOutput[p, sc, a, egs] * (1.0 / m.Par['pEleGenEfficiency_discharge'][egs])
            + m.Par['pEleGenEfficiency_charge'][egs] * m.vEleTotalCharge[p, sc, a, egs])
        == m.vEleInventory[p, sc, a, egs] + m.vEleSpillage[p, sc, a, egs]))
    w2._rep_h = Constraint(list(w2.hgs), rule=lambda m, hgs: Constraint.Skip if (p, sc, a, hgs) not in m.eHydInventory else (
        m._sin_h[hgs] + m.Par['pDuration'][p, sc, a] * (
            m.vHydEnergyInflows[p, sc, a, hgs] - m.vHydEnergyOutflows[p, sc, a, hgs]
            - m.vHydTotalOutput[p, sc, a, hgs]
            + m.Par['pHydGenEfficiency'][hgs] * m.vHydTotalCharge[p, sc, a, hgs])
        == m.vHydInventory[p, sc, a, hgs] + m.vHydSpillage[p, sc, a, hgs]))
    for egs in w2.egs:
        if (p, sc, a, egs) in w2.eEleInventory:
            w2.eEleInventory[p, sc, a, egs].deactivate()
    for hgs in w2.hgs:
        if (p, sc, a, hgs) in w2.eHydInventory:
            w2.eHydInventory[p, sc, a, hgs].deactivate()
    opt.solve(w2)
    R2 = _recourse_perlevel(w2)

    assert len(list(w1.n)) == SPLIT and len(list(w2.n)) == TRUNC - SPLIT
    assert abs(R1 + R2 - mono) / (abs(mono) + 1e-9) < 1e-4, \
        f"per-level windows {R1 + R2:.6f} vs monolith {mono:.6f}"


@pytest.mark.solve
@pytest.mark.parametrize("n_blocks", [2, 3])
def test_el1xr_temporal_benders_matches_monolithic(n_blocks):
    """Full temporal Benders solve (investment + boundary inventory in the master,
    fixed network charge counted once) reproduces the monolithic optimum. Peak /
    net-use-var / energy-tax costs are zero on this case (no grid import), so the
    only per-scenario aggregate cost is the fixed charge."""
    work = tempfile.mkdtemp(prefix="tel1xr_full_")
    gen.build(work, n_scenarios=1, trunc=8)
    date = datetime.datetime.now().replace(second=0, microsecond=0)
    full = build_model(work, "Home1", date)
    SolverFactory(_SOLVER).solve(full)
    mono = float(value(full.eTotalSCost))
    res = el1xr_temporal_benders(work, "Home1", date, n_time_blocks=n_blocks, solver=_SOLVER,
                                 config=BendersConfig(max_iterations=120, relative_gap=1e-7))
    assert res["converged"], f"did not converge: gap={res['gap']:.2e}"
    assert abs(res["objective"] - mono) / abs(mono) < 1e-5, \
        f"temporal benders {res['objective']:.6f} vs monolithic {mono:.6f}"


# --- peak demand charge (the horizon-coupling top-N import cost) -----------------
# The peak charge is the per-month sum of the N largest grid imports. It does not
# split by time window, so the temporal Benders reformulates it as a threshold-LP
# whose scalar threshold per (month, retailer) is a master linking variable. These
# tests exercise that on a case where the grid import (hence the peak) is non-zero.
#
# The peak indicators are binary in the true model; relaxing them (as the LP test
# cases do) underprices the peak. The threshold-LP gives the exact binary value as a
# pure LP, so the Benders (LP subproblems) is validated against the BINARY monolith.

_PEAK_PROFILE = [5.0, 2.0, 8.0, 1.0, 6.0, 3.0, 7.0, 4.0]   # top-2 = 8 + 7 = 15


def _make_import_case(work, npeaks=2, binary_peak=False):
    """A single-node case where the costed grid import is the only supply, so the
    peak charge is active. Node1 is both the market node (retailer EleR_01) and the
    physical node; all demand and a zero-output Solar anchor sit there (the anchor
    keeps the node balance active), every other unit is removed, and the lines are
    dropped. ``binary_peak`` turns the binary top-N peak selection on (the true MILP);
    left off it is the LP relaxation used by the Benders subproblems."""
    gen.build(work, n_scenarios=1, trunc=8)
    d = os.path.join(work, "Home1")

    def path(s):
        return os.path.join(d, f"oM_Data_{s}_Home1.csv")

    par = pd.read_csv(path("Parameter")); par["NumberPowerPeaks"] = npeaks
    par.to_csv(path("Parameter"), index=False)
    dem = pd.read_csv(path("ElectricityDemand")); dem["Node"] = "Node1"
    dem.to_csv(path("ElectricityDemand"), index=False)
    gN = pd.read_csv(path("ElectricityGeneration")); gN["Node"] = "Node1"
    gN.loc[~gN.iloc[:, 0].str.startswith("Solar"), "MaximumPower"] = 0.0   # drop EV/BESS
    gN["InitialStorage"] = 0.0
    gN.to_csv(path("ElectricityGeneration"), index=False)
    g = pd.read_csv(path("VarMaxGeneration"))
    for c in g.columns[3:]:
        g[c] = 0.0                                                         # no solar output
    g.to_csv(path("VarMaxGeneration"), index=False)
    pd.read_csv(path("ElectricityNetwork")).iloc[0:0].to_csv(path("ElectricityNetwork"), index=False)
    if binary_peak:
        op = pd.read_csv(path("Option")); op["IndBinGenOperat"] = 1
        op.to_csv(path("Option"), index=False)
    return work


@pytest.mark.solve
def test_threshold_lp_peak_matches_binary_topN():
    """The threshold-LP peak (built into the temporal Benders) equals the binary
    top-N peak. Here the import is fixed to a known profile so the peak cost is the
    sum of the N largest imports, checked against the binary monolith directly."""
    work = tempfile.mkdtemp(prefix="tpeak_")
    _make_import_case(work, binary_peak=True)
    date = datetime.datetime.now().replace(second=0, microsecond=0)
    m = build_model(work, "Home1", date)
    p, sc = list(m.ps)[0]
    nd0 = m.Par['pEleRetNode']['EleR_01']
    for n, v in zip(list(m.n), _PEAK_PROFILE):
        m.vEleImport[p, sc, n, nd0].fix(v)
    SolverFactory(_SOLVER).solve(m)
    coeff = 65.0 * float(m.factor1) * (1 + 0.25) / 2          # tariff * factor1 * (1+VAT) / N
    expected = coeff * sum(sorted(_PEAK_PROFILE, reverse=True)[:2])
    assert abs(float(value(m.vTotalElePeakCost[(p, sc)])) - expected) < 1e-3


@pytest.mark.solve
@pytest.mark.parametrize("n_blocks", [2, 3, 4])
def test_el1xr_temporal_benders_peak_matches_monolithic(n_blocks):
    """Full temporal Benders with the threshold-LP peak reproduces the binary
    monolithic optimum on a case with a non-zero peak charge. The grid import is
    pinned to a fixed profile in both (so the peak is the sum of the top-N imports),
    isolating the peak-linking mechanism."""
    date = datetime.datetime.now().replace(second=0, microsecond=0)

    # binary monolith (true top-N peak), import fixed
    wm = tempfile.mkdtemp(prefix="tpeakm_")
    _make_import_case(wm, binary_peak=True)
    mono_m = build_model(wm, "Home1", date)
    p, sc = list(mono_m.ps)[0]
    nd0 = mono_m.Par['pEleRetNode']['EleR_01']
    for n, v in zip(list(mono_m.n), _PEAK_PROFILE):
        mono_m.vEleImport[p, sc, n, nd0].fix(v)
    SolverFactory(_SOLVER).solve(mono_m)
    mono = float(value(mono_m.eTotalSCost))
    assert float(value(mono_m.vTotalElePeakCost[(p, sc)])) > 1.0          # peak is active

    # temporal Benders (LP threshold peak), same import pinned in each window
    wb = tempfile.mkdtemp(prefix="tpeakb_")
    _make_import_case(wb, binary_peak=False)
    levels = list(build_model(wb, "Home1", date).n)
    fix_import = {n: _PEAK_PROFILE[i] for i, n in enumerate(levels)}
    res = el1xr_temporal_benders(
        wb, "Home1", date, n_time_blocks=n_blocks, solver=_SOLVER,
        config=BendersConfig(max_iterations=300, relative_gap=1e-6,
                             extra={"fix_import": fix_import}))
    assert res["converged"], f"did not converge: gap={res['gap']:.2e}"
    assert abs(res["objective"] - mono) / abs(mono) < 1e-5, \
        f"temporal benders {res['objective']:.6f} vs binary monolith {mono:.6f}"


# --- endogenous import: the peak charge feeds back into the import decision -------
# The two tests above pin the grid import to a fixed profile, isolating the peak from
# the rest of the operating decision. Here the import is a free decision: the only
# supply is the grid, delivered through a battery that starts empty, so the model must
# import to meet demand and can charge the battery off-peak and discharge it into the
# demand spike -- shaving the top-N import (the peak charge) across the whole horizon.
# This couples the time windows two ways at once -- the storage inventory carried over
# each boundary and the peak threshold -- with the import chosen by the optimiser, so
# it exercises the genuine "import case" that the pinned tests cannot.


def _make_import_storage_case(work, npeaks=2, binary_peak=False):
    """A single-node case where the grid import is the only supply and a battery that
    starts empty can shift it in time. All demand sits at Node1 (the retailer node);
    every generator is removed except the battery BESS_01 -- kept alive as the node
    anchor and the peak-shaving store -- and every unit's initial storage is zero, so
    the import must serve the demand and the battery can only charge from it. With the
    demand spike (one hour far above the rest) the battery pre-charges off-peak and
    discharges into the spike, shaving the peak import. ``binary_peak`` turns on the
    binary top-N peak selection (and the other operating binaries) for the true MILP;
    left off it is the LP relaxation the Benders subproblems use."""
    gen.build(work, n_scenarios=1, trunc=8)
    d = os.path.join(work, "Home1")

    def path(s):
        return os.path.join(d, f"oM_Data_{s}_Home1.csv")

    par = pd.read_csv(path("Parameter")); par["NumberPowerPeaks"] = npeaks
    par.to_csv(path("Parameter"), index=False)
    dem = pd.read_csv(path("ElectricityDemand")); dem["Node"] = "Node1"
    dem.to_csv(path("ElectricityDemand"), index=False)
    gN = pd.read_csv(path("ElectricityGeneration")); gN["Node"] = "Node1"
    name = gN.columns[0]
    gN.loc[gN[name] != "BESS_01", "MaximumPower"] = 0.0      # battery is the only unit
    gN["InitialStorage"] = 0.0                               # empty start -> must import
    gN.to_csv(path("ElectricityGeneration"), index=False)
    pd.read_csv(path("ElectricityNetwork")).iloc[0:0].to_csv(path("ElectricityNetwork"), index=False)
    if binary_peak:
        op = pd.read_csv(path("Option")); op["IndBinGenOperat"] = 1
        op.to_csv(path("Option"), index=False)
    return work


@pytest.mark.solve
@pytest.mark.parametrize("n_blocks", [2, 3, 4])
def test_el1xr_temporal_benders_endogenous_import_matches_monolithic(n_blocks):
    """Temporal Benders with the threshold-LP peak reproduces the binary monolith on a
    case where the grid import is endogenous (not pinned): the battery shaves the import
    peak across the window boundaries, so the storage-boundary coupling and the peak
    threshold are both active and interacting, with the import chosen by the optimiser."""
    date = datetime.datetime.now().replace(second=0, microsecond=0)

    # binary monolith (true top-N peak), import chosen freely
    wm = tempfile.mkdtemp(prefix="tendm_")
    _make_import_storage_case(wm, binary_peak=True)
    mono_m = build_model(wm, "Home1", date)
    p, sc = list(mono_m.ps)[0]
    SolverFactory(_SOLVER).solve(mono_m)
    mono = float(value(mono_m.eTotalSCost))
    assert float(value(mono_m.vTotalElePeakCost[(p, sc)])) > 1.0          # peak is active
    nd0 = mono_m.Par['pEleRetNode']['EleR_01']
    imp = [float(value(mono_m.vEleImport[p, sc, n, nd0])) for n in mono_m.n]
    dem = [float(mono_m.Par['pVarMaxDemand']['EleD_01'][p, sc, n]) for n in mono_m.n]
    assert max(imp) < max(dem) - 1e-3        # the battery shaved the spike out of the import

    # temporal Benders (LP threshold peak), import free in each window
    wb = tempfile.mkdtemp(prefix="tendb_")
    _make_import_storage_case(wb, binary_peak=False)
    res = el1xr_temporal_benders(
        wb, "Home1", date, n_time_blocks=n_blocks, solver=_SOLVER,
        config=BendersConfig(max_iterations=200, relative_gap=1e-6))
    assert res["converged"], f"did not converge: gap={res['gap']:.2e}"
    assert abs(res["objective"] - mono) / abs(mono) < 1e-5, \
        f"temporal benders {res['objective']:.6f} vs binary monolith {mono:.6f}"


# --- transversality: sector coupling -----------------------------------------------
# The split couples the time windows only through storage inventory and the registered
# aggregate costs, which keeps it largely carrier-independent. The heat operating cost
# (heat-not-served + generator running cost) is a duration-weighted, period-discounted
# sum over the window's load levels, so it decomposes per window and is added to the
# recourse. A heat thermal store couples the windows like a battery, so its boundary
# inventory is a master linking variable too (the St analogue of Se / Sh). Both are
# validated against the monolith below.


def _make_heat_case(work, with_store=False, trunc=6):
    """Add a behind-the-meter heat sector to the Home1 case: a small heat pump and a
    boiler at the electricity node, with a heat demand the heat pump cannot fully meet
    so the (costed) boiler runs -- giving a non-zero heat operating cost that the split
    must reproduce. ``with_store`` adds a thermal store."""
    gen.build(work, n_scenarios=1, trunc=trunc)
    cd = os.path.join(work, "Home1")

    def hpath(stem):
        return os.path.join(cd, f"oM_Data_{stem}_Home1.csv")

    rows = {"Node": ["Node1", "Node1"], "Type": ["HeatPump", "Boiler"],
            "MaximumPower": [2.0, 1000.0], "Cost": [0.0, 9.0], "COP": [3.0, 0.0],
            "Efficiency": [0.0, 0.0], "MaxStorage": [0.0, 0.0], "StoEff": [0.0, 0.0],
            "InitialStorage": [0.0, 0.0]}
    idxn = ["HP1", "BOIL1"]
    if with_store:
        store = {"Node": "Node1", "Type": "Storage", "MaximumPower": 100.0, "Cost": 0.0,
                 "COP": 0.0, "Efficiency": 0.0, "MaxStorage": 50.0, "StoEff": 0.95,
                 "InitialStorage": 0.0}
        for k in rows:
            rows[k].append(store[k])
        idxn.append("HSTO1")
    pd.DataFrame(rows, index=idxn).to_csv(hpath("HeatGeneration"))
    pd.DataFrame({"Node": ["Node1"]}, index=["HD1"]).to_csv(hpath("HeatDemand"))
    lv = [f"t{i + 1:04d}" for i in range(trunc)]
    mi = pd.MultiIndex.from_tuples([("period1", "sc01", t) for t in lv])
    pd.DataFrame({"HD1": [5.0 + 2.0 * (i % 3) for i in range(trunc)]}, index=mi).to_csv(
        hpath("VarMaxHeatDemand"))
    return work


@pytest.mark.solve
@pytest.mark.parametrize("n_blocks", [2, 3])
def test_el1xr_temporal_benders_heat_operating_cost_matches_monolithic(n_blocks):
    """With a heat sector whose boiler must run (a non-zero heat operating cost), the
    temporal Benders reproduces the monolith -- the heat operating cost decomposes per
    window and is folded into the recourse alongside the heat-pump electricity draw."""
    date = datetime.datetime.now().replace(second=0, microsecond=0)
    m = build_model(_make_heat_case(tempfile.mkdtemp(prefix="theatm_")), "Home1", date)
    SolverFactory(_SOLVER).solve(m)
    mono = float(value(m.eTotalSCost))
    assert float(value(m.HeatOperatingCost)) > 1.0           # the boiler actually runs
    res = el1xr_temporal_benders(
        _make_heat_case(tempfile.mkdtemp(prefix="theatb_")), "Home1", date,
        n_time_blocks=n_blocks, solver=_SOLVER,
        config=BendersConfig(max_iterations=200, relative_gap=1e-7))
    assert res["converged"], f"did not converge: gap={res['gap']:.2e}"
    assert abs(res["objective"] - mono) / abs(mono) < 1e-5, \
        f"temporal benders {res['objective']:.6f} vs monolith {mono:.6f}"


def _make_heat_storage_case(work, trunc=6):
    """A heat sector where the thermal store must cycle across the window boundaries.
    A heat pump capped below the demand spike, a boiler (the bounded-cost backstop that
    keeps every window feasible, so the elastic-penalty duals stay small and the master
    is well conditioned), and a thermal store. The demand is flat then spikes above the
    pump capacity, so the store pre-charges off the pump and discharges into the spike,
    carrying heat inventory across the boundaries."""
    gen.build(work, n_scenarios=1, trunc=trunc)
    cd = os.path.join(work, "Home1")

    def hpath(stem):
        return os.path.join(cd, f"oM_Data_{stem}_Home1.csv")

    pd.DataFrame(
        {"Node": ["Node1"] * 3, "Type": ["HeatPump", "Boiler", "Storage"],
         "MaximumPower": [5.0, 1000.0, 0.0], "Cost": [0.0, 9.0, 0.0],
         "COP": [3.0, 0.0, 0.0], "Efficiency": [0.0, 0.0, 0.0],
         "MaxStorage": [0.0, 0.0, 50.0], "StoEff": [0.0, 0.0, 1.0],
         "InitialStorage": [0.0, 0.0, 0.0]},
        index=["HP1", "BOIL1", "HSTO1"]).to_csv(hpath("HeatGeneration"))
    pd.DataFrame({"Node": ["Node1"]}, index=["HD1"]).to_csv(hpath("HeatDemand"))
    lv = [f"t{i + 1:04d}" for i in range(trunc)]
    mi = pd.MultiIndex.from_tuples([("period1", "sc01", t) for t in lv])
    demand = [3.0, 3.0, 3.0, 3.0, 3.0, 15.0][:trunc]
    pd.DataFrame({"HD1": demand}, index=mi).to_csv(hpath("VarMaxHeatDemand"))
    return work


@pytest.mark.solve
@pytest.mark.parametrize("n_blocks", [2, 3, 4])
def test_el1xr_temporal_benders_heat_storage_matches_monolithic(n_blocks):
    """Temporal Benders with a heat thermal store that cycles across the window
    boundaries reproduces the monolith: the heat inventory is carried over each boundary
    by the St master linking variable, the heat analogue of the electricity/hydrogen
    Se/Sh boundary inventories."""
    date = datetime.datetime.now().replace(second=0, microsecond=0)
    m = build_model(_make_heat_storage_case(tempfile.mkdtemp(prefix="thstom_")), "Home1", date)
    SolverFactory(_SOLVER).solve(m)
    mono = float(value(m.eTotalSCost))
    p, sc = list(m.ps)[0]
    inv = [float(value(m.vHeatInventory[p, sc, n, "HSTO1"])) for n in m.n]
    assert max(inv) > 1.0          # the store genuinely cycles -> the boundary is exercised
    res = el1xr_temporal_benders(
        _make_heat_storage_case(tempfile.mkdtemp(prefix="thstob_")), "Home1", date,
        n_time_blocks=n_blocks, solver=_SOLVER,
        config=BendersConfig(max_iterations=300, relative_gap=1e-6))
    assert res["converged"], f"did not converge: gap={res['gap']:.2e}"
    assert abs(res["objective"] - mono) / abs(mono) < 1e-5, \
        f"temporal benders {res['objective']:.6f} vs monolith {mono:.6f}"
