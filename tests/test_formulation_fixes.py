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

import numpy as np
import pandas as pd
import pyomo.environ as pyo
import pytest
from pyomo.environ import ConcreteModel, Set
from pyomo.repn import generate_standard_repn

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(REPO, "src"))
from el1xr_opt.Modules.oM_Sequence import build_model, routine  # noqa: E402

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


def test_initial_uc_carryover_guarded_by_uptime_zero():
    """C9: the pre-horizon min-up/min-down carry-over must only fire for a unit that was
    actually on (``UpTimeZero > 0``) resp. off (``DownTimeZero > 0``) before the horizon.
    ``UpTime - UpTimeZero > 0`` alone is true for a never-on unit (``UpTimeZero == 0``),
    which would force ``pInitialUC = 1`` and override the merit-order pre-commitment. Both
    carriers must carry the ``...TimeZero > 0`` guard."""
    lines = open(INPUT_DATA, encoding="utf-8").read().splitlines()
    for token in ("UpTime", "DownTime"):
        for carrier in ("Ele", "Hyd"):
            # the carry-over `if` condition references both the requirement and the
            # pre-horizon counter for the carrier/state
            cond = [ln for ln in lines
                    if ln.lstrip().startswith("if ")
                    and f"p{carrier}Gen{token}'][" in ln
                    and f"p{carrier}Gen{token}Zero'][" in ln]
            assert cond, f"missing {carrier} {token} carry-over condition"
            for ln in cond:
                assert f"p{carrier}Gen{token}Zero'][" in ln.split(" and ")[0], \
                    f"{carrier} {token} carry-over must be guarded by {token}Zero > 0 first"


def test_fixed_consumption_electrolyser_charge_is_defined():
    """C12: a fixed-consumption electrolyser (MinCharge == MaxCharge, so the 2nd block is
    empty) must still have its total charge defined by commitment (MinCharge * uc + standby),
    not left free. eEleTotalCharge needs a fixed-consumption branch, and the unused 2nd-block
    charge must be pinned to zero."""
    text = open(MODEL_FORMULATION, encoding="utf-8").read()
    start = text.index("def eEleTotalCharge(")
    body = text[start:text.index("optmodel.__setattr__('eEleTotalCharge'", start)]
    assert "elif model.Par['pHydMaxCharge'][egs][p,sc,n]:" in body, \
        "eEleTotalCharge needs a fixed-consumption (empty 2nd block) e2h branch (C12)"
    assert "pHydMinCharge'][egs][p,sc,n] * optmodel.vHydGenCommitment[p,sc,n,egs]" in body, \
        "the fixed-consumption charge must be MinCharge * commitment (+ standby) (C12)"
    data = open(INPUT_DATA, encoding="utf-8").read()
    assert "pHydMaxCharge2ndBlock'][idx[-1]][idx[:3]] == 0" in data \
        and "vEleTotalCharge2ndBlock[idx].fix(0.0)" in data, \
        "the unused 2nd-block charge of a fixed-consumption electrolyser must be pinned to 0 (C12)"


def test_total_degradation_cost_fixed_only_if_no_unit_degrades():
    """C22: the total electricity degradation cost may be fixed to zero only when NO storage
    unit has DoD segments. Fixing it whenever ANY single unit lacks DoD (inside the per-unit
    loop) erased a degrading unit's cost or made a mixed fleet infeasible -- it must be gated
    by an aggregate ``all(...)`` over the units."""
    text = open(INPUT_DATA, encoding="utf-8").read()
    i = text.index("fixing storage variables related to depth of discharge")
    block = text[i:i + 1200]
    assert "all((model.Par['pEleGenDoDS1'][egs]" in block, \
        "the vTotalEleDCost fix must be gated by all(... for egs in model.egs) (C22)"
    # the total-cost fix must sit before the per-unit loop, not inside it
    all_pos = block.index("all((model.Par['pEleGenDoDS1']")
    loop_pos = block.index("for egs in model.egs:")
    fix_pos = block.index("vTotalEleDCost')[idx].fix(0.0)")
    assert all_pos < loop_pos and fix_pos < loop_pos, \
        "the vTotalEleDCost fix must be aggregated before the per-unit loop, not inside it (C22)"


def test_volumetric_grid_charges_are_duration_weighted():
    """C15a: the volumetric grid fee, energy tax and incentive revenue are per-kWh
    charges on the per-level import/export power, aggregated as ``ps`` (no pDuration in
    the registry). Each must therefore weight its inner sum over n by ``pDuration`` to
    count energy, or it undercounts by the time-step factor when pParTimeStep > 1."""
    text = open(MODEL_FORMULATION, encoding="utf-8").read()
    for rule in ("eTotalEleNetUseVarCost", "eEleTaxEnergyCost", "eEleTaxISRevenue"):
        start = text.index(f"def {rule}(")
        body = text[start:text.index("optmodel.__setattr__", start)]
        assert "pDuration'][p,sc,n]" in body or "pDuration'][p, sc, n]" in body, \
            f"{rule} must weight the per-level import/export by pDuration (C15a)"


