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

B0+B2 STATUS — DONE (branch feature/phase-b-factor2-degradation). factor2 fully removed
(oM_InputData: no model.factor2; ConstantVarCost = ConstantTerm x FuelCost, StartUp/ShutDown read
directly in the canonical currency = SEK). Realistic AEL_01 values: StartUpCost 30, ShutDownCost 5,
ConstantTerm 0 (no-load dropped -- the electrolyser's electricity is already costed via the energy
balance; removing it also takes AEL out of the hgt no-load set, so the shut-down objective term was
extended to e2h-outside-hgt to keep billing it). NEW per-kWh stack-degradation cost
(pHydGenDegradationCost, 0.07 SEK/kWh on AEL's productive electricity; new optional generation
column, default 0; a per-quantity price so /factor1). Grounding: cold-start 30 SEK = engineering
estimate (warm-up energy + lost production + per-cycle wear; not a standardised literature value);
degradation 0.07 SEK/kWh = stack replacement (~45% x ~EUR1000/kW x 52.5 kW) amortised over ~70000 h
throughput (IEA/IRENA cost ranges; Refaat 2026 degradation-as-cost framing). Re-baselined goldens:
H2Tank 6776.72 -> 6779.40, Electrolyser 6776.72 -> 6779.39 (delta +2.68 SEK = degradation 1.59 +
fractional startup 1.08; validated by decomposition). Main + battery goldens unchanged (AEL inactive
there). Tests: test_electrolyser_canonical_costs_and_degradation (factor2 gone, canonical values,
degradation wired, e2h shut-down billed).

CURRENCY LABEL -- DONE (branch feature/currency-label). pParCurrency (default 'SEK') read from an
optional dfParameter 'Currency' column (string, like the DemandType precedent; dfParameter is not
int-cast, unlike dfOption). LABEL ONLY -- single canonical unit, so no numbers change. Used in the
objective print (oM_ProblemSolving) and the cost-result CSV column header (oM_OutputData, write-time
rename only; 'SEK' stays the internal value-column key so helpers / links / plots are untouched).
Test: test_currency_label (default SEK + settable to EUR via the column). Plot axis titles and the
per-kWh price labels still read 'SEK/kWh' (secondary cosmetic, left as-is).

B1. Piecewise-linear part-load efficiency (replace the constant ProductionFunction = 56.82
kWh/kgH2). FLAG-GATED: default = constant (legacy/non-e2h cases byte-unchanged); PWL when a flag
(e.g. dfOption IndPWLEfficiency, or a per-unit segmented-curve column) is set.

B1 STATUS — DONE (branch feature/phase-b-pwl-efficiency).
- Flag: dfOption IndBinElectrolyserPWL (catalogue feature electrolyser_pwl_efficiency in
  oM_Features; default 0 -> constant ProductionFunction, all existing goldens byte-unchanged).
- Curve: built in oM_InputData.create_variables (model.pwl_curve / model.hpwl). 4 breakpoints per
  flagged e2h unit spanning [MinCharge, MaxCharge] (productive electricity x, hydrogen y). Specific
  energy = full-load ProductionFunction x a canonical alkaline multiplier m(f) (Brauns & Turek
  shape, anchors f=[0.10,0.20,0.50,0.85,1.00] -> m=[1.35,1.25,1.08,0.97,1.00]); at full load m=1 so
  the PWL reproduces the legacy linear conversion exactly. No new data files (derived from existing
  params); B2/later can swap in per-unit measured curves.
- Formulation (oM_ModelFormulation): SOS2 convex combination. appsi/HiGHS has NO native SOS2
  (verified: "Highs interface does not support SOS constraints"), so SOS2 is encoded with segment
  binaries (adjacency). Rows: ePWLConvexity (sum weights == commitment), ePWLSegmentSum (one active
  segment == commitment), ePWLAdjacency (weight_k <= adjacent segments), ePWLPower (productive
  electricity = sum weight_k x_k), ePWLHydrogen (H2 = sum weight_k y_k). eAllEnergy2Hyd skips PWL
  units. Off/standby (commitment 0) -> all weights 0 -> no power, no H2. Segment domain follows the
  commitment (Binary, or relaxed under pOptIndBinGenOperat==0 = convex-hull relaxation).
- Test: test_electrolyser_pwl_efficiency (patches ElectrolyserStandby duckdb Option to flag on;
  asserts PWL active, linear skipped, curve reproduces PF at full load + varies, SOS2 holds in the
  solution). Default-off byte-unchanged confirmed (full solve + fast tiers pass).
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

