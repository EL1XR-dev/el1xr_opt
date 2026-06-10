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
7. The hydrogen storage-energy bounds (inventory variable bound and investment cap) did
   not carry the factor1 unit conversion that the electricity bounds and the initial
   inventory do, so the cap and the accumulated/initial inventory were in different units
   when factor1 != 1.
8. The thermal-store inventory balance (``eHeatInventory``) did not weight the
   charge/discharge by the load-level duration, unlike the electricity/hydrogen
   inventories and the (duration-weighted) heat operating cost, so on a representative
   load level the store state and its cost disagreed.

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
MODULES = os.path.join(REPO, "src", "el1xr_opt", "Modules")
MODEL_FORMULATION = os.path.join(MODULES, "oM_ModelFormulation.py")
INPUT_DATA = os.path.join(MODULES, "oM_InputData.py")
INVESTMENT = os.path.join(MODULES, "oM_Investment.py")


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


def test_hydrogen_storage_energy_scaled_by_factor1():
    """Bug 7: hydrogen storage energy must carry the factor1 unit conversion -- on the
    inventory variable bounds and the investment cap -- like the electricity ESS and the
    (already factor1-scaled) initial inventory, so the cap, the initial state and the
    accumulated inventory share one unit. Checked at the source because factor1 is 1.0 by
    default, so a built model cannot distinguish the scaled from the unscaled form."""
    inp_lines = open(INPUT_DATA, encoding="utf-8").read().splitlines()
    hyd_bounds = [ln for ln in inp_lines
                  if "vHydInventory" in ln and (".setlb(" in ln or ".setub(" in ln)]
    assert hyd_bounds, "could not find the hydrogen inventory bound lines"
    assert all("model.factor1" in ln for ln in hyd_bounds), \
        "hydrogen inventory variable bounds must be scaled by model.factor1"
    inv_cap = [ln for ln in open(INVESTMENT, encoding="utf-8").read().splitlines()
               if "vHydInventory" in ln and "vHydGenInvest" in ln]
    assert inv_cap, "could not find the hydrogen investment inventory cap"
    assert all("model.factor1" in ln for ln in inv_cap), \
        "the hydrogen investment storage-energy cap must be scaled by model.factor1"


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


def test_heat_inventory_is_duration_weighted():
    """Bug 8: the thermal-store inventory balance must weight the charge/discharge by the
    load-level duration (like the electricity/hydrogen inventories), so the charge term's
    coefficient is duration*efficiency and the discharge term's is duration -- not just
    efficiency and 1 as before."""
    from el1xr_opt.Modules.oM_HeatSector import create_heat_sector
    P, S, DUR, EFF = "p1", "s1", 3.0, 0.95
    levels = ["n0001", "n0002"]
    m = ConcreteModel()
    m.n = Set(initialize=levels, ordered=True)
    m.ps = [(P, S)]
    m.htd = ["HD"]
    m.htg = ["HP"]
    m.htp = ["HP"]
    m.hts = ["TS"]
    m.n2htd = [("H", "HD")]
    m.n2htg = [("H", "HP")]
    m.n2hts = [("H", "TS")]
    m.Par = {
        "pHeatDemand":      {"HD": {(P, S, n): 5.0 for n in levels}},
        "pHeatGenMaxPower": {"HP": 30.0},
        "pHeatGenCost":     {"HP": 0.0},
        "pHeatPumpCOP":     {"HP": 3.0},
        "pHeatStoMax":      {"TS": 100.0},
        "pHeatStoEff":      {"TS": EFF},
        "pHeatStoInitial":  {"TS": 5.0},
        "pHeatNSCost":      1000.0,
        "pDuration":        {(P, S, n): DUR for n in levels},
    }
    create_heat_sector(m, m)
    repn = generate_standard_repn(m.eHeatInventory[P, S, levels[0], "TS"].body)
    coefs = {v.name: c for v, c in zip(repn.linear_vars, repn.linear_coefs)}
    chg = next((c for nm, c in coefs.items() if "vHeatCharge" in nm), None)
    dis = next((c for nm, c in coefs.items() if "vHeatDischarge" in nm), None)
    assert chg is not None and dis is not None, "charge/discharge absent from heat inventory"
    assert abs(chg) == pytest.approx(DUR * EFF), \
        f"charge coef {chg} should be duration*efficiency={DUR * EFF}"
    assert abs(dis) == pytest.approx(DUR), \
        f"discharge coef {dis} should be duration={DUR}"


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


