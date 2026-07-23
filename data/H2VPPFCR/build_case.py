"""Build the paper's FCR VPP case from the model's H2VPP/Home1 base case.

This is the readable source for the case study in `inputs/<CASE>/`. It assembles
one node with the full virtual power plant the paper studies:

  * a wind generator (the renewable resource),
  * a battery (BESS) build candidate that bids FCR-N and FCR-D,
  * an electrolyser build candidate, three-state (on / standby / off), that bids
    FCR-N and FCR-D by modulating its consumption,
  * a hydrogen tank build candidate with a sized compressor,
  * a hydrogen demand served by the electrolyser, the tank, or a priced import,
  * FCR-N and FCR-D prices and a requirement large enough that both the battery
    and the electrolyser are needed to meet it.

No single case shipped with the model combines all of these, so the case is
assembled here rather than reused. The transformations follow the model's own
`data/sizing/make_sizing_cases.py` (the same hydrogen fix-ups, the same FCR
requirement cap), extended to size the battery, the electrolyser, the tank and
the compressor together and to add a wind unit.

Every number below is a PLACEHOLDER chosen so the case solves and exercises the
formulation. Real wind, price, demand and techno-economic data is an [ERIK]
input (see notes/development_plan.md, Phase 1). Re-run after editing:

    python experiments/h2vpp_fcr/build_case.py

It reads the model submodule (a clean dependency) and writes the paper-owned
case CSVs into inputs/<CASE>/, which are tracked in this repo.
"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
MODEL = REPO / "model"
BASE_DIR = MODEL / "data" / "H2VPP"
BASE_CASE = "Home1"

CASE = "H2VPPFCR"
OUT_DIR = HERE / "inputs" / CASE

# The model package lives in the submodule; import its CSV reader so the index
# columns are parsed exactly as the model itself parses them.
sys.path.insert(0, str(MODEL / "src"))
from el1xr_opt.Modules.oM_InputCSVSource import CSVSource  # noqa: E402

# --- horizon ---------------------------------------------------------------
# "week" (168 h) or "month" (~744 h). The base case ships only 168 load levels, so
# a month is built by GENERATING 744 levels and tiling the base structure, with the
# real monthly profiles overlaid (the longer horizon is where multi-day storage
# arbitrage pays). The week uses the base 168 levels directly. Each level carries a
# 1 h Duration (see _edit_duration); capex is pro-rated to the modeled window.
# "week" (168 h), "month" (744 h), or "year" (8736 h = 52 weeks). Default month (the
# local/CI horizon); override with H2VPP_HORIZON=year for the full-year Comillas run.
HORIZON = os.environ.get("H2VPP_HORIZON", "month")
N_LOADLEVELS = {"week": 168, "month": 744, "year": 8736}[HORIZON]
HORIZON_HOURS = N_LOADLEVELS
# The real input data (spot, FCR, wind, demand) is a full 2025 year; a shorter horizon
# slices N_LOADLEVELS hours starting at 2025-01-01 + H2VPP_START_HOUR (default 0). Set the
# offset to model a different window (e.g. 24*180 to start in summer).
HORIZON_START_HOUR = int(os.environ.get("H2VPP_START_HOUR", "0"))

# --- annualisation ---------------------------------------------------------
# Investment enters the objective as a FULL ANNUAL charge
# (FixedInvestmentCost x FixedChargeRate, period-weighted), while operating cost is
# summed only over the modeled hours. On a one-day horizon the annual build cost is
# ~365x too dear, so nothing builds. Reconcile the two by pro-rating the annual
# charge down to the modeled window: scale the charge rate by HORIZON_HOURS / 8760.
# pDuration (the storage timestep) is left at 1 h, so storage physics stay correct.
# Report annual figures by scaling the solved cost back up by 8760 / HORIZON_HOURS.
# Set PRORATE = False to reproduce the un-reconciled behaviour (capex dominates,
# nothing builds) as a control.
ANNUAL_HOURS = 8760.0
PRORATE = True
CAPEX_HORIZON_FACTOR = (HORIZON_HOURS / ANNUAL_HOURS) if PRORATE else 1.0

# --- numerical conditioning ------------------------------------------------
# factor1 rescales the model for solver stability (the optimum is invariant, see
# the model's test_factor1_invariant). At Port/MW scale the kW-basis coefficients
# are O(1e3-1e4); factor1 = 0.001 puts them on a MW basis, O(1). Written to the
# Parameter 'Factor1' hook and read by the model. Use 1.0 for the kW basis.
FACTOR1 = 0.001

# --- money base (per-unit cost scaling) ------------------------------------
# MONEY_BASE divides every money-valued input (capex, prices, tariffs, penalties, degradation
# costs) so the cost-layer matrix coefficients land in the same band as the physical ones.
# factor1 already puts power/energy on a MW basis; it does NOT touch the cost layer, so the
# investment-cost coefficient (annualized capex x period weight ~= 4.4e6 at year) and the prices
# (x 1/factor1) sit 6-10 orders above the physical coefficients (~1e-4) -- the matrix range that
# makes the year barrier fragile (see notes/scalability_conditioning_investigation.py). Money
# enters only the objective + cost-aggregation constraints, so dividing every money input by the
# SAME base leaves the optimum MATHEMATICALLY invariant; results come back in MONEY_BASE-SEK and
# run_year scales the reported objective back to SEK. Default 1.0 = raw SEK (no cost scaling).
# RECOMMENDED: MONEY_BASE=1000 cuts the year matrix range from ~10.6 to ~7.6 orders (capex
# coefficient 4.4e6 -> 4.4e3; the small end stays at the physical floor ~1e-4). Larger bases just
# push the per-kWh price coefficients below the physical floor without shrinking the range further.
#
# NUMERICAL WARNING (proven 2026-07-03): the invariance is only mathematical. A raw-SEK basis
# (MONEY_BASE=1) leaves a large annualized capex coefficient against per-hour reserve-activation
# fractions ~1.8e-4 -- a wide range that makes BOTH HiGHS and Gurobi (even NumericFocus=3) return a
# SILENTLY suboptimal optimum, with no infeasibility or warning. When this was first proven the
# largest capex coefficient was ~5.8e5 (a ~3e9 range) and the error was ~17% off the true value.
# The LP is provably identical up to the money scale, so this is pure ill-conditioning, not a
# coefficient bug. Dividing every money input by MONEY_BASE conditions it and recovers the true
# optimum. The guard below rejects any basis whose largest annualized capex coefficient exceeds
# the limit.
MONEY_BASE = float(os.environ.get("MONEY_BASE", "1.0"))
# Largest allowed annualized-capex coefficient (raw FixedInvestmentCost x FixedChargeRate / MONEY_BASE)
# before build() refuses the case as ill-conditioned. NUMBERS UPDATED 2026-07-07: the owned-wind
# investment candidate (1147 EUR/kW x 30 MW x 0.079 charge rate) is now the largest capex coefficient,
# so MONEY_BASE=1 lands ~3.0e7 (rejected) and MONEY_BASE=1000 lands ~3.0e4 -- under the 1e5 limit, and
# the value the validated campaign runs on with its tuned barrier profile. (The old ~5.8e5 / ~580
# anchors predate the owned-wind candidate.) A native-EUR basis is a uniform 1/11.07 rescale, so it is
# conditioning-neutral-to-better than SEK at the same MONEY_BASE; probe 2026-07-07 confirmed this and
# recommends MONEY_BASE=100 for a native-EUR build (see notes/currency_decision_2026-07-07.md).
# Set COND_ALLOW_ILL=1 to override for a deliberate raw-SEK run.
COND_MAX_CAPEX_COEF = float(os.environ.get("COND_MAX_CAPEX_COEF", "1e5"))

# --- firm-contract penalty -------------------------------------------------
# HNSCost is the penalty for not serving scheduled hydrogen demand (SEK/kgH2). For a
# firm contract it must exceed the net cost of serving (import ~150 minus the demand
# revenue ~80 = ~70 SEK/kg) so the contract is honoured, but NOT the value-of-lost-load
# scale (~1e5): that huge coefficient blows up the model's coefficient range and makes
# the MILP numerically fragile (the solver falsely reports it infeasible). 150 SEK/kg is
# binding yet well conditioned. The SAME applies to ENSCost (electricity value-of-lost-load):
# its base ~1e5 value, x1/factor1, is the 1e8 matrix coefficient that gives the year LP a
# [9e-8, 1e8] range and breaks the barrier (numerical trouble) -- even though electricity is
# never unserved here, a never-binding penalty still sits in the matrix and wrecks the
# conditioning. So set it to a realistic VOLL (~8000 EUR/MWh ~= 90 SEK/kWh), still far above any
# serving cost (so vENS stays 0, optimum-neutral) but ~3 orders smaller. See analysis/scaling_diagnostic.py.
HNSCOST = 150.0
ENSCOST = 90.0   # electricity VOLL, SEK/kWh (~8000 EUR/MWh); well conditioned, never-binding

# --- currency --------------------------------------------------------------
# The model is single-currency (SEK here); EUR/USD figures are converted at a
# stated rate as a cited data-prep step, not a model conversion. Source: ECB euro
# reference exchange rates, 2025 ANNUAL AVERAGE (the average of the daily ~16:00
# CET fixings over 2025) -- the same reference year as the market data. The annual
# average is used deliberately so no single trading hour drives the cost basis.
# USD/SEK is the cross-rate EUR/SEK divided by EUR/USD. See notes/data_sources.md.
#   EUR/SEK = 11.0671, EUR/USD = 1.1306  (ECB, 2025 average)
EUR_SEK = 11.0671
USD_SEK = 11.0671 / 1.1306       # = 9.79, cross-rate via ECB 2025 averages

# --- model currency (SEK default; EUR = the native-EUR basis, phase 2) ------
# The whole cost layer is assembled in SEK below (EUR/USD-sourced values x EUR_SEK/USD_SEK; the
# Swedish regulatory items -- tariffs, energy tax, VOLL/HNS penalties -- in native SEK). Set
# H2VPP_CURRENCY=EUR to emit the case in native EUR instead: because every money value is SEK by
# the time it is written, one uniform division of every money column by EUR_SEK converts the whole
# cost layer to EUR. The optimum is invariant to this rescale (see notes/currency_decision_2026-07-07.md
# and the 2026-07-07 conditioning probe); EUR mode just moves the /EUR_SEK from the display layer into
# the inputs. Recommended pairing: H2VPP_CURRENCY=EUR with MONEY_BASE=100 (matches the proven SEK@1000
# conditioning). CURRENCY_DIV is the single factor applied to every money column at write time.
CURRENCY = os.environ.get("H2VPP_CURRENCY", "SEK").upper()
if CURRENCY not in ("SEK", "EUR"):
    raise SystemExit(f"H2VPP_CURRENCY must be SEK or EUR, got {CURRENCY!r}")
CURRENCY_DIV = 1.0 if CURRENCY == "SEK" else EUR_SEK

# --- real market data (2025, SE3) ------------------------------------------
# Real fetched time series (notes/data_sources.md, notes/data_sources.bib) replace
# the placeholder profiles, aligned hour-for-hour to the weekly horizon. EUR is
# converted to SEK at EUR_SEK. Set False to fall back to the base-case placeholders.
USE_REAL_DATA = True
REAL_DATA = HERE / "inputs" / "real_data" / "year"   # full 2025; readers slice the horizon


def _real_spot_sek_kwh():
    """SE3 day-ahead spot price as SEK/kWh, one value per modeled hour."""
    s = pd.read_csv(REAL_DATA / "spot_se3.csv")["price_eur_mwh"].to_numpy()
    return s[HORIZON_START_HOUR:HORIZON_START_HOUR + N_LOADLEVELS] / 1000.0 * EUR_SEK


def _real_fcr_sek_kw_h():
    """svk FCR capacity prices as SEK/kW/h, per product, per modeled hour.

    FCR-N is symmetric (one clearing price), so it fills both the up and down
    columns; FCR-D up and down are separate products.
    """
    d = pd.read_csv(REAL_DATA / "fcr_se.csv")
    to_sek = lambda c: d[c].to_numpy()[HORIZON_START_HOUR:HORIZON_START_HOUR + N_LOADLEVELS] / 1000.0 * EUR_SEK * FCR_PRICE_SCALE
    return {"FCRD_Up": to_sek("fcr_d_up_eur_mw"), "FCRD_Down": to_sek("fcr_d_down_eur_mw"),
            "FCRN_Up": to_sek("fcr_n_eur_mw"), "FCRN_Down": to_sek("fcr_n_eur_mw")}

# --- electricity assets ----------------------------------------------------
# Scale: a 2030 hydrogen-valley VPP serving a medium heavy-duty truck refuelling
# station (~480 kgH2/day, ~8 Class-8 fills). Nameplates are generous candidate
# CEILINGS; the investment model sizes each asset down to its optimum.
WIND_UNIT = "Wind_01"            # renamed from the base case's Solar_01
WIND_UNIT_2 = "Wind_02"          # optional second owned wind plant (same 15 MW site, same CF profile)
WIND_N_PLANTS = int(os.environ.get("WIND_N_PLANTS", "1"))   # owned wind candidates: 1 (a single 30 MW farm, default) avoids the identical-column degeneracy of two 15 MW twins
WIND_SOURCE_UNIT = "Solar_01"    # the active rooftop-solar unit we repurpose
_WIND_UNITS = [WIND_UNIT] + ([WIND_UNIT_2] if WIND_N_PLANTS >= 2 else [])   # active wind candidates
# Stray Home1 base-case units that are NOT part of the VPP: a small EV battery and the
# rooftop-PV strings at the electrolyser node. They are dropped so the case holds only the
# paper's assets (wind, battery, electrolysers, tank, compressor, and the disabled fuel
# cell). Solar_01 is excluded from the drop -- it has already been repurposed as Wind_01.
DROP_UNITS = {f"EV_{i:02d}" for i in range(1, 11)} | {f"Solar_{i:02d}" for i in range(2, 11)}
# The plant does not own the wind: it contracts an OFF-SITE farm through a renewable
# PPA and matches the electrolyser draw to it hourly (EU Delegated Reg 2023/1184,
# hourly from 2030). The contracted farm is sized to the electrolyser (not a co-located
# 5 MW), so hourly matching is feasible without pinning the electrolyser to near-zero.
WIND_MAX_POWER = float(os.environ.get("WIND_MAX_POWER_KW", "30000.0"))   # kW nameplate cap of the owned wind (merchant baseline: one 30 MW farm, sized 0..1); env-overridable
WIND_WAKE_LOSS = 0.10            # farm wake derate on the single-turbine ERA5 CF
# Integrated Hydrogen Valley (HiWhyV): the wind is OWNED / co-invested by the project, not a
# fixed external PPA. It is a sized investment candidate co-located at the grid hub; the green-H2
# hourly matching then couples the electrolyser to the OWNED wind, and the wind build co-sizes
# with the grid-connection capacity (bigger wind -> bigger export peak -> costlier connection).
# Onshore wind, DEA "Technology Data for Generation of Electricity and District Heating" (2030,
# sheet "20 Onshore turbines"): nominal investment 1.147 MEUR/MW (total, incl. internal grid),
# fixed O&M 16.66 kEUR/MW/yr, variable O&M 1.98 EUR/MWh, 30 yr technical life. The model has no
# separate fixed-O&M term for a candidate, so the annual fixed O&M is FOLDED INTO the charge rate:
# effective rate = CRF(30yr@5%=0.0651) + fixedOM/capex(16.66/1147=0.0145) = 0.0796.
WIND_CAPEX_EUR_KW = float(os.environ.get("WIND_CAPEX_EUR_KW", "1147.0"))   # env-overridable for the wind-capex spoke (m4: DEA 2030 1147 +-25%)
WIND_CRF = 0.0796               # DEA 30yr@5% capital recovery (0.0651) + folded fixed O&M (0.0145)
WIND_CAPEX = WIND_CAPEX_EUR_KW * EUR_SEK * WIND_MAX_POWER   # SEK, full nameplate
WIND_OM_VAR = round(0.00198 * EUR_SEK, 4)   # DEA variable O&M ~1.98 EUR/MWh (~0.022 SEK/kWh)
# Wind procurement mode (spoke knob): "owned" = the valley builds and sizes the wind (baseline);
# "ppa" = a fixed off-site contracted PPA paid per kWh (the pre-integration framing, a sensitivity).
WIND_MODE = os.environ.get("WIND_MODE", "owned").lower()
# (retained for reference / the off-site-PPA sensitivity; unused in the owned-wind baseline)
PPA_PRICE_EUR_MWH = 38.0
PPA_PRICE_SEK_KWH = PPA_PRICE_EUR_MWH * EUR_SEK / 1000.0

BESS_UNIT = "BESS_01"     # base row in the ElectricityGeneration CSV, cloned per duration
# Battery cost split into a power and an energy component so competing DURATIONS price
# realistically (a shorter-duration battery is cheaper per MW of reserve). The paper's 4 h
# system cost (334 USD/kWh, NREL ATB 2024) is decomposed ~40 % power / 60 % energy per the
# NREL ATB battery cost breakdown (Cole et al. 2021, NREL/TP-6A20-79236): 534 USD/kW power +
# 200 USD/kWh energy reconciles to 334 USD/kWh at 4 h, and prices 2 h at 467 / 8 h at 267 USD/kWh.
BESS_POWER_CAPEX_USD_KW = 534.0
BESS_ENERGY_CAPEX_USD_KWH = 200.0
BESS_POWER_KW = 8000.0    # candidate power per duration (headroom above the ~4.2 MW optimum)
# Competing duration candidates the model chooses among; each is a separate build candidate
# (BESS_2h, BESS_4h, BESS_8h). The model picks the duration(s) and size for the FCR + arbitrage need.
BESS_DURATIONS_H = [2.0, 4.0, 8.0]
BESS_UNITS = [f"BESS_{int(d)}h" for d in BESS_DURATIONS_H]
BESS_CRF = 0.0963                        # capital recovery, 15 yr @ 5%
BESS_FOM = 0.025                         # fixed O&M ~2.5%/yr of capex (NREL ATB 2024, utility Li-ion)

# --- electrolyser fleet (competing technologies, modular) ------------------
# Port-of-Gothenburg-scale electrolyser (~7 MW), built from MODULES of competing
# technologies; the model picks the optimal mix and how many modules of each.
# Per-technology specs from DEA "Technology Data for Renewable Fuels" (electrolysis chapter
# updated Jan 2024, Ramboll), 2030, sheets "1.1 AEC 100 MW" / "1.1 PEMEC 100 MW". CAPEX is per kW
# of ELECTRICITY INPUT (matches MaximumCharge). DEA 2030: AEC 550 EUR/kW, PEMEC 650 EUR/kW (the
# Jan-2024 update raised these ~60%/~25% vs the 2021 chapter). SOEC omitted (needs a steam source).
ELECTROLYSER_TEMPLATE = "AEL_01"     # base electrolyser row, cloned per module
#   tech : (n_modules, kW/module, kWh/kgH2, capex EUR/kW, min-load frac, standby frac, fixed-O&M frac/yr)
# DEA 2030 fixed O&M = 4%/yr of capex (AEC), 2%/yr (PEMEC), EXCLUDING stack replacement (which the
# throughput degradation cost below prices). Folded into the per-module FixedChargeRate in _build_fleet.
# Module counts are env-tunable (AEL_N / PEM_N, default 2 each = 7 MW) so the electrolyser candidate
# menu can be widened when the optimum pins at the ceiling (all modules built). More modules just add
# continuously-sized [0,1] candidates -- the LP relaxation sizes them smoothly; symmetry-breaking
# orders the identical twins. Default 2/2 keeps existing cases unchanged.
_AEL_N = int(os.environ.get("AEL_N", "2"))
_PEM_N = int(os.environ.get("PEM_N", "2"))
ELECTROLYSER_TECHS = {
    "AEL": (_AEL_N, 2000.0, 50.0, 550.0, 0.20, 0.02, 0.04),   # alkaline: cheaper capex, higher O&M (DEA 2030 AEC)
    "PEM": (_PEM_N, 1500.0, 48.0, 650.0, 0.05, 0.01, 0.02),   # PEM: costlier capex, lower O&M, flexible (DEA 2030 PEMEC)
}
ELECTROLYSER_CRF = 0.0710           # capital recovery, 25 yr @ 5% (DEA technical life)
# Electrolyser VARIABLE O&M (non-electricity, non-stack): deionised water (~9 kg/kgH2) plus minor
# consumables, ~0.02 EUR/kgH2 (DEA leaves variable O&M blank -- electricity/water are priced
# elsewhere; this is the residual water+consumables). The seed template carried an uncalibrated
# 18.2 SEK/kg from the Home1 base case (~90x too high). Fixed O&M (DEA 4%/2% of capex) is now folded
# into the per-tech charge rate; stack replacement is priced by the throughput degradation below.
ELECTROLYSER_OM_VAR = round(0.02 * EUR_SEK, 4)   # ~0.22 SEK/kgH2
# Byproduct valorisation (HiWhyV reuses residual O2 in aquaculture and waste heat in district
# heating). A per-kgH2 CREDIT, Nordic-sourced:
#   HEAT: DEA "Renewable Fuels" gives recoverable heat ~22% (AEC) / 26% (PEMEC) of the electricity
#   input; at ~50 kWh/kg that is ~12 kWh_th/kg. Swedish DH pays external low-grade waste heat at an
#   avoided-cost fraction ~20-30 EUR/MWh_th (Luleaa/Aalto 2024; the Nils Holgersson consumer price
#   is ~99 EUR/MWh incl VAT, far above the wholesale waste-heat remuneration). ~12 kWh x 25 EUR/MWh
#   ~= 0.30 EUR/kg. A heat pump is needed to lift ~60-70 C to DH supply (its power draw is not
#   separately modelled -- absorbed in the conservative price).
#   OXYGEN: 8 kg O2/kgH2; merchant value ~0 unless a local offtaker exists (HiWhyV aquaculture),
#   ~0.02-0.05 EUR/kg O2 -> ~0.15 EUR/kg partial offtake.
# Combined ~0.45 EUR/kgH2. Env-scalable (BYPRODUCT_SCALE); 0 disables it. Negative term in eTotalHydGCost.
BYPRODUCT_CREDIT = round(0.45 * EUR_SEK * float(os.environ.get("BYPRODUCT_SCALE", "1.0")), 4)   # ~4.98 SEK/kgH2

# --- degradation costs (literature-sourced; SEK/kWh in the case currency) -----
# Electrolyser stack wear, per technology, all sharing ONE DEA stack-cost basis so the degradation
# is internally consistent with the DEA capex/O&M above. DEA stack: AEC 115 EUR/kW @ 92,500 h;
# PEMEC 222 EUR/kW @ 77,500 h. DEA lifetimes are STEADY-STATE (Schofield et al. 2024, AIChE J:
# ~30 uV/h steady, degradation ~ j^2 under cycling), so they price the base throughput wear but
# LEAVE FCR CYCLING FREE. The paper's contribution prices that cycling ON TOP, via a high-load
# surcharge (2nd block) and a per-|delta| ramp cost -- the wear that steady-state TE data (DEA)
# misses. No separate stack-replacement capex (the throughput term already prices replacement).
#   base throughput = stack_cost / steady_life_h  (EUR/kWh at rated load)
#   2nd-block high-load surcharge = +13% (Refaat 2026 Table 2: 11.74 vs 10.37 uV/h at full vs <=80%)
#   ramp cost = stack_cost / ~15,800 cycles-to-EoL (Refaat ~24 uV/cycle over ~0.38 V) x 0.25
#               (a within-on ramp ~= a quarter of a 0->Pmax->0 cycle's wear), per kW of |delta|
_ELY_STACK = {"AEL": (115.0, 92500.0), "PEM": (222.0, 77500.0)}   # (stack EUR/kW, steady life h)
ELY_DEGRADATION_COST      = {t: round(c / h * EUR_SEK, 5) for t, (c, h) in _ELY_STACK.items()}
ELY_DEGRADATION_2NDBLOCK  = {t: round(0.13 * v, 5) for t, v in ELY_DEGRADATION_COST.items()}
ELY_RAMP_DEGRADATION_COST = {t: round(c / 15800.0 * 0.25 * EUR_SEK, 5) for t, (c, _h) in _ELY_STACK.items()}
# Battery sub-daily throughput cycle cost, INCREMENTAL to the daily depth-of-discharge
# cost (kept): replacement capex ~200 EUR/kWh over the DoD/cycle-life curve (Ghanaee
# et al. 2026, J. Energy Storage, doi:10.1016/j.est.2026.121426; NREL ATB 2024 capex)
# gives ~0.04-0.07 EUR/kWh discharged; the incremental sub-daily share is taken modest.
BESS_THROUGHPUT_DEGRADATION_COST = round(0.0226 * EUR_SEK, 3)  # ~0.25 SEK/kWh discharged
# Degradation-cost sweep knob: scales ALL the electrolyser degradation costs (throughput +
# 2nd-block + ramp) by DEG_SCALE (default 1.0 = full literature value). DEG_SCALE=0 reproduces
# the electrolyser degradation-off case; intermediate values trace the breakeven where the
# electrolyser re-enters the build. Battery throughput is left at its literature value.
DEG_SCALE = float(os.environ.get("DEG_SCALE", "1.0"))
# Cycling-degradation knob: scales ONLY the FCR-cycling surcharge (2nd-block high-load + ramp), the
# paper's contribution, leaving the DEA steady-state base throughput wear untouched. CYCLING_SCALE=0
# isolates the effect of pricing FCR cycling (base kept), unlike DEG_SCALE=0 which removes all wear.
CYCLING_SCALE = float(os.environ.get("CYCLING_SCALE", "1.0"))
# H2 sale-price sweep knob: scales every sector's willingness-to-pay (DEMAND_SECTORS price)
# by H2_PRICE_SCALE (default 1.0). Used with DEG_SCALE for the 2-D degradation x H2-price
# sensitivity heatmap (does the electrolyser build / provide FCR as these two move).
H2_PRICE_SCALE = float(os.environ.get("H2_PRICE_SCALE", "1.0"))
# FCR price-erosion knob: scales every FCR capacity price (all products, all hours) by
# FCR_PRICE_SCALE (default 1.0). Values below 1.0 emulate reserve prices eroding as a fleet
# of such plants enters the market, testing how far the battery's business case survives.
FCR_PRICE_SCALE = float(os.environ.get("FCR_PRICE_SCALE", "1.0"))

TANK_UNIT = "PEMEL_01"
# H2 tank: ~500 EUR/kgH2 compressed storage (DEA). ~10 tonne candidate at port scale.
# TANK_CAPEX_EUR_KG is env-tunable for the capex sensitivity sweep (default 500).
TANK_STORAGE_KG = 10000.0
TANK_CAPEX_EUR_KG = float(os.environ.get("TANK_CAPEX_EUR_KG", "500.0"))
TANK_CAPEX = TANK_CAPEX_EUR_KG * EUR_SEK * TANK_STORAGE_KG   # SEK, full unit
TANK_CRF = 0.0802                                # capital recovery, 20 yr @ 5%
TANK_FOM = 0.02                                  # fixed O&M ~2%/yr of capex (compressed-H2 storage; DEA Energy Storage / NREL H2A)
# Mandatory cascade storage (opt-in, MANDATORY_STORAGE=1). A refuelling station physically CANNOT
# dispense without a high-pressure cascade buffer: fast-fill (SAE J2601) draws from 350/700-bar banks at
# a burst rate far above the electrolyser's steady output, so on-site storage is a must-have, not an
# optional candidate. Off by default the tank stays a free (InvestmentLo=0) candidate and existing cases
# are unchanged. When on, the tank build is floored at a physical buffer -- the model must build at least
# MANDATORY_STORAGE_KG of cascade (~1 day of HRS dispensing, 1500 kg/day at the Gothenburg station),
# expressed as a build-fraction lower bound on the TANK_STORAGE_KG nameplate. This closes the unphysical
# no-storage/import-the-peaks corner (see notes/methods_pressure_resolved_topology_spec.md sec 7a).
MANDATORY_STORAGE = os.environ.get("MANDATORY_STORAGE", "0") == "1"
MANDATORY_STORAGE_KG = float(os.environ.get("MANDATORY_STORAGE_KG", "1500.0"))   # min cascade buffer (kgH2)
MANDATORY_STORAGE_LO = min(1.0, MANDATORY_STORAGE_KG / TANK_STORAGE_KG)          # build-fraction floor

# Station cascade (opt-in, STATION_CASCADE=1). Cleaner alternative to MANDATORY_STORAGE: the
# dispensing cascade is FIXED infrastructure of the refuelling station (it comes with the station),
# not a VPP investment. Modelled as a non-candidate storage of fixed size STATION_CASCADE_KG that is
# always fully present -- no capex in the VPP objective, no build-fraction floor. The VPP then invests
# only in the electrolyser, the compressor (which fills the cascade) and the fuel cell. This removes
# the tension of "co-sizing a tank we also floor to a mandatory minimum" and makes the cascade's
# presence structural (a station always has one) rather than forced. Pair with PRESSURE_NODES=1.
STATION_CASCADE = os.environ.get("STATION_CASCADE", "0") == "1"
STATION_CASCADE_KG = float(os.environ.get("STATION_CASCADE_KG", str(MANDATORY_STORAGE_KG)))  # fixed cascade (kgH2)
# Per-product LER endurance windows (minutes), per the Svenska kraftnat FCR technical
# requirements: a limited-energy reservoir must sustain full activation for 20 min (FCR-D) and
# 60 min (FCR-N), each direction. The model holds them as separate parameters
# (pEleGenEnduranceFCRD / pEleGenEnduranceFCRN). Verified: FCR-N=60 was already binding, so the
# FCR-D 60->20 correction is a no-op on the results.
FCR_ENDURANCE_MIN_D = float(os.environ.get("FCR_ENDURANCE_MIN_D", "20"))
FCR_ENDURANCE_MIN_N = float(os.environ.get("FCR_ENDURANCE_MIN_N", "60"))
COMPRESSOR_NAMEPLATE = float(os.environ.get("COMPRESSOR_NAMEPLATE_KG", "400.0"))  # kgH2/h compressor throughput candidate max (raise with a bigger electrolyser fleet so it stays interior)
# Compressor: capex enters already annualized. ~800 kEUR overnight, 20 yr @ 5%.
# 20 yr @ 5% (CRF 0.0802) + fixed O&M ~4%/yr of capex (compression is maintenance-heavy; NREL H2A).
COMPRESSOR_CAPEX_ANNUAL = 800_000.0 * EUR_SEK * (0.0802 + 0.04)   # SEK/yr, full nameplate (capital + fixed O&M)

# Standalone compressor asset (opt-in PRESSURE_NODES): a Technology="Compressor" row in the
# hydrogen-generation table that raises H2 from the 30-bar bus (Node2) to the 500-bar cascade
# (Node3), drawing electricity per kg compressed and gating the electrolyser's FCR-down. Replaces
# the tank-welded compressor. 30->500 bar specific energy ~2.3 kWh/kg (Rothuizen & Rokni 2014;
# Argonne HDSAM); capex/nameplate reuse the welded-compressor economics above.
COMPRESSOR_UNIT = "Comp_01"
COMPRESSOR_KWH_KG = float(os.environ.get("COMPRESSOR_KWH_KG", "2.30"))   # 30->500 bar

# Tank ratings + empty start; charge/discharge rate matched to the fleet.
TANK_DATA = {"MaximumPower": 400.0, "MaximumCharge": 400.0, "MaximumStorage": TANK_STORAGE_KG,
             "InitialStorage": 0.0, "MinimumStorage": 0.0}

# --- fuel cell (hydrogen-to-power, h2e): sized candidate that also provides FCR ---
# A PEM fuel cell co-located with the tank at Node3: it burns stored hydrogen to make
# electricity, is sized by the model, and bids FCR -- upward by ramping output (backed by
# stored H2 over an endurance window, the dual of the electrolyser's down-endurance) and
# downward by backing output off. Always a candidate in the case data, but DISABLED in
# every variant except A4/A5 (see VARIANTS / _apply_variant), so the other cases are the
# no-fuel-cell baseline. ProductionFunction > 0 puts it in model.h2e.
FUELCELL_UNIT = "FC_01"
FUELCELL_MAX_POWER = 2000.0       # kW electrical nameplate (2 MW PEM fuel-cell candidate)
# Efficiency (kWh_e per kgH2) and capex are env-overridable so a spoke can sweep the
# fuel-cell break-even (the point at which H2-to-power enters the optimal design).
# FC_PROD_FUNC default 17 kWh_e/kg ~= 51% LHV; FC_CAPEX_EUR_KW default 1200 EUR/kW.
FUELCELL_PROD_FUNC = float(os.environ.get("FC_PROD_FUNC", "17.0"))    # kWh_e per kgH2 (~50% LHV; H2 LHV ~33.3 kWh/kg)
FUELCELL_CAPEX_EUR_KW = float(os.environ.get("FC_CAPEX_EUR_KW", "1200.0"))    # PEM fuel-cell stationary capex (~EUR/kW)
FUELCELL_CAPEX = FUELCELL_CAPEX_EUR_KW * EUR_SEK * FUELCELL_MAX_POWER  # SEK, full unit
FUELCELL_CRF = 0.0963             # capital recovery, ~15 yr @ 5%
FUELCELL_FOM = 0.05               # fixed O&M ~5%/yr of capex (DEA "12 LT-PEMFC CHP": 69.1 kEUR/MW/yr @ 1382 EUR/kW)
# Fuel-cell stack wear + variable O&M, per kWh of ELECTRICITY OUTPUT (applied via the generic
# pEleGenOMVariableCost x vEleTotalOutput term). Previously ZERO: the degradation-cost term only
# covers electric storage (egs), so a generator fuel cell had no wear cost at all and was
# under-costed. Basis: PEM-FC replaceable stack ~500 EUR/kW over ~30 MWh/kW lifetime output
# (~0.017 EUR/kWh) plus minor O&M. Only bites in the fuel-cell variants (A4/A5); FC is disabled
# elsewhere. Calibrate as needed.
FUELCELL_OM_VAR = round(0.017 * EUR_SEK, 4)   # ~0.19 SEK/kWh_e out

# --- node topology (5-node hydrogen valley) --------------------------------
# A spatial layout that gives the electricity and hydrogen networks a real role
# (see CASE_NOTE.md for the figure):
#   Node0  point of common coupling (PCC)    (the grid connection / retailer -- the only grid interface)
#   Node1  plant busbar + wind + battery     (behind the meter, feeds the electrolyser)
#   Node2  electrolyser                      (draws power, produces H2)
#   Node3  H2 compressor + tank + fuel cell  (draws power for the compressor)
#   Node4  H2 offtake                        (shipping / heavy transport, sold)
# The grid connection sits at the PCC (Node0), so all import/export crosses the sized connection;
# the wind, battery, and electrolyser are behind it. Electricity flows Node0 -> Node1 -> Node2 -> Node3;
# hydrogen flows Node2 -> Node3 -> Node4.
NODE_PCC = "Node0"
NODE_GRID = "Node1"
NODE_ELY = "Node2"
NODE_STORE = "Node3"
NODE_DEM = "Node4"
# PCC split: optionally isolate the grid connection (retailer) at its own pendant node (Node0). Left
# OFF: the connection sits at the plant busbar (Node1, with the wind and battery), which is already a
# valid point of common coupling and correctly binds the grid exchange. Hanging the PCC off a single
# line (PCC_SPLIT=1) fights the DC power flow and drives the plant islanded, so it is not used.
PCC_SPLIT = os.environ.get("PCC_SPLIT", "1") == "1"
NEW_NODES = ([NODE_PCC] if PCC_SPLIT else []) + [NODE_STORE, NODE_DEM]   # Node0 (PCC) new when split; Node3/Node4 always; Node1/Node2 in base
ZONE = "Zone1"                            # one zone -> one FCR market for the whole VPP

# Networks as (InitialNode, FinalNode) pairs. The base case ships a Node1-Node2
# electricity line and a (inactive) Node1-Node2 pipe; we lay out the lines the VPP
# needs and size them from the base line's template. The Node0-Node1 line is the physical
# grid-connection cable; the contracted connection capacity is the sized import/export limit at Node0.
# Delivery-compression feature (opt-in, DELIVERY_COMPRESSION=1): charge the electricity to compress
# each delivered kg to the sector's dispensing pressure, drawn at the demand node. Off by default so
# existing cases and goldens are unchanged. When on, the demand node (Node4) is connected to the
# electricity network (its dispensing compressor draws power there) and each sector gets a per-kg
# compression intensity below.
DELIVERY_COMPRESSION = os.environ.get("DELIVERY_COMPRESSION", "0") == "1"
# Pressure-resolved topology (opt-in, PRESSURE_NODES=1): resolve the H2 nodes by pressure --
# Node2 = 30-bar bus (electrolyser, industrial demand, port import/export), Node3 = 500-bar cascade
# (tank + fuel cell + compressor discharge), Node4 = 350-bar dispensing (HRS + ship, filled by
# let-down). The standalone compressor (Comp_01) is the ONLY 30->500 path, so the direct Node2->Node3
# H2 pipe is dropped and every kg going high-pressure is metered + compressed; let-down pipes
# Node3->Node4 (500->350 dispensing) and Node3->Node2 (500->30, feeds the fuel cell and low-pressure
# offtake from storage) carry the return. Off by default so existing cases/goldens are unchanged.
PRESSURE_NODES = os.environ.get("PRESSURE_NODES", "0") == "1"
ELE_LINES = ([(NODE_PCC, NODE_GRID)] if PCC_SPLIT else []) + [(NODE_GRID, NODE_ELY), (NODE_ELY, NODE_STORE)] \
            + ([(NODE_STORE, NODE_DEM)] if DELIVERY_COMPRESSION else [])
H2_LINES = ([(NODE_STORE, NODE_DEM), (NODE_STORE, NODE_ELY)] if PRESSURE_NODES
            else [(NODE_ELY, NODE_STORE), (NODE_STORE, NODE_DEM)])
LINE_TTC = float(os.environ.get("LINE_TTC_KW", "15000.0"))   # kW (electricity, 15000x0.67 = 10.05 MW grid) / kgH2-h; raise to grow the sized grid connection for imports
LINE_SEC = 0.67                  # security factor (matches the base case)

# --- grid-connection investment (industrial VPP) ---------------------------
# An industrial VPP builds its own grid connection up to the point of common coupling
# (transformer station, HV switchgear, cable) -- real project capex the DSO does not bear. The
# model sizes ONE bidirectional connection capacity that must cover both import (electrolyser
# load, battery charge) and export (wind, battery / fuel-cell discharge) and pays this annualized
# per-kW charge (on TOP of the effekttariff, which prices ongoing peak USE, not the connection
# CAPEX). Written to the Parameter file as 'EleConnInvestCost' (SEK/kW/yr); the model reads
# pParEleConnInvestCost and adds the connection variable + capacity caps + cost. 0 disables it.
# Nordic-sourced. DEA does NOT give a transferable grid-connection cost (grid connection is
# socialised in Denmark). The Swedish reference is Svenska kraftnat's connection-charge principle
# (2024), under which large connections are increasingly "DEEP" -- the customer pays the dedicated
# connection assets AND a network-reinforcement contribution. The dedicated connection (transformer
# + HV switchgear + cable to the PCC) runs ~0.05-0.20 MEUR/MW; take 120 EUR/kW as a Nordic midpoint
# (SHALLOW). Deep reinforcement is highly site-specific (can dominate) and is left as a scenario
# lever, not a fixed unit cost. Connection assets 40 yr @ 5% (CRF 0.0583). Horizon pro-rated.
CONNECTION_CAPEX_EUR_KW = 120.0
CONNECTION_CRF = 0.0583          # 40 yr @ 5% (connection assets, longer-lived than the stack)
# Connection-cost knob (spoke): 0 = free/socialised connection, 1 = shallow baseline (120 EUR/kW),
# >1 = deep charge (adds a site-specific network-reinforcement contribution).
CONNECTION_SCALE = float(os.environ.get("CONNECTION_SCALE", "1.0"))
CONNECTION_CAPEX = round(CONNECTION_CAPEX_EUR_KW * CONNECTION_CRF * EUR_SEK * CAPEX_HORIZON_FACTOR * CONNECTION_SCALE, 5)   # SEK/kW/yr, horizon-scaled

# --- electricity supply ----------------------------------------------------
# Grid connection at Node1. A VPP electrolyser drawing hundreds of kW needs more
# than the home's 100 kW, so the grid buy/sell allowance is raised.
ELE_RETAILER = "EleR_01"
ELE_BUY_CAP = float(os.environ.get("ELE_BUY_CAP_KW", "15000.0"))   # kW grid buy/sell allowance; raise with LINE_TTC_KW so imports aren't capped below the sized connection

# --- industrial electricity tariff -----------------------------------------
# The base case ships a HOUSEHOLD tariff (energy tax 0.549 SEK/kWh, 25% VAT, a
# 65 SEK/kW monthly demand charge) -- the wrong price signal for an industrial
# VPP electrolyser, which never imports grid power under it. Swedish
# manufacturing industry that competes internationally pays electricity energy
# tax at the EU minimum of 0.6 ore/kWh (refunded by Skatteverket), and a
# VAT-registered business reclaims VAT, so it is not a real cost. Electrolysis
# for hydrogen is such an industrial process. (Skatteverket, skatt pa el.)
INDUSTRIAL_ENERGY_TAX = 0.006    # SEK/kWh, EU minimum (0.6 ore) for industry
INDUSTRIAL_MOMS = 0.0            # VAT reclaimed by a VAT-registered business
# A multi-MW electrolyser connects at high voltage (hogspanning), not on the
# household low-voltage tariff. We adopt Vattenfall Eldistribution's 2025
# high-voltage industrial power tariff N2T: a 34 SEK/kW monthly demand charge on
# the monthly peak, a 28,500 SEK/month fixed fee, and a 6.4 ore/kWh off-peak
# transfer fee (the plant imports almost nothing, and what little it does is in
# cheap off-peak hours). (Vattenfall Eldistribution, Effekttariffer 2025, Foretag.)
INDUSTRIAL_POWER_TARIFF = 34.0    # SEK/kW/month, N2T manadseffektavgift (single highest hour, all months)
INDUSTRIAL_FAST_AVGIFT  = 28500.0 # SEK/month, N2T fixed fee
INDUSTRIAL_OVERFORING   = 0.064   # SEK/kWh, N2T overforingsavgift, ovrig tid (off-peak transfer)
# Corrected N2T (Vattenfall Eldistribution Effekttariffer 2025, app. rules 6-8): the
# manadseffekt is the SINGLE highest hourly import of the month (NumberPowerPeaks=1, not a
# top-k average), and there is a SECOND demand charge -- the hogbelastningsavgift -- on the
# single highest import during hoglasttid (weekdays 06-22, Jan-Mar/Nov-Dec), plus a
# time-of-use transfer fee (hoglasttid rate > ovrig-tid rate).
INDUSTRIAL_NUMBER_PEAKS    = 1     # N2T manadseffekt = single highest hour
INDUSTRIAL_HIGHLOAD_TARIFF = 49.0  # SEK/kW/month, N2T hogbelastningsavgift (hoglasttid winter months)
INDUSTRIAL_OVERFORING_HIGH = 0.122 # SEK/kWh, N2T overforingsavgift, hoglasttid
N2T_HIGHLOAD_MONTHS   = {1, 2, 3, 11, 12}     # hoglasttid months: Jan, Feb, Mar, Nov, Dec
N2T_HIGHLOAD_HOLIDAYS = {  # 2025 winter-month Swedish helgdagar excluded from hoglasttid (app. rule **)
    "2025-01-01", "2025-01-06", "2025-12-24", "2025-12-25", "2025-12-26", "2025-12-31"}
# PowerTariff (demand charge) and Fastavgift (fixed fee) are MONTHLY charges that
# the model sums over the months in the horizon. On a representative-day horizon
# they would be charged as a full month -- ~30x too dear -- so they are scaled to
# the modeled window, the same horizon reconciliation as the capex. N_MONTHS is
# the number of distinct months the horizon spans (1 representative day -> 1; the
# full-year run -> 12, where the factor returns to ~1).
HOURS_PER_MONTH = 8760.0 / 12.0
N_MONTHS = 12 if HORIZON == "year" else 1
MONTHLY_HORIZON_FACTOR = (HORIZON_HOURS / HOURS_PER_MONTH) / N_MONTHS

# --- multi-sector hydrogen demand (Vastra Gotaland offtakers) --------------
# The offtake is several PRICE-RESPONSIVE demand units at Node4, one per real west-
# coast sector (notes/data_sources.bib). Each is a flexible HydrogenDemand with its
# own hourly PROFILE (VarMaxDemand) and PRICE (the model's per-demand price
# extension): the VPP serves a sector up to its profile whenever the sector price
# covers the marginal cost. The differing shapes drive storage and the FCR split.
#   sector unit : (avg kgH2/h, EUR/kgH2 price, profile shape)
# Per-sector willingness-to-pay (EUR/kgH2), most-recent sourcing (2025-2026). Large uncertainty
# (+-30-50%), subsidy-shaped; no transparent per-sector spot exists. Benchmarks: EU-compliant green-H2
# PRODUCTION cost ~7.5 EUR/kg (Platts / S&P Global, assessed to Dec 2025; Spain avg 7.49), Nordic
# potential 4-6 EUR/kg with own wind (Implement Consulting 2024; European Hydrogen Observatory 2024).
# EU Hydrogen Bank subsidy premiums: IF24 (2nd, 2025) 0.20-0.60 general / 0.45-1.88 maritime;
# IF25 (3rd, results May 2026) 0.57-3.49 EUR/kg -- the premium is a top-up, NOT the sale price.
# Ordering maritime > HRS-wholesale ~ industrial, all above the Nordic production floor.
#   sector unit : (avg kgH2/h, EUR/kgH2 price, profile shape)
DEMAND_SECTORS = {
    # HRS delivered/wholesale ~8 (Hylane/H2 Mobility 2025 fleet deal 8; German retail pump 12-18)
    "HydD_HRS":  (62.5, 8.0, "hrs"),    # Port of Gothenburg HRS, 1500 kg/day, daytime-peaked
    # industrial contracted green-H2 4.5-6.5, buyers resist >5 vs ~2 grey (OIES 2025) -> marginal
    # customer; at 5 it sits BELOW the ~7.5 EUR/kg current EU production cost, so it needs the
    # Nordic cheap-power advantage + subsidy to clear (a realistic tension the model will expose).
    "HydD_Ind":  (42.0, 5.0, "flat"),   # Preem/Stenungsund feedstock, ~1000 kg/day flat baseload
    # maritime: no clean spot; FuelEU Maritime + the 3-4x maritime auction premium (H2 Bank IF24/IF25)
    "HydD_Ship": (21.0, 6.0, "ship"),   # Port bunkering, ~500 kg/day, batchy (storage driver)
}
DEMAND_TEMPLATE = "HydD1"            # base demand row, cloned per sector
# Under PRESSURE_NODES each sector sits at its dispensing-pressure node: industrial at the 30-bar
# bus (Node2, served uncompressed straight off the electrolyser), HRS + ship at the 350-bar node
# (Node4, filled by let-down from the 500-bar cascade). Off, every sector stays at Node4 as before.
SECTOR_NODE = {"HydD_HRS": NODE_DEM, "HydD_Ship": NODE_DEM, "HydD_Car": NODE_DEM, "HydD_Ind": NODE_ELY}
# Per-sector delivery-compression intensity (kWh electricity per kg served), used only when
# DELIVERY_COMPRESSION=1. Each sector's dispensing PRESSURE sets its compression energy:
#   HRS (heavy trucks) -> 350 bar, ~2.05 kWh/kg (DOE Record #9013, ref [10]; SAE J2601 H35).
#   Ship bunkering     -> 350 bar compressed gas: near-term marine H2 is stored at ~350 bar on ferries
#      and short-sea vessels (e.g. Norway's MF Hydra), so it carries the same ~2.05 kWh/kg dispensing
#      compression as the HRS. Env-tunable: raise DELIVERY_COMP_SHIP to ~2.36 for a 500-bar cascade, or
#      ~10 kWh/kg for a liquid-H2 (deep-sea) bunkering scenario (LH2 liquefaction, IEA/DOE).
#   Industrial feedstock -> taken at ~pipeline/electrolyser pressure (~30 bar), no dispensing compression.
# Same kWh/kg convention as the tank's MaxCompressorConsumption column.
DELIVERY_COMP_KWH_KG = {"HydD_HRS":  float(os.environ.get("DELIVERY_COMP_HRS",  "2.05")),   # 350 bar
                        "HydD_Ind":  0.0,                                                    # ~30 bar
                        "HydD_Ship": float(os.environ.get("DELIVERY_COMP_SHIP", "2.05"))}   # 350 bar (compressed)

# 700-bar car dispensing (opt-in, SEVEN_HUNDRED_BAR=1). SENSITIVITY ONLY, default OFF -- NOT a headline
# case: the Port of Gothenburg HRS is a heavy-truck station (350 bar), and light-duty road transport is
# expected to electrify (battery-electric) rather than run on hydrogen, whose durable niche is heavy
# transport. So a 700-bar car offtake is a "what-if" probe of the two-stage compression cost, not a
# grounded demand; the year run confirms it is economically inert. Kept as a toggle for completeness.
# When on: split the HRS offtake into 350-bar heavy-duty
# (trucks, served from the cascade by letdown) and 700-bar cars, which need a booster (500->900 bar)
# plus pre-cooling on top of the 350-bar dispensing energy. Off by default the HRS stays a single
# 350-bar sector, so existing cases and goldens are unchanged. When on, a fraction H2_CAR_FRACTION of
# the HRS volume moves to a 700-bar car sector and the total HRS volume is preserved. The car sector's
# higher delivery-compression intensity (2.05 kWh/kg for the 350-bar stage + 0.30 booster 500->900 +
# 0.18 pre-cool = 2.53 kWh/kg; DOE Record #9013, ref [10] / Table 1) is the "two-stage compression"
# cost, and it only bites when DELIVERY_COMPRESSION=1 (the mechanism that charges dispensing power at
# the demand node). Car willingness-to-pay defaults to the HRS wholesale price so the variant isolates
# the extra 700-bar energy, not a price edge; raise H2_CAR_PRICE for the higher car retail (12-18 EUR/kg).
SEVEN_HUNDRED_BAR = os.environ.get("SEVEN_HUNDRED_BAR", "0") == "1"
H2_CAR_FRACTION = float(os.environ.get("H2_CAR_FRACTION", "0.3"))   # share of HRS volume that is 700-bar cars
H2_CAR_PRICE = float(os.environ.get("H2_CAR_PRICE", "8.0"))         # EUR/kgH2 (defaults to HRS wholesale)
DELIVERY_COMP_700 = float(os.environ.get("DELIVERY_COMP_700", "2.53"))  # 2.05 (350 bar) + 0.30 booster + 0.18 pre-cool
if SEVEN_HUNDRED_BAR:
    _hrs_avg, _hrs_price, _hrs_shape = DEMAND_SECTORS["HydD_HRS"]
    DEMAND_SECTORS["HydD_HRS"] = (round(_hrs_avg * (1.0 - H2_CAR_FRACTION), 4), _hrs_price, _hrs_shape)
    DEMAND_SECTORS["HydD_Car"] = (round(_hrs_avg * H2_CAR_FRACTION, 4), H2_CAR_PRICE, _hrs_shape)
    DELIVERY_COMP_KWH_KG["HydD_Car"] = DELIVERY_COMP_700

# --- experiment-matrix variant switch (notes/experiment_matrix.md) ---------
# VARIANT selects one run of the experiment matrix. Each ID maps to the knobs that
# distinguish it from the A3 baseline (hybrid, both FCR, elastic, degradation on,
# part-load PWL electrolyser). Unset keys keep the baseline. Set with VARIANT=<id>;
# unset (or A3/B3/C1/D0) builds the baseline. The reserve / asset-mix / degradation
# / PWL knobs are applied as a post-build patch on the case CSVs (_apply_variant);
# the demand-mode knob feeds DEMAND_MODE below.
#   disable     : candidate units forced to zero build (InvestmentUp=InvestmentLo=0)
#   reserve     : both | none | fcrn | fcrd   (NoFCRD/NoFCRN bid flags)
#   demand      : elastic | firm
#   degradation : True (baseline) | False   (zero electrolyser DegradationCost + battery DoD price)
#   pwl         : True (baseline part-load PWL -> integer, heavy) | False (constant-eta, S2)
#   battery_rt  : None (baseline) | low      (scale battery round-trip efficiency)
VARIANT = os.environ.get("VARIANT", "").upper()

ELECTROLYSER_UNITS = [f"{t}_{m:02d}" for t, (n, *_) in ELECTROLYSER_TECHS.items()
                      for m in range(1, n + 1)]
AEL_UNITS = [u for u in ELECTROLYSER_UNITS if u.startswith("AEL")]
PEM_UNITS = [u for u in ELECTROLYSER_UNITS if u.startswith("PEM")]
H2_CANDIDATES = ELECTROLYSER_UNITS + [TANK_UNIT]
BATTERY_RT_LOW_FACTOR = 0.95     # S3: -5% on each of charge/discharge efficiency
# To DISABLE a candidate we cap its build fraction at a tiny positive value. A plain
# InvestmentUp = 0 does not work: the model reads any InvestmentUp <= 0 as "unset" and
# defaults it back to 1.0 (oM_InputData: pGenInvestmentUp.where(>0, other=1.0)). A small
# positive cap survives that check and hard-bounds the build to ~0 (capacity = cap x
# nameplate), so the unit stays a candidate but cannot build.
DISABLE_UP = 1e-9

VARIANTS = {
    "A1": {"disable": H2_CANDIDATES, "fuelcell": False},  # asset mix: BESS-only (no H2 chain, no fuel cell)
    "A2": {"disable": list(BESS_UNITS)},     # asset mix: hydrogen-only (electrolyser + tank + fuel cell)
    "A3": {},                                # hybrid baseline (= B3 = C1 = D0); fuel cell offered, not built
    "B0": {"reserve": "none"},               # reserve: no FCR (energy + H2 only)
    "B1": {"reserve": "fcrn"},               # reserve: FCR-N only
    "B2": {"reserve": "fcrd"},               # reserve: FCR-D only
    "B3": {},                                # reserve: both (= A3)
    "C1": {},                                # demand: elastic (= A3)
    "C2": {"demand": "firm"},                # demand: firm HRS contract
    "D0": {},                                # technology: free AEL+PEM (= A3)
    "D1": {"disable": PEM_UNITS},            # technology: AEL-only
    "D2": {"disable": AEL_UNITS},            # technology: PEM-only
    "S1": {"degradation": False},            # spoke: degradation off
    "S2": {"pwl": False},                    # spoke: constant-eta efficiency (baseline is PWL)
    "S3": {"battery_rt": "low"},             # spoke: battery round-trip variant
    "S4": {"export_fee": 0.05},              # spoke: 0.05 SEK/kWh grid fee on exported surplus
    "S5": {"ele_reserve": "fcrn"},           # spoke: electrolyser cannot meet FCR-D 7.5s activation -> FCR-N only (battery provides all FCR-D)
    # (the fuel cell is now a baseline candidate in every case, so the former A4/A5
    #  fuel-cell variants are subsumed by A3 and A2 and have been removed.)
}
if VARIANT and VARIANT not in VARIANTS:
    raise SystemExit(f"unknown VARIANT={VARIANT!r}; known: {sorted(VARIANTS)}")
_VSPEC = VARIANTS.get(VARIANT, {})
# Export-fee sensitivity knob (S4): a per-kWh charge on exported surplus, default off. It is a
# conservative proxy for the production grid fee and balancing cost on exports that the
# deterministic full-spot model omits (a real Swedish HV producer earns a small net natnytta
# credit instead, so this is a worst case).
EXPORT_FEE = float(_VSPEC.get("export_fee", 0.0))   # SEK/kWh

# Demand mode for the headline (HRS) sector; the other sectors stay price-elastic in
# every mode. The VARIANT switch wins; otherwise H2VPP_DEMAND_MODE; FIRM=1 still selects
# "firm" (back-compat).
#   elastic  VarMin=0, VarMax=shaped profile     -- serve only when profitable
#            (no cumulative obligation; behaves like power->H2 arbitrage)
#   firm     VarMin=VarMax=shaped profile        -- must-serve every hour (soft, HNS)
#   shift    VarMax=shaped profile + load shift  -- move demand in time, day/week/month
#            total unchanged (the model's pHydDemShiftedSteps/pHydDemFlexPercent)
DEMAND_MODE = (_VSPEC.get("demand")
               or os.environ.get("H2VPP_DEMAND_MODE")
               or ("firm" if os.environ.get("FIRM") == "1" else "elastic")).lower()
SHIFT_SECTOR = "HydD_HRS"                                                  # sector the mode applies to
SHIFT_STEPS = int(os.environ.get("H2VPP_SHIFT_STEPS", "24"))              # shift window (24=daily, 168=weekly, 730=monthly)
SHIFT_FLEX_PERCENT = float(os.environ.get("H2VPP_SHIFT_FLEX_PERCENT", "0.5"))  # per-hour deviation as a fraction of the profile

# Import backstop at Node4 (an expensive merchant-H2 fallback; the retailer no
# longer forces a sale -- the price-responsive demands are the offtake). SEK/kgH2.
H2_RETAILER = "HydR_01"
H2_IMPORT_PRICE = 12.0 * EUR_SEK     # ~12 EUR/kgH2 merchant-H2 backstop
H2_IMPORT_CAP = 200.0                # kgH2/h backstop import allowance
# H2 export (opt-in, H2_EXPORT=1): sell surplus green H2 to the port market at a per-kg price -- the
# "valley as H2 supplier to the Gothenburg port" revenue stream. Off by default (no sell capacity, sell
# price 0), so existing cases are unchanged. Priced at the Nordic green-H2 production floor (~5.5 EUR/kg;
# Nordic LCOH 4-6 with own wind, Implement Consulting 2024 / European Hydrogen Observatory 2024), so
# selling is a break-even-plus outlet, not a windfall, and stays below the ~8 EUR/kg HRS retail. Set in
# SEK (x EUR_SEK); the native-EUR pass divides it back like other prices.
H2_EXPORT = os.environ.get("H2_EXPORT", "0") == "1"
H2_EXPORT_PRICE = float(os.environ.get("H2_EXPORT_PRICE", "5.5")) * EUR_SEK   # SEK/kgH2 (port, Nordic LCOH)
H2_EXPORT_CAP = 200.0                # kgH2/h export allowance to the port
# H2 port import (opt-in, H2_IMPORT_PORT=1): buy CERTIFIED-GREEN (RFNBO) H2 from the port market as a
# BACKSTOP -- the mirror of the export stream. Off by default the retailer keeps the 12 EUR/kg merchant
# backstop, so existing cases are unchanged. On, the buy price is the prevailing EU green-H2 production
# cost (~7.5 EUR/kg; Platts / S&P Global, EU-compliant green H2 assessed at EUR 7.49/kg in Spain to Dec
# 2025). This sits ABOVE the VPP's own Nordic-wind production cost, so the plant produces its own H2 and
# leans on the port only when its own production is dearer (high-spot hours) -- import is a genuine
# backstop, not a cheaper substitute. Because the import is RFNBO-certified green, reselling it into the
# green offtake keeps additionality intact. Import price stays ABOVE the export price (7.5 > 5.5) so a
# buy-then-sell round-trip always loses money. Set in SEK (x EUR_SEK); native-EUR pass divides it back.
H2_IMPORT_PORT = os.environ.get("H2_IMPORT_PORT", "0") == "1"
H2_IMPORT_PORT_PRICE = float(os.environ.get("H2_IMPORT_PORT_PRICE", "7.5")) * EUR_SEK   # SEK/kgH2 (EU green backstop, Platts 2025)
H2_IMPORT_PORT_CAP = 200.0           # kgH2/h import allowance from the port

# Port delivery by trailer / ship (opt-in, H2_PORT_TRAILER=1): a non-GW VPP has no dedicated H2 pipeline
# -- the Nordic Hydrogen Route (Bothnian Bay) reaches FID only ~2027 and operation in the early 2030s,
# and it is nowhere near the Gothenburg west coast -- so near-term port exchange is by compressed-gas
# tube trailer or ship. That makes the flows BATCHY and DAYTIME, not a 24/7 pipeline flow. When on, the
# port import/export is (a) restricted to a working-hours delivery window [START, END) and (b) capped at
# a daily volume of H2_PORT_TRAILERS_PER_DAY x H2_PORT_TRAILER_KG, applied as the equivalent hourly rate
# over the window. Composite tube trailer ~500-1100 kg/trip at 500 bar (Elgowainy et al. 2018,
# doi:10.1016/j.ijhydene.2018.01.037; DOE "Hydrogen Tube Trailers"); ~800 kg is a mid composite payload.
# No minimum offtake (spot trailer purchase, not a take-or-pay pipeline contract). Off by default (flat
# hourly cap, all hours). The window is enforced economically -- outside it the import price reverts to
# the 12 EUR/kg merchant backstop and the export price drops to 0 -- because the retailer cap is a scalar
# (no per-hour energy-limit series on the H2 retailer), so a hard hourly gate would need a model change.
H2_PORT_TRAILER = os.environ.get("H2_PORT_TRAILER", "0") == "1"
H2_PORT_WINDOW_START = int(os.environ.get("H2_PORT_WINDOW_START", "6"))    # delivery window opens (hour of day)
H2_PORT_WINDOW_END = int(os.environ.get("H2_PORT_WINDOW_END", "22"))       # delivery window closes (exclusive)
H2_PORT_TRAILERS_PER_DAY = float(os.environ.get("H2_PORT_TRAILERS_PER_DAY", "4"))   # trailer/ship deliveries per day
H2_PORT_TRAILER_KG = float(os.environ.get("H2_PORT_TRAILER_KG", "800"))    # kgH2 per composite 500-bar trailer
_PORT_WINDOW_H = max(1, H2_PORT_WINDOW_END - H2_PORT_WINDOW_START)
# Daily cap spread over the window as an equivalent hourly rate (kgH2/h): 4 x 800 / 16 h = 200 kg/h.
H2_PORT_HOURLY_CAP = H2_PORT_TRAILERS_PER_DAY * H2_PORT_TRAILER_KG / _PORT_WINDOW_H


def _port_window_mask():
    """Boolean per-load-level mask, True inside the trailer/ship delivery window. Shares the
    2025-01-01 + HORIZON_START_HOUR clock with the demand profiles, prices and wind."""
    idx = pd.date_range("2025-01-01T00:00:00", periods=N_LOADLEVELS, freq="h") \
        + pd.Timedelta(hours=HORIZON_START_HOUR)
    hod = idx.hour.to_numpy()
    return (hod >= H2_PORT_WINDOW_START) & (hod < H2_PORT_WINDOW_END)

# --- frequency markets -----------------------------------------------------
# Per-product reserve requirement (kW), overwriting the base value (hundreds of
# kW, sized for a far larger system). Reserve provision is bounded above by this
# requirement (sum of all bids <= requirement) and is rewarded at the FCR price,
# so it must sit ABOVE what the battery can offer alone (~50 kW): otherwise the
# battery fills it and there is no room left for the electrolyser's bids to be
# accepted. With it higher, both assets appear in the solution. The realized bids
# here are limited by each asset's physical headroom, not by this cap.
FCR_REQUIRE = 5000.0
FCRD_PRODUCTS = ["FCRD_Up", "FCRD_Down"]
FCRN_PRODUCTS = ["FCRN_Up", "FCRN_Down"]

# --- unit commitment -------------------------------------------------------
# THREE_STATE selects the operating model:
#   True  -> binary commitment, so the three-state (on / standby / off)
#            electrolyser is meaningful. Solves as a MILP. This is the realistic
#            operating model the paper wants.
#   False -> LP relaxation (continuous commitment, no ramps, no min up/down).
#            Mirrors the model's own working ElectrolyserFCR case; reproducible.
#
# Three-state + FCR + investment sizing solves fine (no model bug). Note the
# economics: under binary commitment the electrolyser is only built and run, and
# so only bids FCR, when running it actually pays -- which needs realistic CAPEX,
# electricity and FCR prices and a hydrogen demand it must self-produce. With the
# illustrative costs here it stays off under THREE_STATE = True. See CASE_NOTE.md
# and notes/data_sources.md (cost units must be re-based before real prices go in).
# NOTE: electrolyser minimum up/down time is intentionally NOT modelled. e2h units are free flexible
# loads (commitment tied to consumption); imposing min-time/commitment on them drives production to zero
# (verified on Comillas, 2026-07-09), and physically an electrolyser cycles in seconds-minutes, not hours.
# The production RAMP below is the meaningful, LP-preserving electrolyser-dynamics constraint.
# Electrolyser production ramp limit (opt-in, ELE_RAMP=1). Caps the hour-to-hour change in the
# electrolyser's electricity draw to ELE_RAMP_PCT of its built capacity per hour (model constraint
# eHydMaxRamp{Up,Dw}E2H, gated by IndBinGenRamps). LP-preserving (a continuous limit, no binaries). Note:
# real electrolysers ramp in seconds-minutes, so a realistic hourly cap is near non-binding; the default
# here is deliberately on the tighter side (load-following alkaline) to give the constraint a chance to
# bind -- env-tunable per technology. Off by default so existing cases are unchanged.
ELE_RAMP = os.environ.get("ELE_RAMP", "0") == "1"
ELE_RAMP_PCT = {"AEL": float(os.environ.get("AEL_RAMP_PCTH", "0.3")),    # frac of capacity per hour
                "PEM": float(os.environ.get("PEM_RAMP_PCTH", "0.6"))}    # PEM faster than alkaline
THREE_STATE = True
# Exact binary-free CVaR/sum-of-largest LP for the monthly peak charge (default on; see _edit_option).
PEAK_THRESHOLD_LP = os.environ.get("PEAK_THRESHOLD_LP", "1") == "1"
UC_OFF = ["IndBinGenOperat", "IndBinGenRamps", "IndBinGenMinTime"]
UC_ON = (["IndBinGenOperat"] if THREE_STATE else []) \
        + (["IndBinGenRamps"] if ELE_RAMP else [])


def _set_candidate(df, unit, fic, charge_rate):
    """Make `unit` a continuous (build-fraction) investment candidate.

    `fic` is the overnight cost of the full nameplate unit and `charge_rate` its
    capital-recovery factor; the model annualizes the build cost as their product.
    The charge rate also carries the horizon pro-rating (CAPEX_HORIZON_FACTOR) so
    the annual charge is matched to the modeled operating window.
    """
    if "FixedInvestmentCost" in df.columns:
        df.loc[unit, "FixedInvestmentCost"] = fic
    if "FixedChargeRate" in df.columns:
        df.loc[unit, "FixedChargeRate"] = charge_rate * CAPEX_HORIZON_FACTOR
    if "BinaryInvestment" in df.columns:
        df.loc[unit, "BinaryInvestment"] = pd.NA
    for col, val in (("InvestmentLo", 0.0), ("InvestmentUp", 1.0)):
        if col in df.columns:
            df.loc[unit, col] = val
    return df


def _edit_option(df):
    for flag in UC_OFF:
        if flag in df.columns:
            df[flag] = 0
    for flag in UC_ON:
        if flag in df.columns:
            df[flag] = 1
    # Peak charge as the exact binary-free CVaR / sum-of-largest LP (default ON). For the N2T
    # single-hour effektavgift (NumberPowerPeaks=1) it equals the monthly max exactly, so it gives
    # the identical peak cost while replacing the ~8760 big-M peak-hour binaries per year -- a large
    # MILP speed-up. Override with PEAK_THRESHOLD_LP=0 to fall back to the big-M peak-hour selection.
    df["IndPeakThresholdLP"] = 1 if PEAK_THRESHOLD_LP else 0
    return df


def _edit_parameter(df):
    # Green-H2 hourly matching ON (RFNBO additionality, EU Reg 2023/1184): the
    # productive electrolyser draw is matched hour-by-hour to the contracted PPA wind.
    # This is feasible because the PPA wind is sized to the electrolyser (WIND_MAX_POWER);
    # against a small co-located farm it would pin the electrolyser near zero.
    if "GreenH2Matching" in df.columns:
        df["GreenH2Matching"] = 1
    # Numerical-conditioning scale (model.factor1). At Port/MW scale the kW-basis
    # coefficients are O(1e3-1e4); factor1 rescales them to O(1) for solver
    # stability (the optimum is invariant). Set via the new Parameter 'Factor1' hook.
    df["Factor1"] = FACTOR1
    # Money base: the model divides every money input by this (build_case now writes RAW currency and
    # the model owns the scaling -- Step 1 of the per-unit refactor). Reciprocity with factor1 is no
    # longer a hand-managed coincidence; the model sees both.
    df["MoneyBase"] = MONEY_BASE
    # Firm-contract not-served penalty (binding but well conditioned; see HNSCOST).
    df["HNSCost"] = HNSCOST
    # Grid-connection investment (SEK/kW/yr, annualized + horizon-scaled). The model reads
    # pParEleConnInvestCost and sizes/pays a bidirectional connection capacity; 0 disables it.
    df["EleConnInvestCost"] = CONNECTION_CAPEX
    # PCC split: move the electricity reference (slack) node to the PCC (Node0). Grid exchange happens
    # at the reference node (the model couples it to the retailer and zeros it elsewhere), so the
    # reference, the retailer, and the sized connection must all sit on the PCC for it to bind.
    if PCC_SPLIT and "EleReferenceNode" in df.columns:
        df["EleReferenceNode"] = NODE_PCC
    # Electricity VOLL: realistic + well conditioned (replaces the ~1e5 base that produced the
    # 1e8 matrix coefficient breaking the year LP barrier; never-binding, so optimum-neutral).
    if "ENSCost" in df.columns:
        df["ENSCost"] = ENSCOST
    # N2T manadseffekt is the single highest hour of the month (not a top-k average).
    if "NumberPowerPeaks" in df.columns:
        df["NumberPowerPeaks"] = INDUSTRIAL_NUMBER_PEAKS
    return df


def _edit_reserve_require(df):
    for col in FCRD_PRODUCTS + FCRN_PRODUCTS:
        if col in df.columns:
            df[col] = FCR_REQUIRE
    return df


def _battery_fleet(df):
    """Replace the single BESS template with competing DURATION candidates (BESS_2h/4h/8h).
    Each is a separate electricity build candidate at the grid node; the model picks the
    duration(s) and size. Cost splits into power (USD/kW) + energy (USD/kWh) so a shorter
    duration is cheaper per MW of reserve (NREL ATB decomposition, Cole et al. 2021)."""
    template = df.loc[BESS_UNIT].copy()
    rest = df.drop(index=BESS_UNIT)
    variants = {}
    for d in BESS_DURATIONS_H:
        r = template.copy()
        for c, v in {"Node": NODE_GRID, "NoFCRD": "No", "NoFCRN": "No",
                     "MaximumPower": BESS_POWER_KW, "MaximumCharge": BESS_POWER_KW,
                     "MaximumStorage": BESS_POWER_KW * d}.items():
            if c in r.index:
                r[c] = v
        variants[f"BESS_{int(d)}h"] = r
    df = pd.concat([pd.DataFrame(variants).T, rest])
    for d in BESS_DURATIONS_H:
        capex = (BESS_POWER_CAPEX_USD_KW * BESS_POWER_KW
                 + BESS_ENERGY_CAPEX_USD_KWH * BESS_POWER_KW * d) * USD_SEK
        _set_candidate(df, f"BESS_{int(d)}h", capex, BESS_CRF + BESS_FOM)
    return df


def _edit_ele_generation(df):
    # Wind: repurpose the active rooftop-solar unit as the VPP's wind generator,
    # sited at the grid hub (Node1).
    df = df.rename(index={WIND_SOURCE_UNIT: WIND_UNIT})
    if "Technology" in df.columns:
        df.loc[WIND_UNIT, "Technology"] = "Wind"
    if "MaximumPower" in df.columns:
        df.loc[WIND_UNIT, "MaximumPower"] = WIND_MAX_POWER
    if "Node" in df.columns:
        df.loc[WIND_UNIT, "Node"] = NODE_GRID
        df.loc[BESS_UNIT, "Node"] = NODE_GRID
    # Wind procurement (WIND_MODE). Baseline "owned": the valley builds and sizes the wind, paying its
    # annualized capex (via _set_candidate below) + variable O&M, PPA flag/price off. The "ppa" spoke
    # reverts to a fixed off-site contracted PPA paid per kWh (not owned/sized). Either way the wind
    # is the additionality pool the electrolyser draw is hourly-matched against (oM_GreenHydrogen).
    if WIND_MODE == "ppa":
        if "PPA" in df.columns:
            df.loc[WIND_UNIT, "PPA"] = 1
        if "PPAPrice" in df.columns:
            df.loc[WIND_UNIT, "PPAPrice"] = PPA_PRICE_SEK_KWH
    else:
        if "PPA" in df.columns:
            df.loc[WIND_UNIT, "PPA"] = 0
        if "PPAPrice" in df.columns:
            df.loc[WIND_UNIT, "PPAPrice"] = 0.0
        if "OMVariableCost" in df.columns:
            df.loc[WIND_UNIT, "OMVariableCost"] = WIND_OM_VAR

    # Battery: the electricity FCR bidder. Clear investment costs, then replace the single
    # template with competing DURATION candidates (BESS_2h/4h/8h); the model picks the
    # duration(s) and size.
    if "FixedInvestmentCost" in df.columns:
        df["FixedInvestmentCost"] = pd.NA
    df = _battery_fleet(df)

    # Fuel cell (h2e): clone the wind row as a generic generator template, then retype it
    # as a hydrogen-to-power unit at the tank node (Node3). Added AFTER the FixedInvestmentCost
    # wipe so _set_candidate makes it a sizable candidate; _apply_variant disables it unless
    # the variant enables the fuel cell.
    fc = df.loc[WIND_UNIT].copy()
    # Fuel-cell inlet is low-pressure (~30 bar): under PRESSURE_NODES it sits on the 30-bar bus (Node2,
    # figure node Hn10), drawing stored H2 via the 500->30 let-down; its FCR-up endurance is backed by
    # the cascade reachable through that let-down (eEleFreqUpEnduranceFuelCell generalisation). In the
    # flat topology it stays co-located with the tank at Node3.
    for c, v in (("Node", NODE_ELY if PRESSURE_NODES else NODE_STORE), ("Technology", "FuelCell"),
                 ("RES", 0),    # NOT renewable: a dispatchable fuel-consuming generator that can
                                # be committed and provide FCR (else it lands in egr and its FCR
                                # bids are fixed to zero with the wind/solar).
                 ("MaximumPower", FUELCELL_MAX_POWER), ("MinimumPower", 0.0),
                 ("ProductionFunction", FUELCELL_PROD_FUNC),
                 ("NoFCRD", "No"), ("NoFCRN", "No"),
                 ("EnduranceFCRD", FCR_ENDURANCE_MIN_D), ("EnduranceFCRN", FCR_ENDURANCE_MIN_N),
                 # stack wear + variable O&M per kWh_e out (was 0 -> fuel cell under-costed)
                 ("OMVariableCost", FUELCELL_OM_VAR),
                 ("PPA", 0), ("PPAPrice", 0.0)):
        if c in fc.index:
            fc[c] = v
    df.loc[FUELCELL_UNIT] = fc
    _set_candidate(df, FUELCELL_UNIT, FUELCELL_CAPEX, FUELCELL_CRF + FUELCELL_FOM)
    # Owned wind is a sized investment candidate. Added after the FixedInvestmentCost wipe and the
    # FC clone (which copies the wind row) so neither clears it; it co-sizes with the connection.
    if WIND_MODE != "ppa":   # owned wind is a sized candidate; a PPA-mode wind stays fixed (not built)
        _set_candidate(df, WIND_UNIT, WIND_CAPEX, WIND_CRF)
        # Optional second owned wind plant: clone the (now candidate) Wind_01 row so the model can
        # invest in a second 15 MW farm. Same node, technology, nameplate, and CF profile (co-located;
        # a decorrelated second site would need its own profile). Added after the FC clone so it is
        # not overwritten, and re-set as a candidate.
        if WIND_N_PLANTS >= 2:
            df.loc[WIND_UNIT_2] = df.loc[WIND_UNIT].copy()
            _set_candidate(df, WIND_UNIT_2, WIND_CAPEX, WIND_CRF)
    return df


def _edit_ele_retail(df):
    # Move the grid connection (retailer) to the PCC node (Node0). The wind, battery, and
    # electrolyser sit behind it, so every kWh imported or exported crosses the sized connection.
    if PCC_SPLIT and "Node" in df.columns:
        df["Node"] = NODE_PCC
    # Raise the grid buy/sell allowance so the electrolyser has the electricity it
    # needs (the base 100 kW is a home connection, too small for a VPP).
    for col in ("MaximumEnergyBuy", "MaximumEnergySell", "MaxBuy", "MaxSell"):
        if col in df.columns:
            df[col] = ELE_BUY_CAP
    # Industrial tariff: EU-minimum energy tax, reclaimed VAT, and the monthly
    # demand / fixed charges scaled to the modeled horizon.
    if "EnergyTax" in df.columns:
        df["EnergyTax"] = INDUSTRIAL_ENERGY_TAX
    if "Moms" in df.columns:
        df["Moms"] = INDUSTRIAL_MOMS
    # Replace the household demand / fixed charges with the industrial N2T levels,
    # scaled to the modeled horizon (the demand and fixed fees are monthly charges).
    if "PowerTariff" in df.columns:
        df["PowerTariff"] = INDUSTRIAL_POWER_TARIFF * MONTHLY_HORIZON_FACTOR
    if "Fastavgift" in df.columns:
        df["Fastavgift"] = INDUSTRIAL_FAST_AVGIFT * MONTHLY_HORIZON_FACTOR
    if "Overforingsavgift" in df.columns:
        df["Overforingsavgift"] = INDUSTRIAL_OVERFORING
    # N2T second demand charge (hogbelastningsavgift) and the hoglasttid transfer rate.
    # The model gates both on the per-hour HighLoad mask written into the Duration table.
    df["HighLoadTariff"] = INDUSTRIAL_HIGHLOAD_TARIFF * MONTHLY_HORIZON_FACTOR
    df["OverforingHigh"] = INDUSTRIAL_OVERFORING_HIGH
    # Export-fee sensitivity (S4): charge the exported surplus a per-kWh grid fee. The model
    # books the Incentive parameter as a per-kWh credit on vEleExport, so a NEGATIVE value is a
    # charge. A dedicated Swedish high-voltage producer instead earns a small net natnytta credit,
    # so this fee is a conservative worst case. (Vattenfall Eldistribution, elproduktion 2025.)
    if EXPORT_FEE and "Incentive" in df.columns:
        df["Incentive"] = -EXPORT_FEE
    return df


def _build_fleet(df):
    """Replace the single template electrolyser with a multi-technology, modular
    fleet. Each module (AEL_01, AEL_02, PEM_01, ...) is a separate e2h investment
    candidate at Node2, cloned from the base row and given its technology's specs.
    The model then picks the optimal technology mix and module count.
    """
    template = df.loc[ELECTROLYSER_TEMPLATE].copy()
    rest = df.drop(index=ELECTROLYSER_TEMPLATE)
    modules = {}
    for tech, (n, kw, kwh_kg, capex_eur_kw, min_f, sb_f, fom_f) in ELECTROLYSER_TECHS.items():
        for m in range(1, n + 1):
            r = template.copy()
            vals = {
                "Node": NODE_ELY, "Retailer": ELE_RETAILER, "InitialPeriod": 2020,
                # Technology label per module (AEL/PEM) so the model can pick the
                # technology-specific part-load curve and report per-technology results.
                "Technology": tech,
                # ratings: an e2h's draw is bounded by MaximumCharge, not MaximumPower
                "MaximumPower": kw, "MaximumCharge": kw,
                "MinimumPower": kw * min_f, "MinimumCharge": kw * min_f,
                "ProductionFunction": kwh_kg, "StandByPower": kw * sb_f,
                "StandByStatus": "Yes" if THREE_STATE else "No",
                "FixedInvestmentCost": capex_eur_kw * EUR_SEK * kw,
                # DEA fixed O&M (4%/2% of capex/yr, excl. stack) folded into the charge rate:
                # effective annual = capex x (CRF + fixed-O&M frac), horizon pro-rated.
                "FixedChargeRate": (ELECTROLYSER_CRF + fom_f) * CAPEX_HORIZON_FACTOR,
                "BinaryInvestment": pd.NA, "InvestmentLo": 0.0, "InvestmentUp": 1.0,
                "NoFCRD": "No", "NoFCRN": "No",
                "EnduranceFCRD": FCR_ENDURANCE_MIN_D, "EnduranceFCRN": FCR_ENDURANCE_MIN_N,
                "CompressorNameplate": 0.0, "CompressorInvestCost": 0.0,
                # calibrated variable O&M (replaces the uncalibrated 18.2 SEK/kg seed leftover)
                "OMVariableCost": ELECTROLYSER_OM_VAR,
            }
            # Production ramp limit (opt-in): absolute rate (kW/h) = frac-of-capacity x module kW, so it
            # scales like the power vars in the model (factor1-invariant).
            if ELE_RAMP:
                _rr = round(ELE_RAMP_PCT[tech] * kw, 4)
                vals.update({"RampUp": _rr, "RampDown": _rr})
            for c, v in vals.items():
                if c in r.index:
                    r[c] = v
            modules[f"{tech}_{m:02d}"] = r
    fleet = pd.DataFrame(modules).T
    return pd.concat([fleet, rest])


def _edit_hyd_generation(df):
    # Bring the hydrogen units into the base year (they start in 2040 in the base
    # case, after EconomicBaseYear, so they are otherwise inactive and the
    # electricity-to-hydrogen set is empty).
    if "InitialPeriod" in df.columns:
        df["InitialPeriod"] = 2020

    # Ensure the FCR + compressor columns exist (default opt-out / zero) so every
    # unit, including the new electrolyser modules cloned below, carries them.
    for col, default in (("NoFCRD", "Yes"), ("NoFCRN", "Yes"),
                         ("EnduranceFCRD", 0.0), ("EnduranceFCRN", 0.0),
                         ("CompressorNameplate", 0.0), ("CompressorInvestCost", 0.0)):
        df[col] = default
    # Only candidate units carry an investment cost; clear it everywhere first.
    if "FixedInvestmentCost" in df.columns:
        df["FixedInvestmentCost"] = pd.NA

    # --- Tank + compressor (PEMEL_01) at Node3 ---
    df.loc[TANK_UNIT, "Node"] = NODE_STORE
    for col, val in TANK_DATA.items():
        if col in df.columns:
            df.loc[TANK_UNIT, col] = val
    if STATION_CASCADE:
        # Fixed station cascade: a non-candidate storage (no InvestCost -> always fully present) of
        # size STATION_CASCADE_KG. Belongs to the demand/station, so no capex enters the VPP objective
        # and no build-fraction floor is needed. The FCR-down endurance uses its full (fixed) headroom.
        df.loc[TANK_UNIT, "MaximumStorage"] = STATION_CASCADE_KG
        if "FixedInvestmentCost" in df.columns:
            df.loc[TANK_UNIT, "FixedInvestmentCost"] = pd.NA
    else:
        _set_candidate(df, TANK_UNIT, TANK_CAPEX, TANK_CRF + TANK_FOM)
        # Mandatory cascade storage: floor the tank build fraction at the physical buffer (opt-in). The
        # tank stays investable up to 1.0 but can no longer be built at zero -- a station must have it.
        if MANDATORY_STORAGE and "InvestmentLo" in df.columns:
            df.loc[TANK_UNIT, "InvestmentLo"] = MANDATORY_STORAGE_LO
    df.loc[TANK_UNIT, "CompressorNameplate"] = COMPRESSOR_NAMEPLATE
    df.loc[TANK_UNIT, "CompressorInvestCost"] = COMPRESSOR_CAPEX_ANNUAL * CAPEX_HORIZON_FACTOR

    # --- Electrolyser fleet: replace the template unit with technology modules ---
    df = _build_fleet(df)

    # --- Pressure-resolved standalone compressor (opt-in) -------------------------------
    # A Technology="Compressor" row that lifts H2 from the 30-bar bus (Node2) to the 500-bar
    # cascade (Node3). It SUPERSEDES the tank-welded compressor (zeroed here), so compression is
    # metered on the real device throughput and gates the electrolyser's FCR-down. Clone the tank
    # row for column structure, then clear the storage/production fields so it lands only in
    # model.hc. Its DischargeNode column is the only new column; blank for every other row.
    if PRESSURE_NODES:
        df["DischargeNode"] = df["DischargeNode"].fillna("") if "DischargeNode" in df.columns else ""
        # The tank now charges from already-compressed 500-bar H2, so its welded compressor is fully
        # superseded: zero its throughput, capex AND its charge-compression energy (no double count).
        df.loc[TANK_UNIT, "CompressorNameplate"] = 0.0
        df.loc[TANK_UNIT, "CompressorInvestCost"] = 0.0
        df.loc[TANK_UNIT, "MaxCompressorConsumption"] = 0.0
        comp = df.loc[TANK_UNIT].copy()
        for c, v in {
            "Node": NODE_ELY, "DischargeNode": NODE_STORE, "Retailer": ELE_RETAILER,
            "Technology": "Compressor", "StorageType": "",
            "MaximumCharge": COMPRESSOR_NAMEPLATE, "MinimumCharge": 0.0,
            "MaximumPower": 0.0, "MinimumPower": 0.0,
            "MaximumStorage": 0.0, "MinimumStorage": 0.0, "InitialStorage": 0.0,
            "ProductionFunction": 0.0, "Efficiency": 1.0,
            "MaxCompressorConsumption": COMPRESSOR_KWH_KG,
            "CompressorNameplate": 0.0, "CompressorInvestCost": 0.0,
            "StandByStatus": "No", "BinaryCommitment": pd.NA,
            "NoFCRD": "Yes", "NoFCRN": "Yes", "InitialPeriod": 2020, "FinalPeriod": 2050,
        }.items():
            if c in comp.index:
                comp[c] = v
        df.loc[COMPRESSOR_UNIT] = comp
        _set_candidate(df, COMPRESSOR_UNIT, 800_000.0 * EUR_SEK, 0.0802 + 0.04)
    return df


# Literature-grounded hour-of-day shapes (see notes/data_sources.md / .bib). These set
# only the TEMPORAL pattern; the daily volume is the per-sector `avg` in DEMAND_SECTORS.
# HRS: heavy-duty truck refuelling as a diesel-HDV traffic analogue -- morning ramp,
#   midday plateau, overnight trough (Liu et al., ORNL 2022); no measured HDV-H2 hourly
#   data exists, so this is an analogue (stated in the methods).
# Enhanced (default on) vs legacy demand shapes. The enhanced shapes make each sector's temporal
# pattern more realistic -- crucially bunkering becomes genuinely batchy -- which gives on-site
# storage a clear, hourly-visible job. ENHANCED_PROFILES=0 restores the legacy shapes for A/B.
ENHANCED_PROFILES = os.environ.get("ENHANCED_PROFILES", "1") == "1"

# HRS hour-of-day. Legacy: broad morning ramp + midday plateau. Enhanced: sharper heavy-duty FLEET
# peaks at shift start (~07:00) and shift end (~16:00), when fleets cluster to refuel -- a diesel-HDV
# traffic analogue (Liu et al., ORNL 2022); no measured HDV-H2 hourly data exists (stated in methods).
_HRS_HOD_LEGACY = np.array([
    0.20, 0.15, 0.12, 0.12, 0.20, 0.45,
    0.95, 1.45, 1.70, 1.65, 1.55, 1.50,
    1.55, 1.55, 1.45, 1.30, 1.15, 1.00,
    0.80, 0.60, 0.45, 0.35, 0.30, 0.25])
_HRS_HOD_ENHANCED = np.array([
    0.15, 0.12, 0.10, 0.10, 0.20, 0.60,   # 00-05 overnight trough
    1.45, 1.90, 1.55, 1.25, 1.20, 1.25,   # 06-11 sharp shift-start peak (07:00)
    1.35, 1.30, 1.20, 1.30, 1.65, 1.55,   # 12-17 afternoon shift-end peak (16:00)
    1.05, 0.70, 0.48, 0.34, 0.26, 0.20])  # 18-23 evening taper
_HRS_HOD = _HRS_HOD_ENHANCED if ENHANCED_PROFILES else _HRS_HOD_LEGACY
# Monthly factor: Swedish industrisemester signal (SCB Industrial Production Index),
# July/Aug freight trough. Applied to the truck HRS only.
_HRS_MONTH = np.array([0.946, 0.976, 1.131, 1.001, 1.033, 1.051,
                       0.789, 0.859, 1.060, 1.074, 1.065, 1.015])
# Ship / industrial seasonality (enhanced only). Ship: mild -- Nordic short-sea bunkering is fairly
# steady, slight deep-winter/high-summer softening (analogue: port-call seasonality). Industrial:
# summer maintenance-turnaround dip (SCB Industrial Production Index analogue).
_SHIP_MONTH = np.array([0.92, 0.94, 1.02, 1.05, 1.06, 1.04,
                        0.95, 0.96, 1.05, 1.06, 1.02, 0.93])
_IND_MONTH  = np.array([1.03, 1.02, 1.03, 1.01, 1.00, 0.98,
                        0.88, 0.90, 1.02, 1.04, 1.05, 1.04])
# Ship bunkering call schedule (enhanced): discrete vessel calls on set weekdays/hours so the pattern
# repeats across the horizon. ~2-3 calls/week, each a multi-hour block; the burst magnitude follows
# from normalizing to the sector mean. Analogue: short-sea / port bunkering call frequency (methods).
_SHIP_CALL_DAYS = {1, 3, 5}          # Tue, Thu, Sat
_SHIP_CALL_HOURS = (8, 11)           # 08:00-11:00 block (3 h)


def _sector_profile(shape, avg):
    """Per-load-level demand (kgH2/h) for a sector, normalized so its mean = avg, with a
    literature-grounded hour-of-day / weekday-weekend / seasonal pattern aligned to the
    modeled window (which starts at 2025-01-01 + HORIZON_START_HOUR, like the price and
    wind data, so demand and markets share one clock)."""
    idx = pd.date_range("2025-01-01T00:00:00", periods=N_LOADLEVELS, freq="h") \
        + pd.Timedelta(hours=HORIZON_START_HOUR)
    hod = idx.hour.to_numpy()
    dow = idx.dayofweek.to_numpy()   # 0=Mon .. 6=Sun
    mon = idx.month.to_numpy()
    if shape == "hrs":               # heavy-duty truck refuelling (diesel-HDV analogue)
        p = _HRS_HOD[hod].astype(float)
        p *= np.where(dow == 5, 0.60, np.where(dow == 6, 0.35, 1.0))   # Sat / Sun freight drop
        p *= _HRS_MONTH[mon - 1]                                       # summer/holiday dip
    elif shape == "ship":
        if ENHANCED_PROFILES:        # port bunkering: discrete vessel calls (batchy storage driver)
            h0, h1 = _SHIP_CALL_HOURS
            p = np.where(np.isin(dow, list(_SHIP_CALL_DAYS)) & (hod >= h0) & (hod < h1), 1.0, 0.0).astype(float)
            p *= np.where(dow == 5, 0.7, 1.0)                          # smaller weekend call
            p *= _SHIP_MONTH[mon - 1]                                  # mild seasonality
        else:                        # legacy: smooth daytime working-hours block
            p = np.where((hod >= 7) & (hod < 19), 1.0, 0.0).astype(float)
            p *= np.where(dow == 5, 0.7, np.where(dow == 6, 0.5, 1.0))
    else:                            # industrial feedstock
        if ENHANCED_PROFILES:        # light 2-shift weekday pattern (feedstock never fully stops)
            p = np.where((hod >= 6) & (hod < 22), 1.0, 0.55).astype(float)   # day shift vs night
            p *= np.where(dow >= 5, 0.75, 1.0)                               # weekend turndown
            p *= _IND_MONTH[mon - 1]                                         # summer maintenance dip
        else:                        # legacy: flat 24/7 baseload
            p = np.ones(N_LOADLEVELS)
    m = p.mean()
    return p / m * avg if m > 0 else np.full(N_LOADLEVELS, avg)


def _build_demands(df):
    """Replace the template demand with the price-responsive sector demand units."""
    if "Price" not in df.columns:
        df["Price"] = 0.0
    template = df.loc[DEMAND_TEMPLATE].copy()
    rest = df.drop(index=DEMAND_TEMPLATE)
    rows = {}
    for name, (avg, price_eur, shape) in DEMAND_SECTORS.items():
        r = template.copy()
        # Under PRESSURE_NODES each sector sits at its dispensing-pressure node; otherwise all at Node4.
        sector_node = SECTOR_NODE.get(name, NODE_DEM) if PRESSURE_NODES else NODE_DEM
        for c, v in (("Node", sector_node), ("Retailer", H2_RETAILER),
                     ("InitialPeriod", 2020), ("FinalPeriod", 2050),
                     ("Flexible", "Yes"), ("Price", price_eur * EUR_SEK * H2_PRICE_SCALE)):
            if c in r.index:
                r[c] = v
        # In shift mode the target sector is load-shiftable: a window of SHIFT_STEPS load
        # levels over which the total is preserved, and a per-hour deviation cap. Other
        # sectors / other modes leave these blank (model defaults them to 0 = off).
        if DEMAND_MODE == "shift" and name == SHIFT_SECTOR:
            r["ShiftedSteps"] = SHIFT_STEPS
            r["FlexPercent"] = SHIFT_FLEX_PERCENT
        # Delivery-compression intensity (opt-in): 0 keeps the column inert for existing cases.
        # Under PRESSURE_NODES the standalone compressor asset does the 30->500 compression and
        # dispensing is passive let-down, so the demand-node compression term is off.
        r["MaxCompressorConsumption"] = 0.0 if PRESSURE_NODES else (
            DELIVERY_COMP_KWH_KG.get(name, 0.0) if DELIVERY_COMPRESSION else 0.0)
        rows[name] = r
    return pd.concat([pd.DataFrame(rows).T, rest])


def _edit_hyd_demand(df):
    # Replace the template demand with the multi-sector, price-responsive offtake
    # (flexible demands at Node4, each with its own price; profiles set in
    # VarMaxDemand). InitialPeriod into the base year so they are active.
    if "InitialPeriod" in df.columns:
        df["InitialPeriod"] = 2020
    return _build_demands(df)


def _demand_dict(df):
    # Replace the template demand with the sector demand names in the demand list.
    col = df.columns[0]
    df = df[df[col] != DEMAND_TEMPLATE]
    return pd.concat([pd.DataFrame({col: list(DEMAND_SECTORS)}), df], ignore_index=True)


def _edit_hyd_retail(df):
    # Import/export backstop: an expensive merchant-H2 buy, no forced sell (the price-responsive
    # demands are the offtake). Sits at Node4 by default; under PRESSURE_NODES the port exchange is
    # a 30-bar connection, so it moves to the 30-bar bus (Node2).
    df["Node"] = NODE_ELY if PRESSURE_NODES else NODE_DEM
    if "Buy" in df.columns:
        df["Buy"] = "Yes"
    if "Sell" in df.columns:
        df["Sell"] = "No"
    df["InitialPeriod"] = 2020
    # Opt-in port import raises the buy allowance to the port cap (the buy PRICE is set in
    # _edit_var_energy_cost). Default off keeps the merchant-backstop cap. Trailer/ship mode caps
    # the hourly rate at the daily-trailer-volume equivalent instead.
    _buy_cap = H2_PORT_HOURLY_CAP if (H2_IMPORT_PORT and H2_PORT_TRAILER) else \
        (H2_IMPORT_PORT_CAP if H2_IMPORT_PORT else H2_IMPORT_CAP)
    df["MaximumEnergyBuy"] = _buy_cap
    for col in ("MaximumEnergySell", "MinimumEnergySell"):
        if col in df.columns:
            df[col] = 0.0
    # Opt-in export to the port: give the retailer a sell allowance (the sell PRICE is set in
    # _edit_var_energy_price). Default off leaves MaximumEnergySell = 0, so sell is disabled.
    if H2_EXPORT and "MaximumEnergySell" in df.columns:
        df["MaximumEnergySell"] = H2_PORT_HOURLY_CAP if H2_PORT_TRAILER else H2_EXPORT_CAP
        if "Sell" in df.columns:
            df["Sell"] = "Yes"
    return df


def _edit_var_energy_cost(df):
    # Electricity BUY price = real SE3 day-ahead spot (SEK/kWh); the model adds the
    # energy tax, transfer fee and VAT on top. Hydrogen BUY (import backstop), flat.
    if USE_REAL_DATA and ELE_RETAILER in df.columns:
        df[ELE_RETAILER] = _real_spot_sek_kwh()
    # Opt-in port import: flat port price instead of the expensive merchant backstop.
    if H2_IMPORT_PORT and H2_PORT_TRAILER:
        # Trailer/ship: port price inside the delivery window, merchant backstop (12 EUR/kg) outside it,
        # so imports are economically confined to the working-hours window.
        df[H2_RETAILER] = np.where(_port_window_mask(), H2_IMPORT_PORT_PRICE, H2_IMPORT_PRICE)
    else:
        df[H2_RETAILER] = H2_IMPORT_PORT_PRICE if H2_IMPORT_PORT else H2_IMPORT_PRICE
    return df


def _edit_var_energy_price(df):
    # Electricity SELL price = the spot (export earns the day-ahead price). The H2
    # retailer no longer sells (offtake revenue comes from the per-demand prices), so
    # its sell-price column is zeroed.
    if USE_REAL_DATA and ELE_RETAILER in df.columns:
        df[ELE_RETAILER] = _real_spot_sek_kwh()
    if H2_RETAILER in df.columns:
        # Port export price when enabled, else 0 (no sell). A flat port price.
        if H2_EXPORT and H2_PORT_TRAILER:
            # Trailer/ship: export earns the port price only inside the delivery window; 0 outside it,
            # so exports are economically confined to the working-hours window.
            df[H2_RETAILER] = np.where(_port_window_mask(), H2_EXPORT_PRICE, 0.0)
        else:
            df[H2_RETAILER] = H2_EXPORT_PRICE if H2_EXPORT else 0.0
    return df


def _edit_reserve_activation(df):
    # PREFERRED (REAL_KAPPA=1, default): per-hour activation DEGREES derived from measured
    # 2025 Nordic frequency (Fingrid dataset 177, 3-min; see build_kappa_year.py and
    # notes/data_sources.md). Real FCR-N duty is ~0.11 in EACH direction with both directions
    # active in 98% of hours -- the physically faithful hourly aggregation of a continuous
    # symmetric product. FCR-D comes out rare and shallow (3-min sampling under-resolves the
    # seconds-scale excursions; indicative, and energy-negligible). Falls through to the
    # symmetrised Home1 seed below if the file is absent or REAL_KAPPA=0.
    _real_kap = REAL_DATA / "fcr_activation_2025.csv"
    if USE_REAL_DATA and os.environ.get("REAL_KAPPA", "1") == "1" and _real_kap.exists():
        k = pd.read_csv(_real_kap)
        for col in ("FCRD_Up", "FCRD_Down", "FCRN_Up", "FCRN_Down"):
            if col in df.columns:
                df[col] = k[col].to_numpy()[HORIZON_START_HOUR:HORIZON_START_HOUR + N_LOADLEVELS]
        # Deterministic-model aggregation: even the measured record has UNEQUAL up/down
        # duties within each hour, and a perfect-foresight hourly model can cherry-pick
        # hours by the net direction -- an information rent no real FCR-N provider has
        # (verified: the raw real record re-opens a ~55 kSEK/week gap in the B1 test).
        # Apply the bids to the symmetric per-hour MEAN of the measured pair: the true
        # duty/churn profile is preserved hour-by-hour, the unforeseeable net drift is
        # removed (it belongs to the settlement layer, not to free physics).
        if os.environ.get("ACT_GROSS_SYM", "1") == "1":
            m = (pd.to_numeric(df["FCRN_Up"], errors="coerce").fillna(0.0)
                 + pd.to_numeric(df["FCRN_Down"], errors="coerce").fillna(0.0)) / 2.0
            df["FCRN_Up"] = m
            df["FCRN_Down"] = m
        return df
    # FALLBACK: FCR-N activation as a GROSS symmetric within-hour pair (ACT_GROSS_SYM=1, default).
    # The seeded record carries per-hour ONE-WAY FCR-N activation (up and down are disjoint
    # by hour) -- the signature of an hourly NET-energy record. Physically, FCR-N is a
    # continuous proportional response and the frequency crosses 50.00 Hz many times per
    # hour, so BOTH directions activate within essentially every hour and the energy mostly
    # cancels in the provider's state of charge (micro-cycling, priced by the throughput
    # degradation term). Feeding the one-way record into the hourly model turns FCR-N into a
    # schedulable free one-way energy service (~3 MSEK/yr artifact, see
    # notes/bug_fcrn_activation_channel_2026-07-04.md). The faithful hourly aggregation is
    # the symmetric gross pair: kappa_up = kappa_down = (up + down)/2, which preserves the
    # activation volume (duty) and removes the artificial net drift. The residual real net
    # drift settles via the reserve-delivery/settlement layer (RESERVE_DELIVERY). FCR-D is
    # left as recorded: disturbance activations are genuinely one-directional events and
    # their kappa is ~100x smaller (immaterial channel). ACT_GROSS_SYM=0 restores the raw
    # record for ablation.
    if os.environ.get("ACT_GROSS_SYM", "1") == "1" and "FCRN_Up" in df.columns and "FCRN_Down" in df.columns:
        m = (pd.to_numeric(df["FCRN_Up"], errors="coerce").fillna(0.0)
             + pd.to_numeric(df["FCRN_Down"], errors="coerce").fillna(0.0)) / 2.0
        df["FCRN_Up"] = m
        df["FCRN_Down"] = m
    return df


def _edit_reserve_price(df):
    # FCR capacity prices = real svk Mimer national clearing prices (SEK/kW/h).
    if USE_REAL_DATA:
        for prod, arr in _real_fcr_sek_kw_h().items():
            if prod in df.columns:
                df[prod] = arr
    return df


def _edit_var_fixed_availability(df):
    # Wind availability = real ERA5 single-turbine capacity factor (SE3 west coast),
    # derated for wind-farm WAKE LOSSES (turbines shadow each other). A flat ~10%
    # derate is a standard first-order proxy; a wake model (FLORIS/PyWake) would give
    # the layout-resolved loss. The wind unit is still WIND_SOURCE_UNIT here (renamed
    # to WIND_UNIT after the edit).
    if USE_REAL_DATA:
        cf = pd.read_csv(REAL_DATA / "wind_se3.csv")["cf"].to_numpy()[HORIZON_START_HOUR:HORIZON_START_HOUR + N_LOADLEVELS]
        cf = cf * (1.0 - WIND_WAKE_LOSS)
        for col in (WIND_SOURCE_UNIT, WIND_UNIT):
            if col in df.columns:
                df[col] = cf
        if WIND_N_PLANTS >= 2:
            df[WIND_UNIT_2] = cf   # second plant's own column (created here)
    # Fuel cell is fully available for FCR (dispatchable). Without this it defaults to 0
    # and the FCR availability bound (eEleFreq*BoundFuelCell) caps every fuel-cell bid at 0.
    df[FUELCELL_UNIT] = 1.0
    return df


def _edit_var_max_generation(df):
    # The renewable's absolute hourly output cap lives in VarMaxGeneration: the model sets
    # pMaxPower = VarMaxGeneration and only falls back to the scalar MaximumPower where
    # VarMaxGeneration is exactly 0. The base case leaves a home-scale wind profile here
    # (~3.6 kW peak), which silently throttles the 5 MW farm regardless of MaximumPower or
    # the CF written to VarFixedAvailability. Overwrite the wind column with the real
    # absolute profile = MaximumPower x ERA5 CF x (1 - wake). Floor at a tiny positive value
    # because an exact 0.0 reads as "no profile" and the model would substitute the full
    # nameplate -- inverting calm hours into full output.
    if USE_REAL_DATA:
        cf = pd.read_csv(REAL_DATA / "wind_se3.csv")["cf"].to_numpy()[HORIZON_START_HOUR:HORIZON_START_HOUR + N_LOADLEVELS]
        prof = np.maximum(WIND_MAX_POWER * cf * (1.0 - WIND_WAKE_LOSS), 1e-3)
        for col in (WIND_SOURCE_UNIT, WIND_UNIT):
            if col in df.columns:
                df[col] = prof
        if WIND_N_PLANTS >= 2:
            df[WIND_UNIT_2] = prof   # second plant's own column (created here)
    # Fuel cell is dispatchable: an exact-0 VarMaxGeneration makes the model fall back to
    # its scalar MaximumPower (full nameplate available every hour), which is what we want.
    df[FUELCELL_UNIT] = 0.0
    return df


def _edit_var_min_generation(df):
    # Wind is fully curtailable: clear any must-run minimum. The base case leaves a
    # home-scale VarMinGeneration profile on the renamed unit; left in place it can exceed
    # the (calm-hour) VarMaxGeneration set above, making the unit's output lower bound
    # exceed its upper bound -> a presolve-infeasible model.
    for col in (WIND_SOURCE_UNIT, WIND_UNIT):
        if col in df.columns:
            df[col] = 0.0
    df[FUELCELL_UNIT] = 0.0          # fuel cell fully curtailable (no must-run floor)
    return df


def _set_demand_profiles(df, kind):
    """Sector demand profiles: VarMaxDemand (the profile) / VarMinDemand (the floor).
    VarMax is always the shaped profile; only VarMin changes, and only for the target
    sector under firm. Shift mode also keeps the shaped profile (it is the baseline the
    model redistributes via the shift constraints):
      elastic -> max = shaped profile,  min = 0
      firm    -> max = shaped profile,  min = shaped profile (must-serve every hour)
      shift   -> max = shaped profile,  min = 0 (timing moved by the shift, total preserved)."""
    if DEMAND_TEMPLATE in df.columns:
        df = df.drop(columns=[DEMAND_TEMPLATE])
    for name, (avg, price_eur, shape) in DEMAND_SECTORS.items():
        profile = _sector_profile(shape, avg)
        target = name == SHIFT_SECTOR
        if kind == "max":
            df[name] = profile
        else:  # min
            df[name] = profile if (DEMAND_MODE == "firm" and target) else 0.0
    return df


def _edit_duration(df):
    # Activate the full modeled horizon: give every kept load level a 1 h duration
    # (the base case only sets the first 24). With HORIZON_HOURS = 168 this models a
    # full week so storage can arbitrage the day-to-day price variation.
    df["Duration"] = 1
    # N2T hoglasttid mask (weekdays 06-22, Jan-Mar/Nov-Dec, excl. winter helgdagar),
    # from the real 2025 calendar of the modeled window. Drives the hogbelastningsavgift
    # peak and the time-of-use transfer fee. Rows are in chronological load-level order.
    start = pd.Timestamp("2025-01-01") + pd.Timedelta(hours=HORIZON_START_HOUR)
    idx = pd.date_range(start, periods=len(df), freq="h")
    hol = pd.to_datetime(sorted(N2T_HIGHLOAD_HOLIDAYS)).normalize()
    mask = ((idx.weekday < 5) & (idx.hour >= 6) & (idx.hour < 22)
            & idx.month.isin(N2T_HIGHLOAD_MONTHS) & (~idx.normalize().isin(hol)))
    df["HighLoad"] = mask.astype(int)
    return df


def _fleet_dict(df):
    # Replace the template electrolyser with the fleet module names in the hydrogen-
    # generator list (the dict drives the generator set, so it must list every module).
    names = [f"{t}_{m:02d}" for t, (n, *_) in ELECTROLYSER_TECHS.items()
             for m in range(1, n + 1)]
    # Register the standalone compressor unit under PRESSURE_NODES (the dict drives the generator
    # set, so a data-only row would be silently ignored).
    if PRESSURE_NODES:
        names.append(COMPRESSOR_UNIT)
    col = df.columns[0]
    df = df[df[col] != ELECTROLYSER_TEMPLATE]
    return pd.concat([pd.DataFrame({col: names}), df], ignore_index=True)


def _battery_dict(df):
    # Replace the template battery with the duration-candidate names in the electricity-
    # generator list (the dict drives the generator set, so it must list every candidate).
    col = df.columns[0]
    df = df[df[col] != BESS_UNIT]
    return pd.concat([pd.DataFrame({col: BESS_UNITS}), df], ignore_index=True)


def _add_nodes_dict(df):
    # Append the new nodes (Node3, Node4) to the node list.
    extra = [n for n in NEW_NODES if n not in set(df["Node"])]
    return pd.concat([df, pd.DataFrame({"Node": extra})], ignore_index=True)


def _add_nodes_zone(df):
    # Map every node to the single zone (one zone -> one FCR market). The base case
    # only maps Node1, so this also pulls Node2 into the zone.
    nodes = ([NODE_PCC] if PCC_SPLIT else []) + [NODE_GRID, NODE_ELY, NODE_STORE, NODE_DEM]
    return pd.DataFrame({"Node": nodes, "Zone": [ZONE] * len(nodes)})


def _add_node_location(df):
    # Give the new nodes a location. Geography is not used by the optimisation,
    # only for plotting, so the base coordinates are reused.
    base = df.iloc[0]
    for nd in NEW_NODES:
        df.loc[nd] = base
    return df


def _network_rows(template, pairs, kind, oneway=False):
    # Build a network from a base template row: one active line per node pair. oneway caps the
    # BACKWARD capacity (TTCBck) at ~0 so flow only runs InitialNode->FinalNode. Used for the
    # pressure let-down pipes: H2 falls in pressure without work (500->350, 500->30), but going
    # back UP needs the compressor, so a reverse pipe flow would bypass the compressor gate.
    # TTCBck must be a tiny POSITIVE value, not 0 -- the model resets TTCBck=0 to TTC (symmetric).
    rows = []
    for i, (a, b) in enumerate(pairs, start=1):
        r = template.copy()
        r.index = pd.MultiIndex.from_tuples([(a, b, f"{kind}{i}")])
        for col, val in (("InitialPeriod", 2020), ("FinalPeriod", 2050),
                         ("TTC", LINE_TTC), ("TTCBck", 1e-6 if oneway else LINE_TTC),
                         ("SecurityFactor", LINE_SEC)):
            if col in r.columns:
                r[col] = val
        rows.append(r)
    return pd.concat(rows)


def _build_ele_network(df):
    # Electricity lines: Node1->Node2 (electrolyser), Node2->Node3 (compressor).
    return _network_rows(df.iloc[[0]], ELE_LINES, "c")


def _build_h2_network(df):
    # Hydrogen pipelines. Flat layout: Node2->Node3 (to storage), Node3->Node4 (to offtake),
    # bidirectional. Pressure-resolved: the only pipes are the 500->350 and 500->30 LET-DOWNS,
    # which must be one-way so H2 cannot climb pressure by pipe and bypass the compressor.
    return _network_rows(df.iloc[[0]], H2_LINES, "p", oneway=PRESSURE_NODES)


def _tile_ll(df, base_ll, new_ll):
    """Tile a load-level-indexed df (period, scenario, loadlevel) to len(new_ll) rows
    by repeating the base profile, renaming the load levels to new_ll. Used to build a
    horizon longer than the base case's load levels; the real monthly profiles are
    overlaid afterwards so only the base case's filler columns are actually repeated."""
    out = []
    for (p, sc), g in df.groupby(level=[0, 1], sort=False):
        g = g.droplevel([0, 1]).reindex(base_ll)
        t = g.iloc[[i % len(base_ll) for i in range(len(new_ll))]].copy()
        t.index = pd.MultiIndex.from_tuples([(p, sc, ll) for ll in new_ll])
        out.append(t)
    return pd.concat(out)


