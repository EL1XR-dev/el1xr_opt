# el1xr_opt model audit (2026-06-09)

Ground-truth audit of the formulation against the documentation, done before
rewriting the concept-page equations. Code is authoritative; line numbers are at the
time of writing.

Two parts:

- **Part A — documentation fixes** (doc says X, code does Y): the work list for the
  equation/concept rewrite.
- **Part B — code findings** (likely bugs / modelling concerns): these change model
  results if fixed, so they are listed for a decision, not silently changed. The
  equation rewrite documents *actual* behaviour and flags these inline as known issues
  until they are resolved in code.

---

## Part A — documentation fixes (drive the rewrite)

### concepts/parameters.rst (most divergent)
The dominant error is dropping the mandatory `Ele`/`Hyd` sector prefix; most unprefixed
keys do not exist. Specific wrong names (doc -> actual):

- `pParDiscountRate` -> input `pParAnnualDiscountRate`; derived `pDiscountFactor`.
- `pHydrogenCost` / `pHydrogenPrice` -> none; hydrogen buy/sell use shared
  `pVarEnergyCost` / `pVarEnergyPrice`.
- `pEleRetelcertifikat` -> none (closest: `pEleRetIncentive`).
- `pEleRetpaslag` / `pEleRetmoms` -> `pEleRetPaslag` / `pEleRetMoms` (casing).
- `pEleRetnetavgift` -> `pEleRetOverforingsavgift` (per-kWh) + `pEleRetFastavgift` (fixed).
- `pEleRetTariff` -> `pEleRetPowerTariff`.
- `pEleMaxMarketBuy` / `pEleMaxMarketSell` -> `pEleRetMaximumEnergyBuy` / `...Sell`.
- `pMaxEleProduction` / `pMinEleProduction` (+ Hyd) -> `pEleMaxPower` / `pEleMinPower`.
- `pGenConstantVarCost` / `pGenLinearVarCost` / `pGenStartUpCost` / `pGenShutDownCost`
  -> sector-prefixed `pEleGen...` / `pHydGen...`.
- `pGenRampUpCost` / `pGenRampDownCost` -> none (no ramp *cost*; only ramp *rates*
  `pEleGenRampUp` / `pEleGenRampDown`).
- `pGenMinUpTime` / `pGenMinDownTime` -> `pEleGenUpTime` / `pEleGenDownTime`.
- storage `pMaxStorage` / `pMaxCharge` / ... -> `pEleMaxStorage` / `pEleMaxCharge` / ...
- `pEleStorageCycle` / `pEleStorageOutflowCycle` -> `pEleCycleTimeStep` /
  `pEleOutflowsTimeStep`.
- `pEleConsCompress` -> `pEleGenMaxCompressorConsumption`.
- `pEleDemShiftedSteps` **does exist** (built from the `ShiftedSteps` demand column; used by
  `eEleDemandShiftBalance` / `eEleDemandShifted`) -- the original audit note was wrong.
  Flexibility uses `pEleDemFlexible` + `pEleDemFlexPercent` + `pEleDemShiftedSteps`.
- `pEleMinStorageStart` / `pEleMinStorageEnd` (EV) -> none.
- reserve activation `..._Up_SR` / `_Down_SR` / `_Up_TR` / `_Down_TR` -> the products are
  `_FCRD_Up`, `_FCRD_Down`, `_FCRN_Up`, `_FCRN_Down` (no SR/TR).
- Structural: parameters are dict keys in `model.Par` built in `oM_InputData.py`, **not**
  Pyomo `Param` components, and **not** defined in `oM_ModelFormulation.py`. Drop the
  "Pyomo Component" framing.

### concepts/variables.rst
- `vTotalEleNetUseCost` -> `vTotalEleNetUseVarCost`; `vTotalEleCapTariffCost` ->
  `vTotalEleNetUseFixCost`.
- `vTotalEleVATCost` -> `vTotalEleEnergyTaxCost` (it is the Swedish energy tax, not VAT;
  VAT is `pEleRetMoms`, a multiplier).
- `vEleDemPeak` -> `vEleDemPeakGlobal` (psmer, Peaks) + `vEleDemPeakDay` (psder); same
  for hydrogen.
- `vElePeakHourInd` -> `vElePeakGlobalInd` + `vElePeakMonthInd` + `vElePeakDayInd`; same
  for hydrogen. The three tiers are tied to `pEleRetTariffType` (Hourly vs Daily).