def test_fcr_revenue_price_not_double_factor1_scaled():
    """C16: ``pOperatingReservePrice_*`` is factor1-scaled at read (oM_InputData), like
    the day-ahead energy price, so the FCR revenue constraints must NOT multiply by
    ``model.factor1`` again -- that squared factor1 on the unit knob."""
    text = open(MODEL_FORMULATION, encoding="utf-8").read()
    for rule in ("eEleMarketFCRDUpRevenue", "eEleMarketFCRDDwRevenue", "eEleMarketFCRNRevenue"):
        start = text.index(f"def {rule}(")
        body = text[start:text.index("optmodel.__setattr__", start)]
        assert "OperatingReservePrice" in body, f"{rule} body not found as expected"
        assert "model.factor1" not in body, \
            f"{rule} must not re-apply model.factor1 (price already scaled at read) (C16)"


def test_fcr_revenue_paid_only_over_backed_providers():
    """C17: the FCR revenue must be paid over the backed providers (egt / egs / e2h) --
    the same sets the caps and provisions cover -- not over all of egnr. A non-RES unit
    that is neither thermal nor storage has a free bid, no cap and no provision, so paying
    it (via egnr) makes the objective unbounded."""
    text = open(MODEL_FORMULATION, encoding="utf-8").read()
    for rule in ("eEleMarketFCRDUpRevenue", "eEleMarketFCRDDwRevenue", "eEleMarketFCRNRevenue"):
        start = text.index(f"def {rule}(")
        body = text[start:text.index("optmodel.__setattr__", start)]
        assert "for egnr in model.egnr" not in body, \
            f"{rule} must not pay revenue over all of egnr (unbounded objective) (C17)"
        for s in ("for egt in model.egt", "for egs in model.egs", "for e2h in model.e2h"):
            assert s in body, f"{rule} must pay revenue over the backed set ({s}) (C17)"


def test_ele_fcr_flags_default_to_not_participating():
    """C17: ``pEleGenNoFCRD`` / ``pEleGenNoFCRN`` must get ``.fillna(1)`` (like the e2h
    flags), so a blank cell defaults to 'not participating' instead of NaN -- a NaN flag
    is neither 0 nor 1, letting the unit escape the bid fixing and every FCR constraint
    while still being paid revenue."""
    text = open(INPUT_DATA, encoding="utf-8").read()
    for flag in ("pEleGenNoFCRD", "pEleGenNoFCRN"):
        line = next((ln for ln in text.splitlines()
                     if f"parameters_dict['{flag}'" in ln and ".map(idxDict)" in ln), "")
        assert ".fillna(1)" in line, \
            f"{flag} must default a blank cell to 1 (not participating) via fillna(1) (C17)"


def test_discharge_reserve_bounded_by_discharge_rating():
    """C18: the discharge-headroom fallback (for a NoDayAhead or zero-MaxPower unit) must
    bound the discharge reserve by the DISCHARGE rating (pEleMaxPower), not the charge
    rating (pEleMaxCharge) -- otherwise a non-dischargeable unit sells phantom discharge
    reserve on its charger rating."""
    text = open(MODEL_FORMULATION, encoding="utf-8").read()
    for rule in ("eEleFreqUpDischargeHeadroom", "eEleFreqDownDischargeHeadroom"):
        start = text.index(f"def {rule}(")
        body = text[start:text.index("optmodel.__setattr__", start)]
        # the Dis...Dis + Nor...Dis fallback must not bound by the charge rating
        fallback = [ln for ln in body.splitlines()
                    if "ReserveDis" in ln and "Dis[p,sc,n,egs]" in ln and "<=" in ln
                    and "pEleMaxCharge" in ln]
        assert not fallback, \
            f"{rule} must not bound the discharge reserve by pEleMaxCharge (C18)"


def test_candidate_hydrogen_storage_charge_capped_by_build():
    """C21a: a candidate hydrogen storage unit's charge must be capped by its build
    decision (like electricity storage), so an unbuilt store cannot absorb at nameplate."""
    text = open(INVESTMENT, encoding="utf-8").read()
    assert "def eHydInvestMaxStorageCharge(" in text, \
        "missing the candidate hydrogen-storage charge cap (C21a)"
    start = text.index("def eHydInvestMaxStorageCharge(")
    body = text[start:text.index("optmodel.__setattr__", start)]
    assert "vHydTotalCharge[p, sc, n, hgsc]" in body and "vHydGenInvest[hgsc]" in body, \
        "the cap must bound vHydTotalCharge by pHydMaxCharge * build fraction (C21a)"