def _disable_unit(df, unit):
    """Force a candidate's build to ~0 (see DISABLE_UP), and zero any absolute storage
    floor so a near-empty storage unit stays feasible. The model holds a unit's initial
    inventory at InitialStorage regardless of the built capacity, so a disabled battery
    or tank with InitialStorage > 0 would be infeasible (inventory bound ~0 < start)."""
    if unit not in df.index:
        return
    if "InvestmentUp" in df.columns:
        df.loc[unit, "InvestmentUp"] = DISABLE_UP
    if "InvestmentLo" in df.columns:
        df.loc[unit, "InvestmentLo"] = 0.0
    for c in ("InitialStorage", "MinimumStorage"):
        if c in df.columns:
            df.loc[unit, c] = 0.0


def _set_reserve(df, unit, reserve):
    """Set a unit's FCR bid flags for the reserve level (NoFCR* = 'Yes' means opt-out)."""
    if unit not in df.index:
        return
    no_d, no_n = {"both": ("No", "No"), "none": ("Yes", "Yes"),
                  "fcrn": ("Yes", "No"), "fcrd": ("No", "Yes")}[reserve]
    if "NoFCRD" in df.columns:
        df.loc[unit, "NoFCRD"] = no_d
    if "NoFCRN" in df.columns:
        df.loc[unit, "NoFCRN"] = no_n


