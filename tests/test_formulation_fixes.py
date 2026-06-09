"""Regression tests for formulation bugs found in the 2026-06 model audit.

1. The hydrogen O&M variable cost was **subtracted** in ``eTotalHydGCost`` while the
   electricity analogue adds it, so the model was effectively paid to run hydrogen
   generators.
2. The hydrogen storage inventory balance ``eHydInventory`` was gated on
   ``model.negs`` -- the *electricity* storage cycle set -- instead of
   ``model.nhgs``, so it was never built and hydrogen state-of-charge went
   untracked.
3. The ``eEleMaxRampDwOutput`` guard referenced ``model.Par['pEleGenRampDw']``, a
   misspelled parameter that exists nowhere, which would raise ``KeyError`` for any
   thermal unit with a ramp-down limit under ``IndBinGenRamps == 1``.
4. The hydrogen demand set ``model.hd`` had no base-year period filter (it kept the
   units whose ``MaximumPower`` was zero), so a hydrogen demand whose period window
   does not cover the base year was active anyway.
5. The heat operating cost was not weighted by the load-level duration, unlike the
   electricity and hydrogen operating costs, so it was mis-scaled on representative
   load levels that stand in for several hours.
6. The hydrogen ESS charge/discharge roles were swapped relative to the electricity
   ESS: the 2nd-block limits gated output by the charge binary and charge by the
   discharge binary, and the charge/discharge decisions normalized by the wrong
   capacity (charge by output power, output by charge capacity).

Bugs 1 and 2 are checked behaviourally on the ``H2Tank`` variant case, the only
shipped case that brings the hydrogen generation/storage units into the base year
(so the hydrogen sets are non-empty). The model is only *built*, not solved, so the
separate "hydrogen production does not fully serve the demand" gap in that case does
not matter here.

Bug 3 is checked at the source, because no shipped case has a thermal generator and
constructing one by hand trips unrelated set-membership assumptions in the build.
"""
import datetime
import os
import shutil
import subprocess
import sys
import tempfile

import pandas as pd
import pytest
from pyomo.environ import ConcreteModel, Set
from pyomo.repn import generate_standard_repn

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(REPO, "src"))
from el1xr_opt.Modules.oM_Sequence import build_model  # noqa: E402

SIZING_DIR = os.path.join(REPO, "data", "sizing")
MODEL_FORMULATION = os.path.join(REPO, "src", "el1xr_opt", "Modules",
                                 "oM_ModelFormulation.py")


@pytest.fixture(scope="module")
def h2_model():
    """Build (not solve) the ``H2Tank`` variant, where the hydrogen storage unit and
    the electrolyser are active. Generated on the fly from the H2VPP base if absent."""
    if not os.path.isfile(os.path.join(SIZING_DIR, "H2Tank.duckdb")):
        subprocess.run([sys.executable, os.path.join(SIZING_DIR, "make_sizing_cases.py")],
                       check=True, cwd=REPO)
    date = datetime.datetime.now().replace(second=0, microsecond=0)
    return build_model(SIZING_DIR, "H2Tank", date)


def test_hydrogen_storage_inventory_is_built(h2_model):
    """Bug 2: with a hydrogen storage unit present, ``eHydInventory`` must be built
    (it was silently skipped when gated on the electricity cycle set)."""
    assert len(h2_model.hgs) > 0, "test case has no hydrogen storage unit"
    assert len(h2_model.eHydInventory) > 0, \
        "hydrogen storage inventory balance was not built"


def test_hydrogen_om_cost_is_added(h2_model):
    """Bug 1: the output coefficient in ``eTotalHydGCost`` must reflect
    Linear + O&M (the O&M cost added), not Linear - O&M."""
    m = h2_model
    p, sc = list(m.ps)[0]
    n = list(m.n)[0]
    hg = next((g for g in m.hg if m.Par['pHydGenOMVariableCost'][g]), None)
    assert hg is not None, "test case has no hydrogen generator with an O&M cost"
    lin = float(m.Par['pHydGenLinearVarCost'][hg])
    om = float(m.Par['pHydGenOMVariableCost'][hg])
    repn = generate_standard_repn(m.eTotalHydGCost[p, sc, n].body)
    out = m.vHydTotalOutput[p, sc, n, hg]
    coef = next((c for v, c in zip(repn.linear_vars, repn.linear_coefs) if v is out), None)
    assert coef is not None, "output variable absent from the hydrogen generation cost"
    # the linear + O&M terms on the same variable combine; the buggy '- O&M' would
    # give |Linear - O&M| (zero here, since Linear == O&M).
    assert abs(coef) == pytest.approx(lin + om, rel=1e-9), \
        f"coefficient {coef} should reflect Linear+O&M={lin + om} (O&M added)"


