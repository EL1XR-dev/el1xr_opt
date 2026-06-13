# Dev plan: unit-convention cleanup (factor1/factor2/currency) + electrolyser accuracy

Status: design + grounding complete; Phase A scaffold in place (factor1 settable via the
`FACTOR1` module global in `oM_InputData`, default 1.0; builds, byte-unchanged). Branch:
`feature/factor1-consistency`.

Guiding decisions (agreed with the user):
- Single canonical currency (declared input: EUR | SEK | USD; demo = SEK), no FX in the core
  model. Currency is a data contract + reporting label, not a conversion.
- Eliminate `factor2` (the hidden 1e-3 commitment-cost bridge).
- `factor1` = ONE invariance-preserving numerical-conditioning scale (default 1), exposed as a
  future `dfParameter` input. A true unit conversion: the optimum is unchanged.
- The real accuracy lever for the electrolyser is **part-load efficiency**, not the start-up cost
  (discrete electrolyser start-up costs are non-standard in the literature).

## Phase A — unit-convention cleanup (byte-unchanged goldens; oracle = solve tier + invariance test)

A1. factor1 = invariance-preserving scale. Per-dimension classification:
- QUANTITIES (`* factor1`, keep): MaximumPower, MinimumPower, StandByPower, MaximumCharge,
  MinimumCharge, RampUp, RampDown, MaxOutflowsProd, MinOutflowsProd, MaxInflowsCons,
  MinInflowsCons, OutflowsRampUp, OutflowsRampDown; storage energy bounds (Min/MaxStorage,
  InitialInventory), network TTC/TTCBck, demand (VarMaxDemand), retail Max/Min Energy Buy/Sell,
  FCR volume (OperatingReserveRequire).
- PRICES (`/ factor1`, FLIP from `* factor1`): pVarEnergyCost/Price (energy), OperatingReservePrice
  (FCR), LinearVarCost (fuel), CO2EmissionCost, OMVariableCost; and the in-constraint rate terms
  in oM_ModelFormulation: Overforingsavgift (grid fee, eTotalEleNetUseVarCost), EnergyTax,
  Incentive (ISRev), the per-quantity peak tariff branch (eTotalElePeakCost with peaks).
- FIXED CHARGES (DROP factor1): fastavgift (eTotalEleNetUseFixCost), zero-peak flat tariff
  (eTotalElePeakCost, no-quantity branch).
- INVESTMENT lump sum (DROP factor1): eTotalICost (oM_Investment), and the mirrored investment
  terms in oM_Decomposition (~482, ~837) and oM_Features (~405, ~430). [The investment STORAGE
  CAPS that read `* factor1` are quantities -> keep.]
- DIMENSIONLESS RATIOS (DROP factor1; remove from idx_gen_factoring): ProductionFunction,
  MaxCompressorConsumption, CO2EmissionRate.
- THORNY: the blanket `pPar{indicator} = dfParameter[...] * factor1` (oM_InputData ~137) scales
  ALL parameter columns. Reclassify per column: prices (pParCO2Cost, pCostPeak/pPricePeak) -> /factor1
  or handle at use; counts/years (pParEconomicBaseYear, pParNumberPowerPeaks, pParTimeStep) -> unscaled.
  Inspect dfParameter columns and split.