def _apply_variant(out_dir):
    """Patch the just-built case CSVs for the active experiment-matrix VARIANT.

    Edits the generation and option files in place: forces disabled candidates to
    zero build, sets the FCR bid flags for the reserve level, turns degradation off,
    and enables part-load PWL efficiency. A no-op for the A3 baseline (empty spec).
    """
    disable = set(_VSPEC.get("disable", []))
    reserve = _VSPEC.get("reserve", "both")
    degradation = _VSPEC.get("degradation", True)
    pwl = _VSPEC.get("pwl", True)   # PWL part-load is the baseline; S2 turns it off
    battery_rt = _VSPEC.get("battery_rt")
    fuelcell = _VSPEC.get("fuelcell", True)   # baseline candidate; off only where a variant disables it

    egen = out_dir / f"oM_Data_ElectricityGeneration_{CASE}.csv"
    hgen = out_dir / f"oM_Data_HydrogenGeneration_{CASE}.csv"
    opt = out_dir / f"oM_Data_Option_{CASE}.csv"

    # Electricity generation: the battery (only electricity FCR bidder + a candidate).
    e = pd.read_csv(egen, index_col=0)
    for u in BESS_UNITS:
        if u in disable:
            _disable_unit(e, u)
        _set_reserve(e, u, reserve)
    # Fuel cell: a baseline candidate, offered in every case so the model decides whether to
    # build it; disabled only where a variant turns it off (the battery-only A1). When live it
    # bids FCR per the reserve level.
    if not fuelcell:
        _disable_unit(e, FUELCELL_UNIT)
    _set_reserve(e, FUELCELL_UNIT, reserve)
    # Battery degradation (M3): the daily depth-of-discharge segments (existing) PLUS an
    # incremental sub-daily throughput cycle cost (DegradationCost, per kWh discharged) that
    # captures the FCR micro-cycling the daily DoD envelope misses. Both off under S1.
    if "DegradationCost" not in e.columns:
        e["DegradationCost"] = 0.0
    e["DegradationCost"] = pd.to_numeric(e["DegradationCost"], errors="coerce").fillna(0.0)
    for u in BESS_UNITS:
        if degradation:
            e.loc[u, "DegradationCost"] = BESS_THROUGHPUT_DEGRADATION_COST
        else:
            for c in ("DoDS1", "DoDS2", "DoDS3", "DegradationCost"):
                if c in e.columns:
                    e.loc[u, c] = 0.0
        if battery_rt == "low":
            for c in ("Efficiency_charge", "Efficiency_discharge"):
                if c in e.columns:
                    e.loc[u, c] = pd.to_numeric(e.loc[u, c], errors="coerce") * BATTERY_RT_LOW_FACTOR
    e.to_csv(egen)

    # Hydrogen generation: the electrolyser fleet (FCR bidders + candidates) and tank.
    h = pd.read_csv(hgen, index_col=0)
    for u in disable:
        if u in h.index:
            _disable_unit(h, u)
    # Electrolyser degradation (M2): throughput stack wear (DegradationCost) + a high-load
    # surcharge on the 2nd block (DegradationCost2ndBlock) + a within-on load-ramp cycling
    # cost (RampDegradationCost) that prices the continuous FCR-N modulation prior models
    # leave free -- this paper's degradation contribution. All zeroed under S1.
    for c in ("DegradationCost2ndBlock", "RampDegradationCost", "ByproductCredit"):
        if c not in h.columns:
            h[c] = 0.0
    # S5: the electrolyser can be held to a different reserve level than the battery
    # (e.g. FCR-N only, if it cannot meet the 7.5 s FCR-D activation window).
    ele_reserve = _VSPEC.get("ele_reserve", reserve)
    for u in ELECTROLYSER_UNITS:
        _set_reserve(h, u, ele_reserve)
        if u not in h.index:
            continue
        # Byproduct (O2 + waste heat) credit per kgH2 -- independent of the degradation switch.
        h.loc[u, "ByproductCredit"] = BYPRODUCT_CREDIT
        if degradation:
            _t = "AEL" if "AEL" in u else "PEM"   # per-technology DEA stack basis
            h.loc[u, "DegradationCost"]         = ELY_DEGRADATION_COST[_t]      * DEG_SCALE
            # cycling surcharge (2nd-block + ramp) additionally scaled by CYCLING_SCALE (=0 isolates it)
            h.loc[u, "DegradationCost2ndBlock"] = ELY_DEGRADATION_2NDBLOCK[_t]  * DEG_SCALE * CYCLING_SCALE
            h.loc[u, "RampDegradationCost"]     = ELY_RAMP_DEGRADATION_COST[_t] * DEG_SCALE * CYCLING_SCALE
        else:
            for c in ("DegradationCost", "DegradationCost2ndBlock", "RampDegradationCost"):
                if c in h.columns:
                    h.loc[u, c] = 0.0
    h.to_csv(hgen)

    # Option: part-load PWL electrolyser efficiency (model reads pOptIndBinElectrolyserPWL).
    # PWL is the baseline (on); S2 turns it off for the constant-eta sensitivity.
    o = pd.read_csv(opt)
    o["IndBinElectrolyserPWL"] = 1 if pwl else 0
    # Option: symmetry-breaking across the identical electrolyser modules (AEL_01/AEL_02,
    # PEM_01/PEM_02). LP-preserving build-order constraints that remove the permutation
    # degeneracy stalling the barrier; on by default (no effect on the optimum). Set SYMBREAK=0
    # to turn it off for an ablation (e.g. to confirm the objective is unchanged).
    o["IndBinSymmetryBreaking"] = int(os.environ.get("SYMBREAK", "1"))
    o.to_csv(opt, index=False)