def test_candidate_fcr_down_headroom_limited_by_build():
    """C21b: the FCR-down charge headroom of a candidate unit must be limited by the build
    fraction, not the full nameplate. Storage scales the nameplate by vEleGenInvest in
    place; the electrolyser gets a separate build-cap constraint (the in-place version
    would be bilinear with the commitment)."""
    text = open(MODEL_FORMULATION, encoding="utf-8").read()
    # storage: the candidate branch scales pEleMaxCharge by the build fraction
    start = text.index("def eEleFreqDownChargeHeadroom(")
    body = text[start:text.index("optmodel.__setattr__", start)]
    assert "model.egsc" in body and "pEleMaxCharge'][egs][p,sc,n] * optmodel.vEleGenInvest[egs]" in body, \
        "candidate storage down-charge headroom must scale by vEleGenInvest (C21b)"
    # electrolyser: a separate build-cap constraint bounds the reserve by the build fraction
    assert "def eEleFreqDownChargeHeadroomConvInvest(" in text, \
        "missing the candidate electrolyser FCR-down build cap (C21b)"
    start = text.index("def eEleFreqDownChargeHeadroomConvInvest(")
    body = text[start:text.index("optmodel.__setattr__", start)]
    assert "vHydGenInvest[e2h]" in body and "e2h in model.hgc" in body, \
        "candidate electrolyser FCR-down build cap must bound by vHydGenInvest (C21b)"