# --- Crash-on-first-use batch (model audit Part C: C2, C5, C8, C33 latent, C27 behavioural) ---
# These bugs are latent in the shipped cases (no fuel cell, no committed thermal unit, no
# discharge-only ESS, no missing-column file), so they are guarded at the source -- except
# C27, where dropping the columns from a real file exercises the new fallback directly.


def test_hyd_balance_uses_defined_node_set_for_fuel_cell():
    """C2: the fuel-cell (h2e) hydrogen-consumption term in ``eHydBalance`` must filter on
    a DEFINED node-to-generator set. h2e units are electricity generators (``model.eg``),
    so their node membership lives in ``model.n2eg``; the code referenced the undefined
    ``model.n2g``, which raises ``AttributeError`` on the first case with a fuel cell."""
    text = open(MODEL_FORMULATION, encoding="utf-8").read()
    assert "model.n2g)" not in text, \
        "eHydBalance still references the undefined set model.n2g"
    h2e_terms = [ln for ln in text.splitlines() if "if (nd,h2e) in" in ln]
    assert h2e_terms and all("model.n2eg" in ln for ln in h2e_terms), \
        "the fuel-cell hydrogen-consumption term must filter on model.n2eg"


def test_thermal_fcrn_output_uses_generator_reserve_vars():
    """C5: the non-storage (generator) branches of ``eEleTotalOutput`` must reference the
    FCR-N GENERATOR reserve variables (``NorUpGen`` / ``NorDownGen``, declared on
    ``psnegt``), not the storage-only ``NorUpDis`` / ``NorDownDis`` (``psnegs``). The FCR-D
    legs already used the generator vars; the FCR-N legs wrongly used the discharge vars,
    raising ``KeyError`` on the first committed thermal unit. The storage branch keeps the
    discharge vars."""
    text = open(MODEL_FORMULATION, encoding="utf-8").read()
    gen_branches = [ln for ln in text.splitlines()
                    if "vEleFreqContReserveDisUpGen[p,sc,n,egnr]" in ln]
    assert gen_branches, "could not find the generator branches of eEleTotalOutput"
    for ln in gen_branches:
        assert "NorUpDis[p,sc,n,egnr]" not in ln and "NorDownDis[p,sc,n,egnr]" not in ln, \
            "generator FCR-N output term must not use the storage-only Dis reserve vars"
        assert "NorUpGen[p,sc,n,egnr]" in ln and "NorDownGen[p,sc,n,egnr]" in ln, \
            "generator FCR-N output term must reference NorUpGen/NorDownGen"


def test_pre_horizon_commitment_fixing_uses_own_load_level():
    """C8: the initial-commitment fixing loop over ``model.psnegt`` must test each index's
    OWN load level (``idx[-2]``) in ``model.n.ord(...)``. It used a stale loop variable
    ``n`` leaking from an earlier (single-node-only) loop, so in single-node mode the first
    unit with ``UpTimeZero`` / ``DownTimeZero > 0`` raised ``NameError``."""
    lines = open(INPUT_DATA, encoding="utf-8").read().splitlines()
    fixing = [ln for ln in lines
              if ("GenUpTimeZero" in ln or "GenDownTimeZero" in ln) and "model.n.ord(" in ln]
    assert fixing, "could not find the pre-horizon commitment fixing lines"
    for ln in fixing:
        assert "model.n.ord(idx[-2])" in ln, \
            "commitment fixing must use the index's own load level idx[-2]"
        assert "model.n.ord(n)" not in ln, \
            "commitment fixing must not use the stale loop variable n"


def test_storage_charge_fcr_bounds_guard_zero_capacity():
    """C33: ``eEleFreqUpChargeBound`` / ``eEleFreqDownChargeBound`` divide by
    ``pEleMaxCharge``, so each rule must guard against a zero charge capacity (a
    discharge-only ESS) -- like the e2h analogue -- or it raises ``ZeroDivisionError`` at
    build. Checked at the source: the guard token must appear in each rule body."""
    text = open(MODEL_FORMULATION, encoding="utf-8").read()
    guard = "and model.Par['pEleMaxCharge'][egs][p,sc,n]:"
    for rule in ("eEleFreqUpChargeBound", "eEleFreqDownChargeBound"):
        start = text.index(f"def {rule}(")
        end = text.index(f"rule={rule}", start)
        assert guard in text[start:end], \
            f"{rule} must skip when pEleMaxCharge is zero (divide-by-zero guard)"