# Money columns by data stem (row-keyed files). FixedChargeRate, Moms, ratios, investment bounds,
# physical quantities (nameplate, power) and the tariff-period index are deliberately EXCLUDED.
# MUST MIRROR the model's own money set in oM_InputData.py (_money_cols / _money_allcols): the model
# divides exactly these columns by MoneyBase, and _apply_currency divides exactly these by EUR_SEK.
# If the two drift apart a money column stays in SEK under H2VPP_CURRENCY=EUR and the objective is no
# longer a uniform rescale (caught 2026-07-07: ByproductCredit was missing here but is money in the model).
_MONEY_COLS = {
    "Parameter": ["ENSCost", "HNSCost", "CO2Cost", "EleConnInvestCost"],
    "ElectricityGeneration": ["FuelCost", "OMVariableCost", "LinearTerm", "ConstantTerm",
        "StartUpCost", "ShutDownCost", "FixedInvestmentCost", "FixedRetirementCost",
        "PPAPrice", "DegradationCost", "DoDS1", "DoDS2", "DoDS3"],
    "HydrogenGeneration": ["FuelCost", "OMVariableCost", "LinearTerm", "ConstantTerm",
        "StartUpCost", "ShutDownCost", "FixedInvestmentCost", "FixedRetirementCost",
        "DegradationCost", "CompressorInvestCost", "DegradationCost2ndBlock", "RampDegradationCost",
        "ByproductCredit"],
    "ElectricityRetail": ["Fastavgift", "Overforingsavgift", "PowerTariff", "EnergyTax", "Paslag",
        "HighLoadTariff", "OverforingHigh"],
    "HydrogenRetail": ["paslag", "netavgift"],
    "HydrogenDemand": ["Price"],
}
# Files whose every value column (after the period/scenario/loadlevel index) is money.
_MONEY_ALLCOLS = {"VarEnergyPrice", "VarEnergyCost", "OperatingReservePrice"}