def test_storage_var_bounds_not_read_factor1_scaled():
    """C24: ``pVarMinStorage`` / ``pVarMaxStorage`` must be read unscaled, because the
    single factor1 unit conversion is applied later at the inventory-bound and
    investment-cap sites (matching the GenMaximumStorage fallback and the initial
    inventory). Scaling them at read too double-counts factor1 on the VarStorage path."""
    text = open(INPUT_DATA, encoding="utf-8").read()
    start = text.index("Extract and cast generation parameters")
    body = text[start:text.index("model.retail_frames_suffixes", start)]
    assert "'VarMinStorage', 'VarMaxStorage'" in body, \
        "the storage Var suffixes must be excluded from the factor1 read-scaling (C24)"


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
    # the commitment-gated headroom (exclude the separate C21b build-cap line, which
    # bounds the same reserve by the build fraction rather than the commitment)
    body = [ln for ln in text if "vEleFreqContReserveDisDownCha[p,sc,n,e2h]" in ln
            and "<=" in ln and "vEleTotalCharge2ndBlock" in ln
            and "vHydGenInvest" not in ln]
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
    ``hgt`` (zero fuel cost). The start-up term over the e2h units not in ``hgt`` now lives
    in ``eTotalHydSUCost`` (moved out of GCost by C15b); the cold-start constraints are
    gated on the start-up cost alone, so the cost must match."""
    text = open(MODEL_FORMULATION, encoding="utf-8").read()
    start = text.index("def eTotalHydSUCost(")
    end = text.index("rule=eTotalHydSUCost", start)
    body = text[start:end]
    assert "vHydGenStartUp" in body and "for e2h in model.e2h if e2h not in model.hgt" in body, \
        "start-up cost must cover e2h units outside hgt"


def test_startup_cost_is_not_duration_weighted():
    """C15b: per-event start-up / shut-down costs must NOT be duration-weighted. They are
    moved out of the psn-aggregated GCost into a separate ps term (eTotal{Ele,Hyd}SUCost)
    that sums over n without pDuration, and the SU terms are registered as 'ps' so the
    objective does not multiply them by pDuration."""
    text = open(MODEL_FORMULATION, encoding="utf-8").read()
    # start-up / shut-down are gone from the duration-weighted generation cost
    for rule in ("eTotalEleGCost", "eTotalHydGCost"):
        start = text.index(f"def {rule}(")
        body = text[start:text.index(f"rule={rule}", start)]
        assert "StartUp" not in body and "ShutDown" not in body, \
            f"{rule} must not carry the per-event start-up/shut-down cost (C15b)"
    # the new ps terms carry them and apply no pDuration
    for rule in ("eTotalEleSUCost", "eTotalHydSUCost"):
        start = text.index(f"def {rule}(")
        body = text[start:text.index(f"rule={rule}", start)]
        assert "StartUp" in body and "ShutDown" in body, \
            f"{rule} must sum the start-up and shut-down costs"
        assert "pDuration" not in body, \
            f"{rule} is a per-event cost and must not be weighted by pDuration (C15b)"
    # both are registered as 'ps' (not duration-weighted) in the objective registry
    feat = open(os.path.join(MODULES, "oM_Features.py"), encoding="utf-8").read()
    seed = feat[feat.index("def seed_objective_registry("):feat.index("def aggregate_terms(")]
    for name in ("vTotalEleSUCost", "vTotalHydSUCost"):
        pos = seed.find(name)
        assert pos != -1, f"{name} is not registered in seed_objective_registry (C15b)"
        # the name sits in a `for name in (...): register_cost(model, name, "ps")` block;
        # the register_cost call follows within the same block
        window = seed[pos:pos + 200]
        assert 'register_cost(model, name, "ps")' in window, \
            f"{name} must be registered as a 'ps' cost term (C15b)"


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


# --- Hydrogen-case enablement batch (model audit Part C: C7, C19, C23, C41, C43) ---
# These harden the hydrogen path so a real hydrogen case builds and prices
# correctly. They are latent in the shipped non-hydrogen cases (no hydrogen storage,
# no active hydrogen retailer, no flexible hydrogen demand), so the enforced goldens
# are unchanged; they are guarded on the H2Tank build or at the source.


def test_hydrogen_charge_upper_bound_is_applied(h2_model):
    """C23: the hydrogen-charge bound loop tested ``idx in model.hg`` with ``idx`` the full
    ``(p,sc,n,unit)`` tuple -- always False -- so ``vHydTotalCharge`` got no upper bound. It
    must test ``idx[-1]`` (the unit), like the electricity loop, so a storage unit's charge
    is capped by ``pHydMaxCharge``."""
    m = h2_model
    assert len(m.hgs) > 0, "test case has no hydrogen storage unit"
    p, sc = list(m.ps)[0]
    hgs = list(m.hgs)[0]
    capped = False
    for n in m.n:
        idx = (p, sc, n, hgs)
        if idx in m.vHydTotalCharge:
            ub = m.vHydTotalCharge[idx].ub
            assert ub is not None, "hydrogen storage charge has no upper bound (C23)"
            assert ub == pytest.approx(float(m.Par['pHydMaxCharge'][hgs][p, sc, n])), \
                "hydrogen storage charge ub must equal pHydMaxCharge"
            capped = True
    assert capped, "no hydrogen storage charge variable was found to check"


def test_hydrogen_import_export_closed_without_priced_retailer(h2_model):
    """C7: hydrogen import/export carry no cost and are linked to a buy/sell only by the
    retail composition constraints (gated by pHydRetMaxBuy/Sell > 0). vHydImport/Export
    must be fixed to zero at every node with no active priced hydrogen retailer, and left
    free only where the composition constraint prices them (H2Tank has its retailer at
    Node2, so Node2 imports are priced and every other node stays closed)."""
    m = h2_model
    buy_nodes = {m.Par['pHydRetNode'][hr] for hr in m.hr if m.Par['pHydRetMaxBuy'][hr] > 0}
    sell_nodes = {m.Par['pHydRetNode'][hr] for hr in m.hr if m.Par['pHydRetMaxSell'][hr] > 0}
    assert buy_nodes, "test case has no priced hydrogen retailer (redesigned H2Tank should)"
    assert len(m.vHydImport) > 0, "no hydrogen import variable to check"
    checked_closed = False
    for idx in m.vHydImport:
        if idx[-1] in buy_nodes:
            assert not m.vHydImport[idx].fixed, \
                f"vHydImport{idx} must stay free at a priced retailer node"
        else:
            assert m.vHydImport[idx].fixed and float(m.vHydImport[idx].value or 0.0) == 0.0, \
                f"vHydImport{idx} must be fixed to zero with no priced hydrogen retailer (C7)"
            checked_closed = True
    assert checked_closed, "no unpriced node was found to check the import is closed"
    for idx in m.vHydExport:
        if idx[-1] not in sell_nodes:
            assert m.vHydExport[idx].fixed and float(m.vHydExport[idx].value or 0.0) == 0.0, \
                f"vHydExport{idx} must be fixed to zero with no priced hydrogen retailer (C7)"


def test_retail_max_buy_sell_have_missing_column_default():
    """C43: the per-step buy/sell caps (MaxBuy/MaxSell) and the peak-tariff type
    (TariffType) are optional retail columns. When a retail file omits them,
    ``pRetMaxBuy/Sell`` must default to 0.0 ("no cap") and ``pRetTariffType`` to ''
    ("no peak tariff"), otherwise activating a retailer on the column-less file raises
    ``KeyError``. Checked by dropping the columns from a copied file and rebuilding."""
    work = tempfile.mkdtemp(prefix="retailcap_")
    dst = os.path.join(work, "Home1")
    shutil.copytree(os.path.join(REPO, "data", "H2VPP", "Home1"), dst)
    for sector in ("Hydrogen", "Electricity"):
        rpath = os.path.join(dst, f"oM_Data_{sector}Retail_Home1.csv")
        rt = pd.read_csv(rpath)
        drop = [c for c in rt.columns if c in ("MaxBuy", "MaxSell", "TariffType")]
        if drop:
            rt.drop(columns=drop).to_csv(rpath, index=False)
    # truncate to a few load levels for a quick build
    dpath = os.path.join(dst, "oM_Data_Duration_Home1.csv")
    dur = pd.read_csv(dpath)
    keep = set(dur[dur.columns[2]].unique()[:6])
    dur.loc[~dur[dur.columns[2]].isin(keep), "Duration"] = float("nan")
    dur.to_csv(dpath, index=False)
    date = datetime.datetime.now().replace(second=0, microsecond=0)
    m = build_model(work, "Home1", date)   # must not raise
    for key in ("pHydRetMaxBuy", "pHydRetMaxSell", "pEleRetMaxBuy", "pEleRetMaxSell"):
        assert key in m.Par, f"{key} missing -- no schema default for the optional column (C43)"
        assert (m.Par[key] == 0.0).all(), \
            f"{key} must default to 0.0 when the MaxBuy/MaxSell column is absent"
    for key in ("pHydRetTariffType", "pEleRetTariffType"):
        assert key in m.Par, f"{key} missing -- no default for the optional TariffType column"
        assert (m.Par[key] == "").all(), \
            f"{key} must default to '' (no peak tariff) when the TariffType column is absent"


def test_balance_guards_include_demand():
    """C19: the build guards of ``eEleBalance`` / ``eHydBalance`` counted units and lines but
    not demands, so a node carrying only demand was skipped and its demand silently dropped
    at zero cost. The guards must count demand (``ed2n`` / ``hd2n``)."""
    text = open(MODEL_FORMULATION, encoding="utf-8").read()
    ele_start = text.index("def eEleBalance(")
    ele_guard = text[ele_start:text.index("return", ele_start)]
    assert "ed2n[nd]" in ele_guard, "eEleBalance guard must count electricity demand (ed2n)"
    hyd_start = text.index("def eHydBalance(")
    hyd_guard = text[hyd_start:text.index("return", hyd_start)]
    assert "hd2n[nd]" in hyd_guard, "eHydBalance guard must count hydrogen demand (hd2n)"


def test_hydrogen_not_served_capped_by_demand():
    """C41: hydrogen-not-served must not exceed the scheduled hydrogen demand, otherwise
    ``vHydDemand - vHNS`` goes negative and a flexible demand node becomes a paid hydrogen
    sink. A constraint must cap ``vHNS <= vHydDemand`` for flexible hydrogen demand."""
    text = open(MODEL_FORMULATION, encoding="utf-8").read()
    assert "def eHydNotServedCap(" in text, "the hydrogen-not-served cap rule is missing (C41)"
    start = text.index("def eHydNotServedCap(")
    end = text.index("rule=eHydNotServedCap", start)
    body = text[start:end]
    assert "pHydDemFlexible" in body, "the cap must gate on flexible hydrogen demand"
    assert "vHNS[p,sc,n,hd] <= optmodel.vHydDemand[p,sc,n,hd]" in body, \
        "the cap must constrain vHNS <= vHydDemand"


# --- C26: compressor consumption draws electricity on hydrogen-store charging ---


def test_compressor_draws_electricity_on_store_charging(h2_model):
    """C26: ``MaxCompressorConsumption`` was read but referenced nowhere, so charging a
    hydrogen store cost no compression energy. The store's charge must now enter its node's
    ``eEleBalance`` as a load: the coefficient on ``vHydTotalCharge`` is the negative
    compressor rate (electricity per unit of hydrogen charged)."""
    m = h2_model
    stores = [g for g in m.hgs if float(m.Par['pHydGenMaxCompressorConsumption'][g]) > 0]
    assert stores, "test case has no hydrogen store with a compressor rate"
    g = stores[0]
    rate = float(m.Par['pHydGenMaxCompressorConsumption'][g])
    nd = next(node for (node, u) in m.n2hg if u == g)
    p, sc = list(m.ps)[0]
    found = False
    for n in m.n:
        if (p, sc, n, nd) in m.eEleBalance:
            repn = generate_standard_repn(m.eEleBalance[p, sc, n, nd].body)
            pairs = list(zip(repn.linear_vars, repn.linear_coefs))
            ch = m.vHydTotalCharge[p, sc, n, g]
            comp = next((c for v, c in pairs if v is ch), None)
            assert comp is not None, \
                "store charge absent from the electricity balance (compressor not wired)"
            assert abs(comp) == pytest.approx(rate), \
                f"compressor coefficient magnitude must be the rate {rate}, got {abs(comp)}"
            # confirm it acts as a LOAD: same sign as the electrolyser's electricity draw
            # (another load) at this node, whichever way Pyomo normalised the body.
            e2h_load = next((c for v, c in pairs
                             if "vEleTotalCharge" in v.name and "AEL" in v.name), None)
            if e2h_load is not None:
                assert (comp > 0) == (e2h_load > 0), \
                    "compressor term must enter the balance as a load, like the electrolyser draw"
            found = True
            break
    assert found, "no active electricity balance at the store's node"


# --- Hydrogen-retailer activation bugs (found enabling the H2Tank/Electrolyser cases) ---
# The first case with an active hydrogen retailer (MaximumEnergyBuy > 0) hit two
# latent crashes: pHydRetTariffType was never created (the hydrogen retail file has
# no TariffType column -- covered by the optional-column default test above), and the
# hydrogen peak-indicator variables were declared over the *electricity* retail sets
# (psner/psder/psdner), so the hydrogen fixing loops raised KeyError the moment the
# hydrogen and electricity retailer sets differed.


def test_hydrogen_peak_indicators_on_hydrogen_sets(h2_model):
    """The hydrogen peak-hour indicators must be indexed by the hydrogen retailers
    (psnhr/psdhr/psdnhr), not the electricity ones. On H2Tank the two retailer sets
    differ (EleR_01 vs HydR_01), so a wrong-set declaration cannot hide."""
    m = h2_model
    hr = set(m.hr)
    er = set(m.er)
    assert hr and hr != er, "fixture must have distinct electricity/hydrogen retailers"
    for vname in ("vHydPeakGlobalInd", "vHydPeakMonthInd", "vHydPeakDayInd"):
        var = getattr(m, vname)
        rets = {idx[-1] if vname == "vHydPeakDayInd" else idx[-2] for idx in var}
        assert rets <= hr, \
            f"{vname} is indexed by {sorted(rets - hr)} -- not hydrogen retailers"
        assert not (rets & (er - hr)), f"{vname} carries electricity retailers"


# --- 2026-06 audit batch 1: dead / vacuous logic cleanup --------------------
# C28 eE2HMinCharge2ndBlock vacuous (documented, non-binding by design);
# C29 reserve-require gates flipped >=0 -> >0; C32 RES FCR bid vars fixed to 0;
# C42 misleading "2Commitment" docs corrected; C45 tautological NoDayAhead conjunct removed.


def test_reserve_require_gates_use_strict_positive():
    """C29: the per-unit FCR build gates tested ``pOperatingReserveRequire_* >= 0``,
    always true for a fillna(0), clamped parameter, so they built dead rows at zero-
    requirement levels. They must test ``> 0`` so a zero requirement skips the row (the
    requirement cap still binds the bids to zero)."""
    text = open(MODEL_FORMULATION, encoding="utf-8").read()
    import re
    bad = re.findall(r"pOperatingReserveRequire_[A-Za-z_]+'\]\[p,sc,n\]\s*>=\s*0", text)
    assert not bad, f"reserve-require gates still use '>= 0' (C29): {bad[:3]}"
    good = re.findall(r"pOperatingReserveRequire_[A-Za-z_]+'\]\[p,sc,n\]\s*>\s*0", text)
    assert len(good) >= 20, f"expected the reserve-require gates to use '> 0' (C29), found {len(good)}"


def test_res_fcr_bid_variables_are_fixed(h2_model):
    """C32: RES generators (egr) carry FCR bid variables (declared over eg) but appear in
    no cap, relation, or revenue term. They must be fixed to zero so they cannot carry
    arbitrary values into the result tables."""
    m = h2_model
    assert len(m.egr) > 0, "fixture has no RES generator"
    p, sc = list(m.ps)[0]
    n = list(m.n)[0]
    egr = list(m.egr)[0]
    for vname in ("vEleFreqContReserveDisUpwardBid", "vEleFreqContReserveDisDownwardBid",
                  "vEleFreqContReserveNorBid"):
        v = getattr(m, vname)[p, sc, n, egr]
        assert v.fixed and v.value == 0.0, \
            f"{vname}[{egr}] must be fixed to 0 for a RES unit (C32)"


def test_no_tautological_nodayahead_conjunct():
    """C45: the ESS 2nd-block bounds gated on
    ``(pEleGenNoDayAhead == 1 or pEleGenNoDayAhead == 0)`` -- a binary, so always true --
    making the binary-gated branch unreachable. The dead conjunct is removed (behaviour is
    unchanged; mutual exclusion still holds via the charge/discharge decisions)."""
    text = open(MODEL_FORMULATION, encoding="utf-8").read()
    assert "pEleGenNoDayAhead'][egs] == 1 or model.Par['pEleGenNoDayAhead'][egs] == 0" not in text, \
        "the always-true NoDayAhead conjunct must be removed (C45)"


def test_inflow_outflow_bound_docs_not_commitment():
    """C42: the eEle/eHyd Max/Min In/Outflows2Commitment constraints bound the in/outflow
    variable by a parameter limit -- there is no commitment variable. The misleading
    'to commitment' doc string is corrected (the attribute name is retained on purpose)."""
    text = open(MODEL_FORMULATION, encoding="utf-8").read()
    assert "to commitment [p.u.]" not in text, \
        "the misleading 'to commitment' doc must be corrected (C42)"


# --- 2026-06 audit batch 2: load-time warnings & relabels -------------------
# C34 peak cost is a constant offset at zero peaks; C35 standby needs binary UC;
# C36 ignored electrolyser shut-down cost; C39 dropped future-dated unit;
# C44 misattributed hydrogen day-ahead constraint name.


def test_batch2_warnings_present():
    """C34/C35/C36/C39: each is a byte-safe load-time warning (no model change). Guard that
    the warning and its triggering condition are wired in oM_InputData."""
    text = open(INPUT_DATA, encoding="utf-8").read()
    assert "WARNING (C34)" in text and "pParNumberPowerPeaks'] == 0" in text, "C34 warning missing"
    assert "WARNING (C35)" in text and "pOptIndBinGenOperat'] == 0" in text, "C35 warning missing"
    assert "WARNING (C36)" in text and "pHydGenShutDownCost'][e2h] > 0" in text, "C36 warning missing"
    assert "WARNING (C39)" in text and "InitialPeriod'][_g] > _base_year" in text, "C39 warning missing"


def test_hydrogen_day_ahead_constraint_name_matches_rule(h2_model):
    """C44: the hydrogen day-ahead buy cost constraint was registered as
    ``eTotalHydTradeCost`` while its rule is ``eHydMarketDayAheadCost`` -- a name-grep
    mismatch. The attribute is now named after its rule, mirroring the electricity analogue
    ``eEleMarketDayAheadCost``."""
    m = h2_model
    assert hasattr(m, "eHydMarketDayAheadCost"), \
        "hydrogen day-ahead cost constraint must be named eHydMarketDayAheadCost (C44)"
    assert not hasattr(m, "eTotalHydTradeCost"), \
        "the misattributed name eTotalHydTradeCost must be gone (C44)"
    # the electricity analogue it now mirrors
    assert hasattr(m, "eEleMarketDayAheadCost")


# --- 2026-06 audit batch 3: parameter correctness --------------------------
# C30 terminal-level endurance backing; C31 FCR-N cap uses min not avg;
# C37 H2 storage ramp reuse documented; C46 per-unit pre-horizon ramp output.


def test_first_step_ramp_uses_per_unit_initial_output():
    """C46: the first-step thermal ramp used the scalar system aggregate pEleSystemOutput
    (overwritten across (p,sc), so only the last scenario survived) as every unit's
    pre-horizon output. It must use the unit's own pEleInitialOutput[p,sc,egt]."""
    text = open(MODEL_FORMULATION, encoding="utf-8").read()
    # within the two first-step ramp branches, the system aggregate must be gone
    for rule in ("eEleMaxRampUpOutput", "eEleMaxRampDwOutput"):
        start = text.index(f"def {rule}(")
        body = text[start:text.index(f"rule={rule}", start)]
        assert "pEleSystemOutput" not in body, f"{rule} must not use the system aggregate (C46)"
        assert "pEleInitialOutput'][p,sc,egt]" in body, \
            f"{rule} must use the per-unit pre-horizon output (C46)"