- `vEleStorOperat` is documented but **commented out** in code; only `vHydStorOperat`
  exists. Remove or restore (see Part B).
- Missing entirely: `vEleImport` / `vEleExport` / `vHydImport` / `vHydExport`,
  `vEleInventoryMinDay/MaxDay/DoDDay/DoDS1-3Day`, the FCR-D/FCR-N revenue sub-vars.
- Domains: with every `IndBin*` flag defaulting to 0, the commitment/storage/peak/
  network-commit "binaries" are **`UnitInterval` by default** -- the shipped default is
  an **LP**, not a MILP. The doc presents them as `{0,1}` unconditionally.
- `vEleDemFlex` is only created when some demand is flexible (conditional).

### concepts/sets.rst
- Names that appear are correct, but many working sets are undocumented: `hgt`,
  `els/elc/ele`, `hpa/hpc/hpe`, `endrf/hndrf`, `et/ht/rt`, `ehs/eh/he/esc`, all the
  `n2*/z2*/t2*/r2*` maps, and the whole time-set family (`moy, doy, psm, psd, psdn, ...`).
- `hgr` is a deliberately empty placeholder (no hydrogen RES column).
- The single letters `e` (storage) and `r` (retailer) in the doc match no code id;
  storage is `egs/hgs/ehs`, retailers `er/hr`.

### concepts/objective-function.rst
- `eTotalTCost` is wrong: the doc shows only `sum_p discount * sum_s (C - R)` and
  **omits `vTotalICost` (investment) and `heat_cost`**, both of which are in the actual
  objective.
- "discount rate" -> it is `pDiscountFactor[p]`, a per-period discount **factor**.
- `vTotalEleEnergyTaxCost` is shown as "VAT" -- it is the energy tax (see above).
- `factor1` usage is uneven and should be stated per term: peak, net-use-var, net-use-
  fix, energy tax, FCR, generation-invest cost all use `factor1`; the **day-ahead market
  buy/sell and the hydrogen PPA do not** (see Part B).
- Net grid charge splits into `vTotalEleNetUseVarCost` (per-kWh överföringsavgift) and
  `vTotalEleNetUseFixCost` (fixed fastavgift, `= fastavgift * factor1 * months * (1+moms)`).
- Investment cost: `vTotalICost = period_weight * factor1 * sum InvestCost * build`,
  `period_weight = sum_p pDiscountFactor[p]`.

### concepts/constraints.rst
- **Peak equations are stale.** They are written on `vEleBuy` with no night/day
  adjustment; the code uses `vEleImport` adjusted by `_adjusted_import` (night/day buy
  factor + a no-demand addend, from `pEleRetPeakNight/DayBuyFactor` / `...Addend`). The
  note "a night discount is not currently applied" is now **false**.
- Peak is three-tier (Hourly: `eElePeakHourValue` / `...Ind_C1` / `...Ind_C2` /
  `eElePeakNumberMonths`; Daily: the daily/global family). `eEleMonthPeakOrder` is active
  but only mentioned in passing.
- `eEleInventoryDoDS3Upper`: doc says `<= pdodsc * pmaxstorage`; code bounds segment 3 by
  the daily DoD (`<= vEleInventoryDoDDay`).
- EV `eEleMinEnergyStartUp`: doc hard-codes `0.8 * pelemaxstorage`; code uses a data
  parameter `* factor1`.
- Reserve-bound constraints invented in the doc (`eEleFreqDisUpChargeBound`, ...) do not
  exist as named; the real ones are the combined `eEleFreqUp/DownCharge/DischargeBound`.
- Correctly documented as disabled (keep the notes): `eEleBuyComposition`,
  `eEleSellComposition`, `eIncompatibilityEleChargeOutflows`, and the older DoD S1/S2/S3
  block. Also commented out: `eEleMaxRampUp/DwOutflows`, `eEleMonthDayAtMostOnePeak`.
- Section numbering is broken (two "3"s).
- `eKirchhoff2ndLaw` carries a `doc=` string calling it "Kirchhoff 1st Law".

### concepts/heat-sector.rst
- `eHeatBalance` description is incomplete: it omits the **store-charge sink** and the
  **heat-to-power consumption** term (both on the demand side), mislabels heat-not-served
  as "minus" (it is a `+` supply term), and lists heat-pump output separately from
  `vHeatOutput` though heat pumps are a subset of `htg` (double-counting in words).

### concepts/community.rst
- Add the **>= 2-members-per-zone** condition: `eEleCommunityPool` is skipped for a zone
  with fewer than two members.