## Phase A status (factor1 consistency) — DONE & VERIFIED (full invariance across all case types)
Implemented the full per-dimension reclassification (quantities x factor1; per-quantity prices /
factor1 -- energy, FCR, O&M, CO2, fuel, grid fee, energy tax, incentive, Paslag, peak-quantity;
fixed charges + investment lump sum + dimensionless ratios unscaled). factor1 is now settable via
the FACTOR1 module global (default 1.0).
VERIFIED: factor1=1 is BYTE-UNCHANGED (full solve suite + fast tests pass -> no regression).
factor1 INVARIANCE is now EXACT across ALL case types: the continuous model, the peak-demand tariff
MILP, the day-ahead market (buy/sell with per-step caps), FCR-D and FCR-N provision with its storage
SoC-endurance backing, the electricity PPA, the electrolyser, and the investment/sizing layer. Every
main and sizing case gives ratio 1.00000 at factor1=1 vs 2. Phase A is complete.

PEAK-TARIFF MILP — RESOLVED (was a stale "residual"). Re-measuring on the merged code shows the
peak tariff IS scale-invariant: Home1 and Grid1 with the peak tariff ENABLED give identical total
cost at factor1=1 and factor1=2 (Grid1 bit-for-bit, reldiff 0.0; peak cost component invariant in
every case). The earlier 0.856 non-invariance was an intermediate broken state (before the
energy-price double-scaling fix and the _adjusted_import addend fix), not a property of the
peak-selection MILP -- the selected peak hours are unchanged under a uniform rescaling and
tariff/factor1 x peak-quantity*factor1 is invariant. test_factor1_invariant now runs Home1 with the
peak tariff ON (no longer disabled).

MAXBUY/MAXSELL — FIXED (audit C38, this branch). The per-step retail caps pEleRetMaxBuy/MaxSell
(constraints eEleRetMaxBuy/eEleRetMaxSell) are per-step power quantities (kW/step) but were read
unscaled (not in idx_retail_factoring) -- a sell pinned at the cap earned half the revenue at twice
the unit scale. Now scaled by factor1 in oM_InputData (a zero "no cap" stays zero). This makes the
day-ahead market revenue (vTotalEleMrkDARev) exactly invariant (was ratio 0.5). factor1=1 is x1, so
goldens are byte-unchanged.

FCR-D DOWNWARD STORAGE PROVISION — RESOLVED (audit C38). The FCR-provision sizing cases were not
invariant because the DOWNWARD FCR-D bid from storage was sub-proportional (~x1.86). Two unscaled
terms, both found via a feasibility-transfer test (scale the factor1=1 optimum -- quantities x2,
money x1, binaries unchanged -- and check which factor1=2 constraint it violates):
 1. pEleMaxStorage / pHydMaxStorage (storage ENERGY capacity, kWh) is NOT in idx_gen_factoring, so
    it is applied x factor1 only at SOME use sites (the inventory variable bound, the investment
    layer) and was MISSING the x factor1 at the FCR SoC-endurance constraints
    (eEleStorageEnduranceDown/DownEnd lines 750/768, eEleFreqDownEnduranceConv/ConvEnd lines
    867/883), which compare raw MaxStorage against the scaled inventory. At factor1=2 that made the
    down-charge endurance artificially tight and throttled the downward bid. Fixed: multiply the
    MaxStorage term by model.factor1 at those four use sites (matching the existing scale-at-use
    pattern at the inventory bound and the investment layer).
 2. The electricity PPA settlement (eEleMarketPPACost, oM_GreenHydrogen) multiplied pEleGenPPAPrice
    (a per-quantity price, EUR/kWh) by the output (a quantity) WITHOUT 1/factor1, so the PPA cost
    scaled x2 instead of staying invariant. Fixed: pEleGenPPAPrice / model.factor1 (like the
    day-ahead energy price). The old code even flagged this with a "REVIEW (units)" comment.
After both fixes EVERY sizing case is exactly invariant (ratio 1.00000): HomeBatt, HomeBattNoTariff,
HomeBattNoFCR, HomeBattFCRDonly, HomeBattFCRNonly, Electrolyser, H2Tank. Guarded by
test_sizing_factor1_invariant (HomeBattFCRDonly + Electrolyser). factor1=1 is x1 / 1/1, so goldens
are byte-unchanged.

Phase B is now complete: factor2 elimination, the PWL part-load-efficiency feature, and the
degradation cost are all done (see the B0+B2 and B1 status notes above).