def test_fcrn_volume_cap_uses_minimum_not_average():
    """C31: the FCR-N volume cap (a symmetric product) must bound the bids by the MINIMUM of
    the up/down requirements, not their average. The price average (FCR-N revenue) is a
    separate, legitimate term and is left untouched."""
    text = open(MODEL_FORMULATION, encoding="utf-8").read()
    start = text.index("def eEleFreqContReserveNor(")
    body = text[start:text.index("rule=eEleFreqContReserveNor", start)]
    assert "min(model.Par['pOperatingReserveRequire_FCRN_Up']" in body, \
        "FCR-N volume cap must use min(up, down) (C31)"
    assert "Require_FCRN_Down'][p,sc,n]) / 2" not in body, \
        "FCR-N volume cap must not use the average (C31)"


def test_terminal_endurance_constraints_exist(green_model):
    """C30: the rolling endurance constraints leave the last load level's FCR bid unbacked.
    Terminal-level endurance constraints must exist so end-of-horizon bids are energy-backed.
    On ElectrolyserFCR the e2h node-level terminal constraint is built with active rows."""
    m = green_model
    for name in ("eEleStorageEnduranceUpEnd", "eEleStorageEnduranceDownEnd",
                 "eEleFreqDownEnduranceConvEnd"):
        assert hasattr(m, name), f"terminal endurance constraint {name} missing (C30)"
    assert len(m.eEleFreqDownEnduranceConvEnd) > 0, \
        "the e2h terminal endurance has no active rows on ElectrolyserFCR (C30)"
    # the terminal rows reference the LAST load level
    last = m.n.last()
    assert any(idx[2] == last for idx in m.eEleFreqDownEnduranceConvEnd), \
        "terminal endurance must bind the last load level (C30)"


