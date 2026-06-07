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
them. Wiring temporal Benders into el1xr therefore needs those handled at the master
(the peak becomes a linking variable across windows, the fixed charge is counted
once); the per-level operating cost, validated here, is the part that decomposes.
See ``docs/decomposition.md``.

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
