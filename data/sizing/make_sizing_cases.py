"""Generate the small CI validation cases from the H2VPP base case.

Each case is a short, linear (LP) variation of the H2VPP case that exercises one
feature, so its cost is reproducible in CI. To keep the repository small, each
case is committed as a single ``<Case>.duckdb`` file (the model reads it through
the same interface as a CSV folder); this script is the readable source that
produces them. Re-run it after changing an assumption:

    python data/sizing/make_sizing_cases.py

Cases (all keep day-ahead market participation):

  * Sizing:  HomeBatt (home battery), HoodBatt (neighbourhood battery)
  * Tariff:  HomeBattNoTariff (no power/peak tariff vs HomeBatt with it)
  * FCR:     HomeBattNoFCR, HomeBattFCRDonly, HomeBattFCRNonly (vs HomeBatt = both)
  * Hydrogen: H2Tank (size the tank), Electrolyser (size the electrolyser)

Common assumptions (review before drawing conclusions):
  * Horizon: first N_LOADLEVELS load levels of the base case. The base case only
    gives the first 24 levels a nonzero Duration, so the solved horizon is one day.
  * Unit commitment relaxed (LP) so costs are reproducible.
  * Continuous investment (build fraction in [0, 1]).
  * FCR requirement capped to FCR_CAP kW so home/neighbourhood assets can meet it.
  * Exactly one asset carries an investment cost, so only that asset is sized.

Hydrogen cases: the 5 kgH2/h demand sits at the converter node (Node2) together
with a priced hydrogen import (the retailer is moved there and given a buy
allowance). The import is cheap at night and expensive in the day, which is what
the candidates are sized against: the tank buys cheap night hydrogen and serves
the day (built in full), and the electrolyser is built only for the hours where
producing from retail electricity beats the day import price (a small fraction).
Green-hydrogen matching is off in these two cases - the base case's rooftop solar
(~0.2 kW) cannot supply an electrolyser drawing kilowatts.

DoD (depth-of-discharge) variants are not generated here yet: the model has no
single switch for them, so that toggle needs the model author's input.
"""
import os
import shutil

import pandas as pd

from el1xr_opt.Modules.oM_InputCSVSource import CSVSource
from el1xr_opt.Modules.oM_CsvToDuckDB import csv_case_to_duckdb

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
BASE_DIR = os.path.join(REPO, "data", "H2VPP")
BASE_CASE = "Home1"
OUT_ROOT = HERE

N_LOADLEVELS = 168   # one week
FCR_CAP = 20.0       # kW per FCR product (home-scale requirement)
RELAX_FLAGS = ["IndBinGenOperat", "IndBinGenRamps", "IndBinGenMinTime"]
FCRD_PRODUCTS = ["FCRD_Up", "FCRD_Down"]
FCRN_PRODUCTS = ["FCRN_Up", "FCRN_Down"]