def test_hydrogen_storage_charge_discharge_not_swapped(h2_model):
    """Bug 6: the hydrogen ESS must gate output by the DISCHARGE binary and charge by the
    CHARGE binary, and normalize output by the output power and charge by the charge
    capacity -- mirroring the electricity ESS. They were swapped."""
    m = h2_model
    assert len(m.hgs) > 0, "test case has no hydrogen storage unit"
    p, sc = list(m.ps)[0]
    hgs = list(m.hgs)[0]

    def _find(cname):
        c = getattr(m, cname)
        for n in m.n:
            if (p, sc, n, hgs) in c:
                return c[p, sc, n, hgs], n
        return None, None

    def _vnames(constr):
        return {v.name for v in generate_standard_repn(constr.body).linear_vars}

    def _coef(constr, var):
        repn = generate_standard_repn(constr.body)
        return next((cf for v, cf in zip(repn.linear_vars, repn.linear_coefs) if v is var), None)

    # the decisions must be built for a real storage unit (it charges and discharges)
    cdec, ncd = _find('eHydChargingDecision')
    ddec, ndd = _find('eHydDischargingDecision')
    assert cdec is not None and ddec is not None, \
        "hydrogen charge/discharge decisions not built for the storage unit"

    # decision binaries + capacity normalisation
    assert any('vHydStorCharge' in nm for nm in _vnames(cdec)), \
        "charging decision must use the charge binary"
    assert _coef(cdec, m.vHydTotalCharge[p, sc, ncd, hgs]) == \
        pytest.approx(1.0 / float(m.Par['pHydMaxCharge'][hgs][p, sc, ncd])), \
        "charging decision must normalize by the charge capacity (not the output power)"
    assert any('vHydStorDischarge' in nm for nm in _vnames(ddec)), \
        "discharging decision must use the discharge binary"
    assert _coef(ddec, m.vHydTotalOutput[p, sc, ndd, hgs]) == \
        pytest.approx(1.0 / float(m.Par['pHydMaxPower'][hgs][p, sc, ndd])), \
        "discharging decision must normalize by the output power (not the charge capacity)"

    # 2nd-block limits: output gated by discharge, charge gated by charge
    out2, _ = _find('eHydMaxESSOutput2ndBlock')
    if out2 is not None:
        names = _vnames(out2)
        assert any('vHydStorDischarge' in nm for nm in names) and \
            not any('vHydStorCharge' in nm for nm in names), \
            "output 2nd block must be gated by the discharge binary, not the charge binary"
    cha2, _ = _find('eMaxHydESSCharge2ndBlock')   # note: attr name differs from the rule
    if cha2 is not None:
        names = _vnames(cha2)
        assert any('vHydStorCharge' in nm for nm in names) and \
            not any('vHydStorDischarge' in nm for nm in names), \
            "charge 2nd block must be gated by the charge binary, not the discharge binary"


def test_ele_rampdown_uses_correct_param_name():
    """Bug 3: the ramp-down guard must use ``pEleGenRampDown``; the misspelled
    ``pEleGenRampDw`` raised KeyError for any ramp-limited thermal unit."""
    text = open(MODEL_FORMULATION, encoding="utf-8").read()
    assert "pEleGenRampDw'" not in text, \
        "misspelled parameter pEleGenRampDw was reintroduced"
    assert "pEleGenRampDown'" in text