def test_h2_storage_ramp_reuse_is_documented():
    """C37: the hydrogen storage charge/outflow ramp reuses the generation ramp parameter;
    this is documented as a known data-schema limitation with a dedicated-parameter follow-up."""
    text = open(MODEL_FORMULATION, encoding="utf-8").read()
    assert "Audit C37" in text and "pHydGenOutflowsRamp" in text, \
        "the C37 ramp-reuse limitation must be documented at the H2 charge ramp"


# --- 2026-06 audit batch 4: investment dimensional convention --------------


def test_investment_cost_unit_label_consistent():
    """C38: vTotalICost is added directly to the [EUR] operating-cost components in
    eTotalSCost, so its unit must be EUR -- the [MEUR] label was wrong."""
    inv = open(INVESTMENT, encoding="utf-8").read()
    assert "investment cost [EUR]" in inv, "vTotalICost must be labelled [EUR] (C38)"
    assert "investment cost [MEUR]" not in inv, "the wrong [MEUR] label must be gone (C38)"
    obj = open(MODEL_FORMULATION, encoding="utf-8").read()
    assert "Total system cost [EUR]" in obj, "the objective unit label must be [EUR] to match (C38)"


def test_factor1_default_is_one(h2_model):
    """C38: factor1 defaults to 1.0 (so the goldens are byte-unchanged) and is settable via the
    FACTOR1 module global for the invariance test and a future dfParameter input."""
    assert float(h2_model.factor1) == 1.0, "factor1 must default to 1.0 (byte-unchanged goldens)"
    import el1xr_opt.Modules.oM_InputData as _ID
    assert _ID.FACTOR1 == 1.0, "the FACTOR1 module-global default must be 1.0"