# Case specifications. Each is read by build_case below.
#   battery: (unit, fixed_investment_cost, scale_dict|None) or None
#   h2:      (unit, fixed_investment_cost) or None
#   fcrd/fcrn: whether storage may bid that frequency product
#   power_peaks: NumberPowerPeaks value, or None to keep the base value
#   h2_demand: kgH2/h at the electrolyser node (defaults to H2_DEMAND)
#   e2h_fcr: whether the electrolyser may bid FCR by modulating its consumption
CASES = {
    "HomeBatt":         dict(battery=("BESS_01", 0.2, None),  fcrd=True,  fcrn=True),
    "HoodBatt":         dict(battery=("BESS_01", 0.2, dict(MaximumPower=50, MaximumCharge=50.0, MaximumStorage=100.0)), fcrd=True, fcrn=True),
    "HomeBattNoTariff": dict(battery=("BESS_01", 0.2, None),  fcrd=True,  fcrn=True, power_peaks=0),
    "HomeBattNoFCR":    dict(battery=("BESS_01", 0.2, None),  fcrd=False, fcrn=False),
    "HomeBattFCRDonly": dict(battery=("BESS_01", 0.2, None),  fcrd=True,  fcrn=False),
    "HomeBattFCRNonly": dict(battery=("BESS_01", 0.2, None),  fcrd=False, fcrn=True),
    # H2Tank: size the tank (PEMEL_01), with the electrolyser (AEL_01) existing.
    # A priced hydrogen import at the converter node serves the bulk of the demand
    # (the electrolyser can only make ~0.9 kgH2/h); the day/night import price
    # spread is what gives the tank arbitrage value to be sized against.
    "H2Tank":           dict(battery=None, fcrd=True, fcrn=True, h2=("PEMEL_01", 0.05),
                             h2_import=True, green=0),
    # H2TankCompressor: H2Tank plus a sized compressor on the tank (PEMEL_01). The
    # compressor is built to cover the realized charging duty -- a small end-to-end
    # demo of Phase 1 compressor sizing. Decision/invariance case, no golden cost.
    "H2TankCompressor": dict(battery=None, fcrd=True, fcrn=True, h2=("PEMEL_01", 0.05),
                             h2_import=True, green=0, compressor=("PEMEL_01", 10.0, 0.05)),
    # Electrolyser: AEL_01 is the candidate; the existing tank (PEMEL_01) stays.
    # The same priced import serves the demand; the electrolyser is built only if
    # making hydrogen from retail electricity beats the import price.
    "Electrolyser":     dict(battery=None, fcrd=True, fcrn=True, h2=("AEL_01", 0.10),
                             h2_import=True, green=0),
    # Electrolyser FCR validation: a hydrogen demand keeps the electrolyser running, so it
    # has consumption to modulate. The NoFCR case is the baseline; the FCR case lets the
    # electrolyser bid FCR. The FCR case should cost less, by the FCR revenue the
    # electrolyser earns. A priced hydrogen import backs the demand: the electrolyser sits
    # at Node2, which only has local solar for electricity, so it cannot make the full
    # 0.5 kgH2/h on its own. Without the import the demand is unservable and the case is
    # infeasible. Green-H2 matching stays on here so the matching structure is testable.
    "ElectrolyserNoFCR": dict(battery=None, fcrd=True, fcrn=True, h2=("AEL_01", 0.10), h2_demand=0.5, e2h_fcr=False, h2_import=True),
    "ElectrolyserFCR":   dict(battery=None, fcrd=True, fcrn=True, h2=("AEL_01", 0.10), h2_demand=0.5, e2h_fcr=True, h2_import=True),
    # ElectrolyserFCR plus a sized compressor on the tank (PEMEL_01): exercises the Phase 2
    # FCR-down rate coupling -- the electrolyser's FCR-down bid is bounded by the spare
    # compressor throughput at the node, on top of the tank-headroom volume limit.
    # green=0 here so the electrolyser can draw grid electricity and run hard enough to
    # hold real FCR-down bids; with matching on (and all solar dropped in this single-period
    # run) its consumption is pinned near zero and the FCR-down coupling is never exercised.
    "ElectrolyserFCRCompressor": dict(battery=None, fcrd=True, fcrn=True, h2=("AEL_01", 0.10),
                                      h2_demand=0.5, e2h_fcr=True, compressor=("PEMEL_01", 2.0, 0.05),
                                      green=0, h2_import=True),
    # Three-state electrolyser demonstration: binary commitment, a small electrolyser, and
    # a hydrogen demand burst with a one-hour gap (0.09, 0, 0.09) and no storage buffer.
    # The electrolyser sits in STANDBY through the idle hour (drawing only its standby
    # power, making no hydrogen) to avoid a cold restart -- so standby is actively chosen
    # and the cost is lower than if it had to shut down and cold-start again.
    "ElectrolyserStandby": dict(battery=("BESS_01", 0.2, None), fcrd=False, fcrn=False,
                                h2=("AEL_01", 0.10), e2h_charge=(2.0, 20.0), standby=True,
                                no_h2_buffer=True, binary_uc=True, green=0,
                                demand_profile=[0.09, 0.0, 0.09] + [0.0] * 9),
}