def _scale_money(stem, df):
    """Divide the money-valued columns of one data table by MONEY_BASE (no-op when MONEY_BASE=1)."""
    if MONEY_BASE == 1.0:
        return df
    if stem in _MONEY_ALLCOLS:
        for c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce") / MONEY_BASE
    elif stem in _MONEY_COLS:
        for c in _MONEY_COLS[stem]:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce") / MONEY_BASE
    return df


def _apply_currency(out_dir):
    """Convert every money column of the WRITTEN case from SEK to the model currency (no-op in SEK
    mode). A final pass over the written CSVs -- runs after _apply_variant (which rewrites the
    generation files with SEK-valued degradation/byproduct constants), so nothing it touches is
    left in SEK and nothing is converted twice. Uses the same column map as _scale_money, so it
    covers capex, O&M, fuel, startup, degradation, tariffs, taxes, the ENS/HNS penalties (Parameter
    file) and the spot / FCR / H2 price series. MoneyBase is NOT in the map, so the conditioning
    knob is untouched. Blank-header index columns (period/scenario/loadlevel) read back as
    'Unnamed: N'; they are left numerically intact and their empty header is restored on write."""
    if CURRENCY_DIV == 1.0:
        return

    def _rewrite(f, money_cols):
        df = pd.read_csv(f)
        unnamed = [c for c in df.columns if str(c).startswith("Unnamed:")]
        # money_cols is None -> every value column is money (the all-money time series)
        cols = ([c for c in df.columns if c not in unnamed] if money_cols is None
                else [c for c in money_cols if c in df.columns])
        for c in cols:
            df[c] = pd.to_numeric(df[c], errors="coerce") / CURRENCY_DIV
        df.rename(columns={c: "" for c in unnamed}).to_csv(f, index=False)

    for stem, money_cols in _MONEY_COLS.items():
        f = out_dir / f"oM_Data_{stem}_{CASE}.csv"
        if f.exists():
            _rewrite(f, money_cols)
    for stem in _MONEY_ALLCOLS:
        f = out_dir / f"oM_Data_{stem}_{CASE}.csv"
        if f.exists():
            _rewrite(f, None)