def test_hydrogen_demand_respects_base_year_period():
    """Bug 4: a hydrogen demand whose period window does not cover the base year must
    be excluded from ``model.hd``. The shipped H2VPP demand (HydD1) runs 2040-2050
    while the base year is 2025, so it must not be active; with the bug (no period
    filter) it was."""
    work = tempfile.mkdtemp(prefix="h2dem_")
    dst = os.path.join(work, "Home1")
    shutil.copytree(os.path.join(REPO, "data", "H2VPP", "Home1"), dst)
    # truncate to a few load levels for a quick build
    dpath = os.path.join(dst, "oM_Data_Duration_Home1.csv")
    dur = pd.read_csv(dpath)
    keep = set(dur[dur.columns[2]].unique()[:6])
    dur.loc[~dur[dur.columns[2]].isin(keep), "Duration"] = float("nan")
    dur.to_csv(dpath, index=False)
    date = datetime.datetime.now().replace(second=0, microsecond=0)
    m = build_model(work, "Home1", date)
    assert "HydD1" in list(m.hdd), "test assumption: HydD1 is a declared demand unit"
    assert "HydD1" not in list(m.hd), \
        "out-of-period hydrogen demand should be excluded from model.hd"


def test_heat_operating_cost_is_duration_weighted():
    """Bug 5: the heat operating cost must be weighted by the load-level duration
    (like the electricity/hydrogen operating costs). The boiler-output coefficient in
    HeatOperatingCost must be duration * cost, not just cost."""
    from el1xr_opt.Modules.oM_HeatSector import create_heat_sector
    P, S, DUR, COST = "p1", "s1", 3.0, 7.0
    levels = ["n0001", "n0002"]
    m = ConcreteModel()
    m.n = Set(initialize=levels, ordered=True)
    m.ps = [(P, S)]
    m.htd = ["HD"]
    m.htg = ["HP", "BOIL"]
    m.htp = ["HP"]
    m.hts = ["TS"]
    m.n2htd = [("H", "HD")]
    m.n2htg = [("H", "HP"), ("H", "BOIL")]
    m.n2hts = [("H", "TS")]
    m.Par = {
        "pHeatDemand":      {"HD": {(P, S, n): 5.0 for n in levels}},
        "pHeatGenMaxPower": {"HP": 30.0, "BOIL": 50.0},
        "pHeatGenCost":     {"HP": 0.0, "BOIL": COST},
        "pHeatPumpCOP":     {"HP": 3.0},
        "pHeatStoMax":      {"TS": 20.0},
        "pHeatStoEff":      {"TS": 0.95},
        "pHeatStoInitial":  {"TS": 5.0},
        "pHeatNSCost":      1000.0,
        "pDuration":        {(P, S, n): DUR for n in levels},   # non-unit, (p,sc,n)-keyed
    }
    create_heat_sector(m, m)
    repn = generate_standard_repn(m.HeatOperatingCost)
    out = m.vHeatOutput[P, S, levels[0], "BOIL"]
    coef = next((c for v, c in zip(repn.linear_vars, repn.linear_coefs) if v is out), None)
    assert coef is not None, "boiler output absent from the heat operating cost"
    assert coef == pytest.approx(DUR * COST), \
        f"coefficient {coef} should be duration*cost={DUR * COST} (duration-weighted)"


def test_electrolyser_input_capped_by_build_decision():
    """A candidate electrolyser's ELECTRICITY input must be capped by its build
    fraction (eHydInvestMaxCharge). An electrolyser converts electricity to hydrogen
    at output = input / ProductionFunction, so the input is the real capacity; sizing
    it only through the hydrogen-output cap left the input fixed at its operating
    bound, so building a larger unit bought no extra production."""
    if not os.path.isfile(os.path.join(SIZING_DIR, "Electrolyser.duckdb")):
        subprocess.run([sys.executable, os.path.join(SIZING_DIR, "make_sizing_cases.py")],
                       check=True, cwd=REPO)
    date = datetime.datetime.now().replace(second=0, microsecond=0)
    m = build_model(SIZING_DIR, "Electrolyser", date)
    candidates = [g for g in m.e2h if g in m.hgc]
    assert candidates, "test case has no candidate electrolyser"
    assert len(m.eHydInvestMaxCharge) > 0, \
        "candidate electrolyser electricity input is not capped by the build decision"
    p, sc = list(m.ps)[0]
    n = list(m.n)[0]
    g = candidates[0]
    repn = generate_standard_repn(m.eHydInvestMaxCharge[p, sc, n, g].body)
    names = {v.name for v in repn.linear_vars}
    assert any("vEleTotalCharge" in nm and g in nm for nm in names), \
        "the cap must constrain the electrolyser's electricity input"
    assert any("vHydGenInvest" in nm and g in nm for nm in names), \
        "the cap must scale with the build decision"