def _relax_uc(df):
    for flag in RELAX_FLAGS:
        if flag in df.columns:
            df[flag] = 0
    return df


def _set_power_peaks(df, n):
    if "NumberPowerPeaks" in df.columns:
        df["NumberPowerPeaks"] = n
    return df


def _set_fcr_requirement(df, fcrd, fcrn):
    # Participated products are capped to a home scale; non-participated products
    # have their requirement zeroed so the case stays feasible with no bidder.
    for col in FCRD_PRODUCTS:
        if col in df.columns:
            df[col] = df[col].clip(upper=FCR_CAP) if fcrd else 0.0
    for col in FCRN_PRODUCTS:
        if col in df.columns:
            df[col] = df[col].clip(upper=FCR_CAP) if fcrn else 0.0
    return df


def _edit_ele(df, spec):
    if "ESS" in df.columns:
        is_storage = df["ESS"].astype(str).str.strip().str.lower().eq("yes")
        if "NoFCRD" in df.columns:
            df.loc[is_storage, "NoFCRD"] = "No" if spec["fcrd"] else "Yes"
        if "NoFCRN" in df.columns:
            df.loc[is_storage, "NoFCRN"] = "No" if spec["fcrn"] else "Yes"
    if "FixedInvestmentCost" in df.columns:
        df["FixedInvestmentCost"] = pd.NA  # clear all; one candidate is set below
    battery = spec.get("battery")
    if battery:
        unit, fic, scale = battery
        if scale:
            for col, val in scale.items():
                if col in df.columns:
                    df.loc[unit, col] = val
        _set_candidate(df, unit, fic)
    return df


H2_DEMAND = 5.0  # kgH2/h at node HydD1, so the electrolyser/tank have something to serve

# Priced hydrogen import (h2_import cases): the hydrogen retailer is moved to the
# converter node and given a buy allowance, so the demand the electrolyser cannot
# cover is bought instead of hitting the not-served penalty. The day/night price
# spread is what makes a tank worth building (buy cheap at night, serve the day).
H2_TANK_UNIT = "PEMEL_01"
H2_IMPORT_CAP = 10.0           # kgH2/h buy allowance (demand is 5, tank can charge too)
# Prices are on the H2VPP money scale (the electrolyser's own hydrogen costs about
# 53 per kg: ~35 retail electricity incl. fees and tax at 56.82 kWh/kg, plus 18.2
# O&M). The day price sits above that so producing and storing beat importing in
# the day; the night price sits below it so the night import is the cheap source.
H2_IMPORT_PRICE_NIGHT = 40.0   # per kgH2, hours 00-07 and 20-23
H2_IMPORT_PRICE_DAY = 80.0     # per kgH2, hours 08-19
H2_IMPORT_DAY_HOURS = range(8, 20)
# The base-case tank ratings are implausible for a 22 kgH2 tank (900+ kgH2/h) and
# its 12 kgH2 minimum / 15 kgH2 initial inventory neither scales with the build
# fraction nor lets a candidate start empty - so a candidate tank was forced to
# be built just to satisfy its own floor. Finite ratings, empty start.
H2_TANK_DATA = {"MaximumPower": 10.0, "MaximumCharge": 10.0,
                "InitialStorage": 0.0, "MinimumStorage": 0.0}


def _edit_hyd_retail(df):
    # Activate the hydrogen retailer as a priced import at the converter node:
    # the base retailer sits at Node1 (no pipeline to Node2) with a zero buy
    # allowance, so it can never compose an import. MaximumEnergyBuy > 0 is what
    # puts the retailer in the active set (model.hr).
    df["Node"] = H2_NODE
    if "Buy" in df.columns:
        df["Buy"] = "Yes"
    df["InitialPeriod"] = 2020
    df["MaximumEnergyBuy"] = H2_IMPORT_CAP
    return df