### concepts/features-and-modes.rst
- Drop "or SDP" from the `detect_problem_class` output list (it never returns SDP).
- Stop listing "green-hydrogen matching" as an `oM_Features` flag (it lives in
  `oM_GreenHydrogen.py`); the balance mode is seeded by `apply_flag_defaults`, not a
  `Feature`.
- Document the **horizon-coupling registry** (`register_horizon_constant` /
  `register_horizon_threshold` / `register_horizon_unsupported`, `seed_horizon_coupling`,
  `TEMPORAL_HANDLED_PS_COST/_REV`).

### user-guide/network-analysis.rst
- The IEEE-33 loss/voltage numbers (~202.7 kW, ~0.913 pu) are validated in the tests, not
  in `oM_ACOPF.py` / `oM_LinDist3Flow.py`. Verify against the test before quoting.

### user-guide/decomposition.rst
- Add the heat-store boundary coupling (`St`, the heat analogue of `Se`/`Sh`) and the
  heat operating cost in the recourse.
- Describe the registry-driven (constant / threshold / unsupported) mechanism and the
  transversality guard, not the old hard-coded peak/fixed-charge description.
- State the MVP scope limits: single `(period, scenario)`, hourly storage cycle = 1,
  Daily power tariff unsupported.

### concepts/future-developments.rst
- Mark as done (move out of the future list): heat thermal store in temporal Benders,
  registry-driven cost architecture. Grid-fee item is partially done (fixed fee, net-use,
  energy tax, power tariff all exist). Resolve the DoD note-vs-body redundancy.

---

## Part B — code findings (decide before/with the rewrite)

Severity: **H** = wrong cost in the objective; **M** = asymmetry / likely bug; **L** =
cosmetic / fragility.

1. **[H] ENS / HNS reliability cost is duration-weighted twice. FIXED 2026-06-09.**
   `eTotalEleRCost` (oM_ModelFormulation.py:189) multiplied by `pDuration`, then
   `vTotalEleRCost` was summed into `vTotalEleOCost` (eEleOpMaintCost:160), registered
   with kind `psn` and so multiplied by `pDuration` again (oM_Features.aggregate_terms).
   Its sibling O&M terms (G/E/C) have no internal duration, so unserved energy entered the
   objective as `pDuration^2 * ENSCost * vENS`. Same for `vTotalHydRCost`. Fix: dropped the
   internal `pDuration` from `eTotalEleRCost` / `eTotalHydRCost`, so the `psn` aggregation
   supplies the single duration like the siblings. Golden costs are unchanged because the
   shipped validation cases serve all load (ENS = HNS = 0 at the optimum); the fix only
   bites when some load is shed.

   ### factor1 -- investigated, NOT bugs (the audit agent over-called these)
   `factor1` (oM_InputData.py:97) is a kWh<->MWh **energy** unit knob, currently `1.0`,
   applied at **parameter-build** time and at the point of use for energy quantities:

   - The "intra-electricity inconsistency" is correct: `eEleInvestMaxInventory` carries
     `factor1` because inventory is **energy**; `eEleInvestMaxOutput` / `...Charge` do not
     because those cap **power**. The electricity inventory variable bound
     (oM_InputData.py:1189) carries `factor1` for the same reason, so the invest cap and
     the bound agree.
   - The electricity-vs-hydrogen storage-energy difference **was a real inconsistency,
     FIXED 2026-06-09.** `factor1` scales storage *energy* at the point of use (the
     inventory variable bound) and the initial inventory (`pHydInitialInventory =
     GenInitialStorage * factor1`, oM_InputData.py:611) -- the latter for **both**
     sectors. Electricity also scaled its inventory bounds (:1188-1189) and invest cap
     (oM_Investment.py:116); hydrogen scaled neither (:1237-1238, :126), so the hydrogen
     cap was in raw units while its initial state and its accumulated inventory (built
     from `factor1`-scaled charge/inflow powers) were in scaled units. Inert at
     `factor1 = 1`, wrong otherwise. Fixed by scaling the hydrogen inventory bounds and
     invest cap by `factor1`, mirroring electricity; golden-neutral. (Broader, lower
     priority and symmetric across sectors: the raw `pEle/HydMaxStorage` *parameter* is
     also compared against the scaled `InitialInventory` in some storage feasibility
     pre-checks -- a separate `factor1`-convention clean-up, not addressed here.)
   - Day-ahead market / PPA: the per-energy cost flows through parameters
     (`pVarEnergyCost`, `pEleGenLinearVarCost = pEleGenLinearTerm * factor1 * ...`,
     oM_InputData.py:199) that are scaled at build, so there is no missing constraint-level
     `factor1`. Confirm the retailer ratio/påslag scaling if `factor1` is ever set != 1.