def test_hydrogen_standby_columns_optional():
    """C27: ``pHydGenStandByStatus`` / ``pHydGenStandByPower`` must have a missing-column
    default (status 0, power 0), like the FCR columns added in the same feature. A
    hydrogen-generation file without the StandBy columns must still build (standby
    disabled), not ``KeyError``."""
    work = tempfile.mkdtemp(prefix="standby_")
    dst = os.path.join(work, "Home1")
    shutil.copytree(os.path.join(REPO, "data", "H2VPP", "Home1"), dst)
    hpath = os.path.join(dst, "oM_Data_HydrogenGeneration_Home1.csv")
    hg = pd.read_csv(hpath)
    drop = [c for c in hg.columns if "StandBy" in c]
    assert drop, "test assumption: the H2VPP hydrogen generation file has StandBy columns"
    hg.drop(columns=drop).to_csv(hpath, index=False)
    # truncate to a few load levels for a quick build
    dpath = os.path.join(dst, "oM_Data_Duration_Home1.csv")
    dur = pd.read_csv(dpath)
    keep = set(dur[dur.columns[2]].unique()[:6])
    dur.loc[~dur[dur.columns[2]].isin(keep), "Duration"] = float("nan")
    dur.to_csv(dpath, index=False)
    date = datetime.datetime.now().replace(second=0, microsecond=0)
    m = build_model(work, "Home1", date)   # must not raise
    assert (m.Par['pHydGenStandByStatus'] == 0).all(), \
        "standby status must default to 0 when the column is absent"
    assert (m.Par['pHydGenStandByPower'] == 0).all(), \
        "standby draw must default to 0 when the column is absent"


# --- Electrolyser credibility batch (model audit Part C: C3, C4, C6, C10, C11, C13) ---


@pytest.fixture(scope="module")
def standby_model():
    """Build (not solve) the ``ElectrolyserStandby`` variant, where the electrolyser has
    its three-state standby capability switched on."""
    if not os.path.isfile(os.path.join(SIZING_DIR, "ElectrolyserStandby.duckdb")):
        subprocess.run([sys.executable, os.path.join(SIZING_DIR, "make_sizing_cases.py")],
                       check=True, cwd=REPO)
    date = datetime.datetime.now().replace(second=0, microsecond=0)
    return build_model(SIZING_DIR, "ElectrolyserStandby", date)


def test_fcr_down_headroom_is_state_gated():
    """C3: the electrolyser's FCR-down charge headroom must be gated by the commitment and
    use the 2nd-block capacity, so an off/standby unit (commitment 0) gets zero headroom and
    cannot sell down-reserve it could not absorb. It used the bare nameplate
    ``pHydMaxCharge`` with no state gate."""
    text = open(MODEL_FORMULATION, encoding="utf-8").read().splitlines()
    body = [ln for ln in text if "vEleFreqContReserveDisDownCha[p,sc,n,e2h]" in ln
            and "<=" in ln and "vEleTotalCharge2ndBlock" in ln]
    assert body, "could not find the e2h FCR-down headroom rule"
    for ln in body:
        assert "pHydMaxCharge2ndBlock'][e2h][p,sc,n] * optmodel.vHydGenCommitment" in ln, \
            "FCR-down headroom must be pHydMaxCharge2ndBlock * commitment - 2ndBlock"


def test_fcr_down_endurance_binds_without_storage():
    """C3: a node with FCR-flagged electrolysers but no hydrogen store must still build the
    down-endurance constraint (with an empty, zero right-hand side, forcing the down bids to
    zero) rather than skipping it."""
    text = open(MODEL_FORMULATION, encoding="utf-8").read()
    start = text.index("def eEleFreqDownEnduranceConv(")
    end = text.index("rule=eEleFreqDownEnduranceConv", start)
    body = text[start:end]
    assert "if not e2h_at_node:" in body, "endurance must skip only when no e2h at the node"
    assert "not hgs_at_node" not in body, \
        "endurance must not skip a no-store node (its zero headroom forces the down bid to 0)"


def test_standby_only_reachable_when_warm(standby_model):
    """C4: standby must be reachable only from a warm state. The transition constraint
    ``sb[t] <= uc[t-1] + sb[t-1]`` must be built with active rows for the standby-capable
    electrolyser and reference the previous-step commitment and standby variables."""
    m = standby_model
    u = "AEL_01"
    assert m.Par['pHydGenStandByStatus'][u] == 1, "test case electrolyser has no standby"
    con = m.eHydElectrolyserStandByTransition
    assert len(con) > 0, "standby transition constraint has no active rows"
    # pick a non-first load level and check the body ties to the previous step
    p, sc = list(m.ps)[0]
    levels = list(m.n)
    c = con[p, sc, levels[1], u]
    names = {v.name for v in generate_standard_repn(c.body).linear_vars}
    assert any("vHydGenStandBy" in nm for nm in names), "transition must use the standby state"
    assert any("vHydGenCommitment" in nm for nm in names), \
        "transition must reference the previous-step commitment"