def _set_h2_import_price(df, retailer="HydR_01"):
    # Day/night import price profile on the hydrogen retailer column of
    # VarEnergyCost (load levels are hourly, starting at hour 0).
    hours = pd.Series(range(len(df)), index=df.index) % 24
    df[retailer] = [H2_IMPORT_PRICE_DAY if h in H2_IMPORT_DAY_HOURS
                    else H2_IMPORT_PRICE_NIGHT for h in hours]
    return df


def _edit_hyd(df, spec):
    h2 = spec.get("h2")
    if h2:
        if spec.get("h2_import"):
            for col, val in H2_TANK_DATA.items():
                if col in df.columns:
                    df.loc[H2_TANK_UNIT, col] = val
        # In the base case the hydrogen units come online in 2040 (InitialPeriod),
        # but the model runs at EconomicBaseYear 2025, so they are inactive and the
        # electricity-to-hydrogen set (e2h) is empty. Bring them into the base year
        # so the electrolyser is linked and can be sized.
        if "InitialPeriod" in df.columns:
            df["InitialPeriod"] = 2020
        _set_candidate(df, h2[0], h2[1])
        if spec.get("e2h_charge"):
            mn, mx = spec["e2h_charge"]
            if "MinimumCharge" in df.columns:
                df.loc[h2[0], "MinimumCharge"] = mn
            if "MaximumCharge" in df.columns:
                df.loc[h2[0], "MaximumCharge"] = mx
        if spec.get("standby") and "StandByStatus" in df.columns:
            df.loc[h2[0], "StandByStatus"] = "Yes"   # enable the three-state (on/standby/off) model
        if spec.get("no_h2_buffer") and "InitialPeriod" in df.columns:
            # keep only the electrolyser active; push the H2 store(s) out of the base year
            # so the electrolyser must serve demand directly (no buffer to smooth cycling)
            for u in df.index:
                if u != h2[0]:
                    df.loc[u, "InitialPeriod"] = 2040
        if spec.get("e2h_fcr"):
            # The hydrogen-generation data has no FCR columns by default. Add them
            # (every unit off) and opt the electrolyser in, with a 60-minute
            # endurance for the FCR-down hydrogen-headroom check.
            df["NoFCRD"] = "Yes"
            df["NoFCRN"] = "Yes"
            df["EnduranceFCRD"] = 0.0
            df["EnduranceFCRN"] = 0.0
            for col, val in (("NoFCRD", "No"), ("NoFCRN", "No"),
                             ("EnduranceFCRD", 60.0), ("EnduranceFCRN", 60.0)):
                df.loc[h2[0], col] = val
        comp = spec.get("compressor")
        if comp:
            # Compressor sizing (Phase 1): a rated throughput and an annualized capex on
            # one unit; every other unit stays at 0 so it is not a compressor candidate.
            unit, nameplate, invest = comp
            df["CompressorNameplate"] = 0.0
            df["CompressorInvestCost"] = 0.0
            df.loc[unit, "CompressorNameplate"] = nameplate
            df.loc[unit, "CompressorInvestCost"] = invest
    return df


def _set_h2_demand(df, demand=H2_DEMAND, profile=None):
    if "HydD1" in df.columns:
        if profile is not None:
            df["HydD1"] = [profile[i % len(profile)] for i in range(len(df))]
        else:
            df["HydD1"] = demand
    return df


# Node the hydrogen demand is moved to, so it sits with the electrolyser/tank.
H2_NODE = "Node2"