def _drop_stray_units(df):
    """Remove the stray base-case units from a data table. They appear as COLUMNS in the
    time-indexed Var* tables and as the ROW index in the per-unit generation table, so drop
    both. Time-indexed tables (period, scenario, load level) have a multi-level index that
    never holds a unit name, so only their columns are touched."""
    drop_cols = [c for c in df.columns if c in DROP_UNITS]
    if drop_cols:
        df = df.drop(columns=drop_cols)
    if df.index.nlevels == 1:
        df = df[~df.index.astype(str).isin(DROP_UNITS)]
    return df


def build():
    src = CSVSource(str(BASE_DIR / BASE_CASE))
    if OUT_DIR.is_dir():
        shutil.rmtree(OUT_DIR)
    OUT_DIR.mkdir(parents=True)

    base_ll = list(src.read_dict("LoadLevel").iloc[:, 0])
    all_loadlevels = set(base_ll)
    TILE = N_LOADLEVELS > len(base_ll)            # generate levels beyond the base
    new_ll = ([f"t{i:04d}" for i in range(1, N_LOADLEVELS + 1)] if TILE
              else base_ll[:N_LOADLEVELS])
    keep = set(base_ll[:N_LOADLEVELS])

    for stem in sorted(src.list_dict_stems()):
        df = src.read_dict(stem)
        if stem == "LoadLevel":
            df = pd.DataFrame({df.columns[0]: new_ll})
        if stem == "Node":
            df = _add_nodes_dict(df)
        if stem == "NodeToZone":
            df = _add_nodes_zone(df)
        if stem == "HydrogenGeneration":
            df = _fleet_dict(df)
        if stem == "ElectricityGeneration":
            # Replace the single battery template with the duration candidates (BESS_2h/4h/8h).
            df = _battery_dict(df)
            # Register the fuel cell in the generator list that seeds model.eg (its
            # ProductionFunction>0 in the data table then places it in model.h2e).
            col = df.columns[0]
            if FUELCELL_UNIT not in set(df[col].astype(str)):
                df = pd.concat([df, pd.DataFrame({col: [FUELCELL_UNIT]})], ignore_index=True)
            # Register the second wind plant (Wind_02) so it seeds model.eg as a candidate; Wind_01
            # arrives via the Solar_01 -> Wind_01 rename below, so only add the extra plant here.
            if WIND_N_PLANTS >= 2 and WIND_UNIT_2 not in set(df[col].astype(str)):
                df = pd.concat([df, pd.DataFrame({col: [WIND_UNIT_2]})], ignore_index=True)
        if stem == "HydrogenDemand":
            df = _demand_dict(df)
        if stem == "Technology" and "Technology" in df.columns:
            for _t in ("Wind", *ELECTROLYSER_TECHS):
                if _t not in set(df["Technology"]):
                    df = pd.concat(
                        [df, pd.DataFrame({"Technology": [_t]})],
                        ignore_index=True,
                    )
        # Rename the wind unit wherever a dict lists it (e.g. the generator list
        # that seeds the generator set).
        df = df.replace(WIND_SOURCE_UNIT, WIND_UNIT)
        # Drop the stray units wherever a dict lists them (the generator list seeds model.eg).
        df = df[~df.iloc[:, 0].astype(str).isin(DROP_UNITS)]
        df.to_csv(OUT_DIR / f"oM_Dict_{stem}_{CASE}.csv", index=False)

    for stem in sorted(src.list_data_stems()):
        df = src.read_data(stem)
        # Trim only genuine time-indexed files (period, scenario, loadlevel) to the
        # modeled horizon. Other 3-level files -- the electricity and hydrogen
        # networks -- are indexed by (node, node, circuit); the loadlevel filter must
        # NOT touch them, or it deletes every line and islands the nodes (which
        # silently starves the electrolyser of grid power).
        if df.index.nlevels == 3 and set(df.index.get_level_values(2)) <= all_loadlevels:
            df = _tile_ll(df, base_ll, new_ll) if TILE else df[df.index.get_level_values(2).isin(keep)]
        df = df.copy()

        if stem == "Option":
            df = _edit_option(df)
        elif stem == "Parameter":
            df = _edit_parameter(df)
        elif stem == "OperatingReserveRequire":
            df = _edit_reserve_require(df)
        elif stem == "OperatingReserveActivation":
            df = _edit_reserve_activation(df)
        elif stem == "ElectricityGeneration":
            df = _edit_ele_generation(df)
        elif stem == "ElectricityRetail":
            df = _edit_ele_retail(df)
        elif stem == "HydrogenGeneration":
            df = _edit_hyd_generation(df)
        elif stem == "HydrogenDemand":
            df = _edit_hyd_demand(df)
        elif stem == "HydrogenRetail":
            df = _edit_hyd_retail(df)
        elif stem == "VarEnergyCost":
            df = _edit_var_energy_cost(df)
        elif stem == "VarEnergyPrice":
            df = _edit_var_energy_price(df)
        elif stem == "OperatingReservePrice":
            df = _edit_reserve_price(df)
        elif stem == "VarFixedAvailability":
            df = _edit_var_fixed_availability(df)
        elif stem == "VarMaxGeneration":
            df = _edit_var_max_generation(df)
        elif stem == "VarMinGeneration":
            df = _edit_var_min_generation(df)
        elif stem == "ElectricityNetwork":
            df = _build_ele_network(df)
        elif stem == "HydrogenNetwork":
            df = _build_h2_network(df)
        elif stem == "NodeLocation":
            df = _add_node_location(df)
        elif stem == "Duration":
            df = _edit_duration(df)
        elif stem == "VarMaxDemand":
            df = _set_demand_profiles(df, "max")
        elif stem == "VarMinDemand":
            df = _set_demand_profiles(df, "min")

        # Rename the wind column anywhere a generator-keyed data file carries it.
        if WIND_SOURCE_UNIT in df.columns:
            df = df.rename(columns={WIND_SOURCE_UNIT: WIND_UNIT})

        # Drop the stray base-case units (EV battery + rooftop PV) from every table.
        df = _drop_stray_units(df)

        # Money scaling moved INTO the model (Step 1 of the per-unit refactor): build_case writes RAW
        # currency + a 'MoneyBase' Parameter column, and oM_InputData divides every money input by it.
        # (Old in-builder _scale_money retained above for reference / MONEY_BASE=1 cases but no longer called.)
        # df = _scale_money(stem, df)

        df.to_csv(OUT_DIR / f"oM_Data_{stem}_{CASE}.csv")

    _apply_variant(OUT_DIR)
    _apply_currency(OUT_DIR)
    _check_conditioning(OUT_DIR)
    tag = f" [VARIANT={VARIANT}]" if VARIANT else ""
    cur = "" if CURRENCY == "SEK" else f" [currency={CURRENCY}]"
    try:                                   # OUT_DIR may sit outside the repo (e.g. OUT_BASE on D:)
        _rel = OUT_DIR.relative_to(REPO)
    except ValueError:
        _rel = OUT_DIR
    print(f"built {CASE} -> {_rel}{tag}{cur} (mode={DEMAND_MODE})")