def test_retail_settlement_buys_full_electrolyser_load():
    """C6: the retail settlement must subtract the electrolyser's FULL consumption
    (minimum load + 2nd block + standby), not only the 2nd block, so the committed-minimum
    and standby electricity is actually bought -- mirroring the physical eEleBalance."""
    text = open(MODEL_FORMULATION, encoding="utf-8").read()
    start = text.index("def eEleRetNodeBalance(")
    end = text.index("rule=eEleRetNodeBalance", start)
    body = text[start:end]
    assert "vEleTotalCharge[p,sc,n,e2h] for e2h in model.e2h if (er,e2h) in model.r2hg" in body, \
        "retail balance must subtract the full e2h charge"
    assert "vEleTotalCharge2ndBlock[p,sc,n,e2h]" not in body, \
        "retail balance must not use only the e2h 2nd block"


def test_fcr_activation_modulates_electrolyser_charge():
    """C10: an activated FCR bid must change the electrolyser's realised consumption. The
    e2h branch of ``eEleTotalCharge`` must carry the four operating-reserve activation
    terms, like the storage branch above it (it had none)."""
    text = open(MODEL_FORMULATION, encoding="utf-8").read()
    start = text.index("elif egs in model.e2h:")
    end = text.index("def ", start)
    body = text[start:end]
    for act in ["pOperatingReserveActivation_FCRD_Up", "pOperatingReserveActivation_FCRD_Down",
                "pOperatingReserveActivation_FCRN_Up", "pOperatingReserveActivation_FCRN_Down"]:
        assert act in body, f"e2h charge branch is missing the {act} activation term"


def test_electrolyser_startup_cost_billed_outside_hgt():
    """C11: the cold-start cost must be billed for an electrolyser even when it is not in
    ``hgt`` (zero fuel cost). ``eTotalHydGCost`` must add a start-up term over the e2h units
    not in ``hgt``; the cold-start constraints are gated on the start-up cost alone, so the
    cost must match."""
    text = open(MODEL_FORMULATION, encoding="utf-8").read()
    start = text.index("def eTotalHydGCost(")
    end = text.index("rule=eTotalHydGCost", start)
    body = text[start:end]
    assert "vHydGenStartUp" in body and "for e2h in model.e2h if e2h not in model.hgt" in body, \
        "start-up cost must cover e2h units outside hgt"


def test_electrolyser_has_no_ramp_or_mintime_constraint():
    """C13 (documented choice): the electrolyser is a fast-ramping load, so no charge-side
    ramp or minimum up/down-time constraint is imposed at hourly resolution (cycling is
    deterred by the start-up cost + standby). Guard that the output-side ramp/min-time rules
    still exclude e2h and that no e2h-specific ramp rule was added."""
    text = open(MODEL_FORMULATION, encoding="utf-8").read()
    for rule in ["eHydMaxRampUpOutput", "eHydMaxRampDwOutput", "eHydMinUpTime", "eHydMinDownTime"]:
        start = text.index(f"def {rule}(")
        end = text.index(f"rule={rule}", start)
        assert "hgt not in model.e2h" in text[start:end], \
            f"{rule} must keep excluding the electrolyser (pure-load treatment)"