def _move_h2_demand_node(df):
    # In the base case the hydrogen demand is at Node1, but the electrolyser and
    # tank are at Node2 and there is no hydrogen pipeline between the two. The
    # hydrogen balance is only built at nodes that have local hydrogen assets, so
    # a demand on an asset-less node is silently dropped and nothing is produced.
    # Put the demand on the electrolyser's node so it actually drives production.
    if "Node" in df.columns and "HydD1" in df.index:
        df.loc["HydD1", "Node"] = H2_NODE
    # Bring the demand into the base year too (the supply is moved to 2020 in
    # _edit_hyd). Otherwise the demand sits in 2040-2050 and is dropped by the
    # base-year period filter on the hydrogen-demand set.
    if "InitialPeriod" in df.columns:
        df["InitialPeriod"] = 2020
    return df


def _set_candidate(df, unit, fic, fcr_rate=0.08):
    if "FixedInvestmentCost" in df.columns:
        df.loc[unit, "FixedInvestmentCost"] = fic
    if "FixedChargeRate" in df.columns:
        df.loc[unit, "FixedChargeRate"] = fcr_rate
    if "BinaryInvestment" in df.columns:
        df.loc[unit, "BinaryInvestment"] = pd.NA   # continuous build fraction
    for col, val in (("InvestmentLo", 0.0), ("InvestmentUp", 1.0)):
        if col in df.columns:
            df.loc[unit, col] = val
    return df


def build_case(case, spec):
    """Write the CSV folder for one case and return its path."""
    src = CSVSource(os.path.join(BASE_DIR, BASE_CASE))
    out = os.path.join(OUT_ROOT, case)
    if os.path.isdir(out):
        shutil.rmtree(out)
    os.makedirs(out)
    keep = set(list(src.read_dict("LoadLevel").iloc[:, 0])[:N_LOADLEVELS])

    for stem in sorted(src.list_dict_stems()):
        df = src.read_dict(stem)
        if stem == "LoadLevel":
            df = df.iloc[:N_LOADLEVELS]
        df.to_csv(os.path.join(out, f"oM_Dict_{stem}_{case}.csv"), index=False)

    for stem in sorted(src.list_data_stems()):
        df = src.read_data(stem)
        if df.index.nlevels == 3:
            df = df[df.index.get_level_values(2).isin(keep)]
        df = df.copy()
        if stem == "Option":
            df = _relax_uc(df)
            if spec.get("binary_uc") and "IndBinGenOperat" in df.columns:
                df["IndBinGenOperat"] = 1   # keep binary commitment (3-state needs discrete on/standby/off)
        elif stem == "Parameter":
            if spec.get("power_peaks") is not None:
                df = _set_power_peaks(df, spec["power_peaks"])
            if spec.get("green") is not None and "GreenH2Matching" in df.columns:
                df["GreenH2Matching"] = spec["green"]
        elif stem == "OperatingReserveRequire":
            df = _set_fcr_requirement(df, spec["fcrd"], spec["fcrn"])
        elif stem == "ElectricityGeneration":
            df = _edit_ele(df, spec)
        elif stem == "HydrogenGeneration":
            df = _edit_hyd(df, spec)
        elif stem == "HydrogenDemand" and spec.get("h2"):
            df = _move_h2_demand_node(df)
        elif stem == "HydrogenRetail" and spec.get("h2_import"):
            df = _edit_hyd_retail(df)
        elif stem == "VarEnergyCost" and spec.get("h2_import"):
            df = _set_h2_import_price(df)
        elif stem in ("VarMaxDemand", "VarMinDemand") and spec.get("h2"):
            df = _set_h2_demand(df, spec.get("h2_demand", H2_DEMAND), spec.get("demand_profile"))
        df.to_csv(os.path.join(out, f"oM_Data_{stem}_{case}.csv"))
    return out


def main(keep_csv=False):
    for case, spec in CASES.items():
        folder = build_case(case, spec)
        db = csv_case_to_duckdb(OUT_ROOT, case)        # writes data/sizing/<case>.duckdb
        if not keep_csv:
            shutil.rmtree(folder)                       # keep only the .duckdb
        print(f"built {case} -> {os.path.basename(db)}")


if __name__ == "__main__":
    import sys
    main(keep_csv="--keep-csv" in sys.argv)