@pytest.mark.solve
def test_factor1_invariant():
    """C38: factor1 is a TRUE unit conversion -- it scales extensive quantities by factor1 and
    per-quantity prices by 1/factor1, leaving fixed charges / investment / ratios unscaled, so
    the optimum (total cost) is INVARIANT. Verified on Home1 with the peak-demand tariff ENABLED:
    the discrete peak-tariff MILP is scale-invariant too (the selected peak hours are unchanged
    under a uniform unit rescaling, and tariff/factor1 x peak-quantity*factor1 is invariant), so
    no peak component is excluded. Solving at FACTOR1=1 and FACTOR1=2 must give the same total
    system cost."""
    import el1xr_opt.Modules.oM_InputData as _ID
    src = os.path.join(REPO, "src", "el1xr_opt", "Home1")
    work = tempfile.mkdtemp(prefix="f1inv_")
    dst = os.path.join(work, "Home1")
    shutil.copytree(src, dst)
    # truncate to one week so the solve is fast
    dur = os.path.join(dst, "oM_Data_Duration_Home1.csv")
    dd = pd.read_csv(dur, index_col=[0, 1, 2])
    dd.iloc[168:, dd.columns.get_loc("Duration")] = np.nan
    dd.to_csv(dur)

    def _cost(f1):
        _ID.FACTOR1 = f1
        try:
            m = routine(dir=work, case="Home1", solver="highs",
                        date=datetime.datetime.now().replace(second=0, microsecond=0),
                        rawresults="False", plots="False", indlog="False", duckdbresults="False")
        finally:
            _ID.FACTOR1 = 1.0
        return float(pyo.value(m.eTotalSCost))

    c1 = _cost(1.0)
    c2 = _cost(2.0)
    assert abs(c2 - c1) <= 1e-5 * max(1.0, abs(c1)), \
        f"factor1 must leave the optimum invariant: cost {c1} (f1=1) vs {c2} (f1=2)"