def test_om_variable_cost_counted_once(h2_model):
    """C1: variable O&M must hit output exactly once. It was baked into
    ``pHydGenLinearVarCost`` (``LinearTerm*factor1*FuelCost + OMVariableCost*factor1``)
    AND added again as an explicit term in ``eTotalHydGCost``, so O&M-bearing output paid
    twice -- the electrolyser paid 36.4 instead of 18.2 per kg. ``LinearVarCost`` is now
    the fuel cost only; the explicit term carries O&M (scaled once, which also fixes the
    secondary factor1-squared scaling, since ``OMVariableCost`` is in
    ``idx_gen_factoring``). Only the electrolyser cases (currently ``xfail`` or
    decision-checked, not cost-checked) carry O&M, so no enforced golden moves."""
    m = h2_model
    hg = next((g for g in m.hg if m.Par['pHydGenOMVariableCost'][g]), None)
    assert hg is not None, "test case has no hydrogen generator with an O&M cost"
    # LinearVarCost is the fuel cost only -- no O&M baked in
    fuel_only = float(m.Par['pHydGenLinearTerm'][hg]) * float(m.factor1) \
        * float(m.Par['pHydGenFuelCost'][hg])
    assert float(m.Par['pHydGenLinearVarCost'][hg]) == pytest.approx(fuel_only, rel=1e-9), \
        "pHydGenLinearVarCost must be the fuel cost only (O&M removed from it)"
    # the objective coefficient on hydrogen output is fuel + O&M (once), not fuel + 2*O&M
    p, sc = list(m.ps)[0]
    n = list(m.n)[0]
    om = float(m.Par['pHydGenOMVariableCost'][hg])
    repn = generate_standard_repn(m.eTotalHydGCost[p, sc, n].body)
    out = m.vHydTotalOutput[p, sc, n, hg]
    coef = next((c for v, c in zip(repn.linear_vars, repn.linear_coefs) if v is out), None)
    assert coef is not None, "output variable absent from the hydrogen generation cost"
    # generate_standard_repn runs on the constraint body (LHS - RHS), so the cost
    # coefficient appears negated; compare on magnitude, like test_hydrogen_om_cost_is_added.
    assert abs(coef) == pytest.approx(fuel_only + om, rel=1e-9), \
        f"hydrogen output must pay fuel+O&M once ({fuel_only + om}), got {abs(coef)}"
    # O&M is added in exactly one place per sector in the objective
    form = open(MODEL_FORMULATION, encoding="utf-8").read()
    assert form.count("pEleGenOMVariableCost'") == 1, \
        "electricity O&M must appear exactly once in the objective"
    assert form.count("pHydGenOMVariableCost'") == 1, \
        "hydrogen O&M must appear exactly once in the objective"
    # and it is no longer baked into the LinearVarCost construction
    src = open(INPUT_DATA, encoding="utf-8").read().splitlines()
    lvc = [ln for ln in src if "GenLinearVarCost'" in ln and "GenLinearTerm" in ln]
    assert lvc and all("OMVariableCost" not in ln for ln in lvc), \
        "LinearVarCost must not include O&M (it is added once in the objective)"


# --- C20: green-H2 matching additionality + standby exclusion (RFNBO) ---


@pytest.fixture(scope="module")
def green_model():
    """Build (not solve) the ``ElectrolyserFCR`` variant: green-H2 matching is on, the
    electrolyser is active, and PPA-flagged renewables exist."""
    if not os.path.isfile(os.path.join(SIZING_DIR, "ElectrolyserFCR.duckdb")):
        subprocess.run([sys.executable, os.path.join(SIZING_DIR, "make_sizing_cases.py")],
                       check=True, cwd=REPO)
    date = datetime.datetime.now().replace(second=0, microsecond=0)
    return build_model(SIZING_DIR, "ElectrolyserFCR", date)


def test_green_matching_uses_ppa_pool_and_excludes_standby(green_model):
    """C20: green-H2 matching allocates renewable to the electrolyser over the PPA-flagged
    pool (additionality) and matches only the PRODUCTIVE draw -- the standby draw, which
    makes no hydrogen, is excluded (EU 2023/1184 Art. 6)."""
    m = green_model
    assert hasattr(m, "eGreenH2Matching") and len(m.eGreenH2Matching) > 0, \
        "green matching not built (is matching on for this case?)"
    assert hasattr(m, "vEleResToE2h") and hasattr(m, "eGreenH2AllocCap"), \
        "renewable->electrolyser allocation variable / cap not built"
    # the allocation pool is the PPA-flagged renewables (additionality)
    pool = sorted({idx[-1] for idx in m.vEleResToE2h})
    assert pool, "allocation variable has no generators"
    for g in pool:
        assert int(m.Par["pEleGenPPA"][g]) == 1, \
            f"allocation pool unit {g} is not PPA-flagged (additionality)"
    # the matching body matches the productive draw against the allocation, standby excluded
    p, sc = list(m.ps)[0]
    n = list(m.n)[0]
    names = {v.name for v in generate_standard_repn(m.eGreenH2Matching[p, sc, n].body).linear_vars}
    assert any("vEleResToE2h" in nm for nm in names), "matching must use the allocation variable"
    assert any("vEleTotalCharge" in nm for nm in names), \
        "matching must reference the electrolyser consumption"
    # standby exclusion is checked at the source: in this case the electrolyser has standby
    # off, so the (fixed-to-zero) standby variable folds out of the constraint body, but the
    # rule must subtract the standby draw so a standby-capable unit is matched on its
    # productive draw only.
    grn = open(os.path.join(MODULES, "oM_GreenHydrogen.py"), encoding="utf-8").read()
    start = grn.index("def eGreenH2Matching(")
    end = grn.index("optmodel.__setattr__('eGreenH2Matching'", start)
    assert "pHydGenStandByPower" in grn[start:end] and "vHydGenStandBy" in grn[start:end], \
        "matching rule must subtract the standby draw (productive draw only)"