- pEpsilon_cost (~965, `pCostPeak * factor1`): a tolerance; make consistent or leave (verify it
  doesn't shift the optimum).
- At factor1==1 every change is a no-op -> goldens byte-unchanged (immediate error oracle).
- NEW TEST `test_factor1_invariant`: solve a small case at FACTOR1=1 and FACTOR1=2, assert
  (a) total cost (eTotalSCost) invariant within tol, (b) extensive decisions scale by 2 / are
  identical after unscaling, (c) investment build fractions identical.

A2. (MOVED to Phase B — coupled to commitment-cost revaluation.)

A3. Currency. Add `Currency` to dfOption (string label; EUR|SEK|USD; default EUR, demo SEK).
Read as a plain label (NOT scaled). Replace the hardcoded `'SEK'` print (oM_ProblemSolving ~212)
and the stale `[MEUR]`/`[MEUR/GWh]`/`[EUR]` doc labels with the declared currency. Byte-unchanged
(cosmetic).

A4. Validate: full `pytest -m solve tests/` byte-unchanged + `test_factor1_invariant`.

## Phase B — electrolyser accuracy (re-baselines e2h cases; grounded by lit-review)

B0. Eliminate factor2 + re-enter commitment costs in the canonical currency (the deferred A2):
set factor2 -> 1 (remove `* model.factor2` at the 3 sites), and set ConstantTerm / StartUpCost /
ShutDownCost to realistic canonical-currency values (see B2). Re-baseline e2h goldens once.

B1. Piecewise-linear part-load efficiency (replace the constant ProductionFunction = 56.82
kWh/kgH2). FLAG-GATED: default = constant (legacy/non-e2h cases byte-unchanged); PWL when a flag
(e.g. dfOption IndPWLEfficiency, or a per-unit segmented-curve column) is set.
- Anchors (Brauns & Turek 2020, alkaline): best efficiency ~80-90% load; specific energy
  ~50-56 kWh/kgH2 at full load rising to ~62-73 kWh/kgH2 at 20% load; min stable load ~10-20%
  (already represented by MinimumCharge). PEM: worse at part load, min load ~5%.
- Formulation: SOS2 / lambda segment variables over the (electricity-in, H2-out) curve, or the
  no-load + marginal-segment form. Standard MILP PWL methodology: Carrion & Arroyo 2006.
- Data: 2-4 (load %, kWh/kgH2) points per electrolyser; alkaline vs PEM differ.

B2. Degradation cost (the real cost of flexible operation; Refaat et al. 2026):
- Per-throughput and/or per-cycle degradation cost; amortize stack-replacement over the
  cycle/calendar-aging-limited lifetime. Refaat Table 2: PEMEL ~5-20 uV/h + ~16 uV/cycle; cycle
  life vs DoD (Weibull-like). Use to derive a EUR/kWh-throughput or EUR/cycle term.
- Keep a SMALL documented warm-up cold-start (StartUpCost ~ warm-up energy + lost production,
  order ~tens of currency units; explicitly an estimate, not literature-sourced).

B3. Keep the three-state (on/standby/off) + min-load (physically sound for alkaline).

B4. Validate; deliberately re-baseline e2h goldens (Electrolyser, ElectrolyserFCR,
ElectrolyserStandby, H2Tank) with justification + the citations below.

## References (verify exact BibTeX before citing)
- Brauns, J.; Turek, T. "Alkaline Water Electrolysis Powered by Renewable Energy: A Review."
  Processes 2020, 8(2), 248. (part-load efficiency anchors; ~635 cites)
- Refaat, A. et al. (2026) degradation-based sizing/EMS of hydrogen-assisted hybrid microgrids
  (PEMEL/PEMFC degradation numerics: uV/h, cycle/calendar aging).
- Carrion, M.; Arroyo, J. M. "A Computationally Efficient Mixed-Integer Linear Formulation for
  the Thermal Unit Commitment Problem." IEEE Trans. Power Syst. 2006, 21(3), 1371-1378.
  (standard PWL / commitment MILP methodology to adapt).
- Production function 56.82 kWh/kgH2 sits at the full-load end of Brauns & Turek's 50-56 range.

## Sequencing & git
Phase A first (orthogonal, byte-unchanged), committed as its own unit. Then Phase B (re-baseline).
User commits/pushes; I prepare commits + commands. Telegram ping at milestones.

## Phase A status (factor1 consistency) — CONTINUOUS PART DONE & VERIFIED
Implemented the full per-dimension reclassification (quantities x factor1; per-quantity prices /
factor1 -- energy, FCR, O&M, CO2, fuel, grid fee, energy tax, incentive, Paslag, peak-quantity;
fixed charges + investment lump sum + dimensionless ratios unscaled). factor1 is now settable via
the FACTOR1 module global (default 1.0).
VERIFIED: factor1=1 is BYTE-UNCHANGED (21 solve goldens + 54 fast tests pass -> no regression).
factor1 INVARIANCE is EXACT for the continuous model: Home1 with the peak tariff disabled gives
identical total cost at factor1=1 and factor1=2 (ratio 1.00000). Guarded by test_factor1_invariant.
RESIDUAL (documented follow-up): the peak-demand power-tariff is a MILP (binary peak-hour
selection) whose discrete structure does not scale cleanly with factor1, so peak-tariff cases are
not exactly invariant. The _adjusted_import constant addend is now scaled by factor1 (a kW
constant). Making the peak-selection MILP scale-invariant is the remaining factor1 item.
STILL TODO: factor2 elimination + the PWL part-load-efficiency feature + degradation cost (Phase B,
not started); the peak-tariff MILP invariance.