2. **[M] Hydrogen storage charge/discharge roles were swapped. FIXED 2026-06-09.**
   Confirmed a genuine bug against the electricity formulation and the conf.py macro
   meanings (`vHydStorCharge` = charging binary, `vHydStorDischarge` = discharging
   binary, `pHydMaxCharge` = charge capacity, `pHydMaxPower` = output capacity). Four
   places were wrong: `eHydMaxESSOutput2ndBlock` gated output by the **charge** binary
   (now discharge); `eHydMaxESSCharge2ndBlock` gated charge by the **discharge** binary
   (now charge) -- combined with the mutual-exclusion `eHydStorageMode` these two forced
   the storage 2nd block to zero whenever it actually charged/discharged;
   `eHydChargingDecision` normalized charge by **pHydMaxPower** (now pHydMaxCharge) and
   `eHydDischargingDecision` normalized output by **pHydMaxCharge** (now pHydMaxPower).
   Fixed to mirror the electricity ESS exactly. Golden impact: the shipped validation
   cases have no active base-year hydrogen storage (`hgs` empty), so the headline
   goldens are unchanged; the fix corrects the H2 variant cases (H2Tank / Electrolyser,
   currently xfail).

3. **[M] `vTotalHydDCost` is registered (psd) with no defining constraint.** Every other
   registered term has an `e...Cost` constraint; this one relies on the variable being
   fixed to zero elsewhere. If ever left free it enters the objective unconstrained.

4. **[L] `vEleStorOperat` is dead** (commented out both branches) but documented; only the
   hydrogen side has a storage-operation variable.

5. **[L] Feature flags without backing variables.** `binary_gen_retirement`,
   `binary_net_investment`, `binary_h2net_investment` are in the `FEATURES` catalogue and
   retirement parameters exist, but `oM_Investment.py` only builds `vEleGenInvest` /
   `vHydGenInvest` -- no retirement or transmission-build variable. Flags advertise
   capability that is not implemented.

6. **[L] `eKirchhoff2ndLaw` `doc=` says "Kirchhoff 1st Law".** Cosmetic label.

7. **[L] Initial-condition asymmetry** between electricity (ramp first-step subtracts a
   `max(pEleSystemOutput - MinPower, 0)` term) and hydrogen (no analogue).

8. **[M] Heat inventory omitted the load-level duration. FIXED 2026-06-09.** The heat
   operating cost weights output by `pDuration` (after the bug-5 fix), but `eHeatInventory`
   (oM_HeatSector) updated `inv[n] = prev + eff*charge[n] - discharge[n]` with no
   `duration`, unlike the electricity/hydrogen inventories which sum `duration * (...)`.
   So on a representative load level (`duration != 1`) a heat charge/discharge moved the
   store by one hour's worth while its cost was counted for all the hours the level
   stands for -- the store state and its cost disagreed. Fixed: the inventory now weights
   the charge/discharge by `pDuration`, matching the other sectors and the cost. Note
   `eHeatBalance` correctly stays a duration-free **power** balance (like `eEleBalance`),
   so only the inventory needed the weight. The temporal-Benders heat boundary (`_rep_ht`)
   is weighted to match, and the monolith-vs-Benders heat-storage test still agrees.
   Golden-neutral (the validation cases have no heat sector; heat tests use hourly
   resolution); guarded by `test_heat_inventory_is_duration_weighted`. Still open: the
   heat-sector variables carry no unit doc-strings (undocumented, nothing mislabelled).

---

## Status / sequencing

- **Done (merged or in flight):** Part A concept-page rewrite; ENS/HNS double-count
  (item 1); hydrogen storage charge/discharge swap (item 2); hydrogen storage-energy
  `factor1` scaling (item 1 sub-point); electricity + hydrogen storage unit labels
  (`kW`/`kWh`, `kgH2/h`/`kgH2`); heat inventory duration weighting (item 8).
- **Flagged, not changed (modelling-judgement review):** items 3-7 -- notably
  `vTotalHydDCost` with no defining constraint (item 3); the rest are low severity.
- Re-run the strict docs build (`sphinx -W`) after any docstring change (the
  `.githooks/pre-push` hook does this).