def _check_conditioning(out_dir):
    """Refuse an ill-conditioned money basis before it silently corrupts the solve.

    The largest annualized capex coefficient the model will see is raw FixedInvestmentCost x
    FixedChargeRate / MONEY_BASE. Above COND_MAX_CAPEX_COEF the coefficient range gets wide enough
    that the solver returns a silently suboptimal optimum (see the note by MONEY_BASE). Hard error,
    overridable with COND_ALLOW_ILL=1.
    """
    worst = 0.0
    for stem in ("ElectricityGeneration", "HydrogenGeneration"):
        f = out_dir / f"oM_Data_{stem}_{CASE}.csv"
        if not f.exists():
            continue
        df = pd.read_csv(f)
        if "FixedInvestmentCost" not in df.columns or "FixedChargeRate" not in df.columns:
            continue
        fic = pd.to_numeric(df["FixedInvestmentCost"], errors="coerce")
        fcr = pd.to_numeric(df["FixedChargeRate"], errors="coerce")
        coef = (fic * fcr / MONEY_BASE).abs().max()
        if coef == coef:  # skip NaN
            worst = max(worst, float(coef))
    if worst > COND_MAX_CAPEX_COEF and os.environ.get("COND_ALLOW_ILL", "0") != "1":
        need = MONEY_BASE * worst / COND_MAX_CAPEX_COEF
        raise SystemExit(
            f"ill-conditioned money basis: largest annualized capex coefficient is {worst:.3g} at "
            f"MONEY_BASE={MONEY_BASE:g} (limit {COND_MAX_CAPEX_COEF:.3g}). This range makes the "
            f"solver return a silently suboptimal optimum (~17% off at MONEY_BASE=1, on both HiGHS "
            f"and Gurobi). Raise MONEY_BASE to at least {need:.0f} for this case, or set "
            f"COND_ALLOW_ILL=1 to run the raw basis anyway."
        )


if __name__ == "__main__":
    build()
