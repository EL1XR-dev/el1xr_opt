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

## Part C — formulation review round 2 (2026-06-09)

A four-way parallel review of the whole formulation (objective components + FCR;
storage/commitment/three-state; hydrogen/green/heat/investment; input-data bounds,
fixing and the cost registry), after the electrolyser-FCR + three-state merge.
Findings marked **[verified]** were re-checked line by line in the code by the main
session; the rest were verified by the reviewing agent only. Severity as in Part B.

### HIGH — wrong objective, wrong physics, or latent crash

C1. **[H][verified] Variable O&M cost is double-counted, both sectors.**
`pEleGenLinearVarCost = LinearTerm*factor1*FuelCost + OMVariableCost*factor1`
(oM_InputData.py:199) already contains O&M, yet `eTotalEleGCost`
(oM_ModelFormulation.py:165-169) charges both `LinearVarCost*output` **and**
`OMVariableCost*output`; same in `eTotalHydGCost` (:204-208). Live in shipped cases:
the electrolysers carry `OMVariableCost = 18.2`, so hydrogen output pays 36.4 instead
of 18.2 per kg. Note Part B item "hydrogen O&M sign" added the explicit O&M term on
the hydrogen side — the sign fix was right but it landed on top of the O&M already
inside `LinearVarCost`; the clean fix is to drop O&M from one of the two places in
both sectors. Secondary (latent at factor1=1): `OMVariableCost` is in
`idx_gen_factoring` so it is factor1-scaled twice.

C2. **[H][verified] `eHydBalance` references the undefined set `model.n2g`.**
oM_ModelFormulation.py:437 filters the fuel-cell (h2e) hydrogen consumption with
`(nd,h2e) in model.n2g`; only `n2eg` / `n2hg` exist. Latent because no shipped case
has an active h2e unit; the first case with a fuel cell raises `AttributeError` (or,
with the name defined-but-empty, silently drops the fuel-cell hydrogen draw from the
node balance).

C3. **[H][verified] Electrolyser FCR-D down headroom is not gated by the unit
state.** `eEleFreqDownChargeHeadroomConv` (oM_ModelFormulation.py:680-685) bounds
down-provision by `pHydMaxCharge - vEleTotalCharge2ndBlock`. The 2nd block is zero
when the unit is OFF or in STANDBY, so an off/standby electrolyser can sell its full
nameplate as FCR-D down although it cannot absorb the activation from cold. When
committed, the headroom overstates the true room by `MinCharge` (consumption is
`MinCharge + 2ndBlock`, room to nameplate is `MaxCharge - MinCharge - 2ndBlock`).
FCR-N is protected by the up-side symmetry; FCR-D down is not. Also, a node with
FCR-flagged electrolysers but no hydrogen store **skips** `eEleFreqDownEnduranceConv`
(:710-711) instead of forcing the down bid to zero — the constraint that motivated
the node-level design ends up absent exactly where it should bind hardest.

C4. **[H][verified] STANDBY is reachable from OFF, so the cold-start cost can be
dodged.** The only standby constraints are `uc + sb <= 1` (:916) and the cold-start
bound `su >= uc[t] - uc[t-1] - sb[t-1]` (:931). Nothing requires being warm to enter
standby: from OFF the solver can pay one period of `StandByPower` (0.52 kW in the
demo data) and then start "warm" for free, dodging the 2612.5 start-up cost.
Physically a cold stack cannot be held warm without having started. Missing
transition constraint: `sb[t] <= uc[t-1] + sb[t-1]` plus an initial-standby state
(`pHydInitialStandBy`); related, `pHydInitialUC[e2h]` is pinned to 0 by the
initial-UC skip, so an electrolyser running before the horizon is billed a cold start
at t1.

C5. **[H][verified] Thermal-generator FCR-N bids have no physical backing.**
`vEleFreqContReserveNorUpGen` / `NorDownGen` appear only in their declaration, the
no-FCRN fixing, and the two relations `NorBid <= NorUpGen` / `NorBid <= NorDownGen`
(oM_ModelFormulation.py:488,495) — both right-hand sides are otherwise free
variables, so the relations are vacuous and an egt unit can bid the whole FCR-N
requirement with no headroom reserved. Worse, the non-storage branches of
`eEleTotalOutput` (:1213-1217) reference `vEleFreqContReserveNorUpDis`/`NorDownDis`,
which are declared **on storage only** (`psnegs`): the first case with an active
committed thermal unit raises `KeyError` at build. The intended variables are
`NorUpGen`/`NorDownGen`; fixing the indexing would also wire the missing FCR-N
activation for generators.

C6. **[H][verified] The retail settlement misses the electrolyser's committed
minimum load and standby draw.** `eEleRetNodeBalance` (oM_ModelFormulation.py:309-311)
subtracts only `vEleTotalCharge2ndBlock[e2h]`, while the unit's real consumption is
`MinCharge*uc + 2ndBlock + StandByPower*sb` (:1257-1259) and the physical balance
`eEleBalance` uses the full `vEleTotalCharge`. Thermal generation in the same retail
balance *does* include its committed minimum, so this is an asymmetry, not a
convention: the min-load and standby electricity never has to be bought
(`vEleBuy`), so the day-ahead cost undercounts exactly the consumption block the
three-state feature introduces — standby looks cheaper than it is.

C7. **[H] `vHydImport` / `vHydExport` are an unpriced, unbounded hydrogen
source/sink whenever no active hydrogen retailer prices them.** `vHydImport`
(NonNegativeReals, no upper bound) enters `eHydBalance` with `+`; it is priced only
through `eHydBuyComposition`, which requires an active retailer (`pHydRetMaxBuy > 0`)
— none exists in any shipped case — and it is fixed to zero only at non-reference
nodes in network mode (oM_InputData.py:1619-1628). In single-node mode nothing is
fixed anywhere: free hydrogen. Latent today because shipped hydrogen demand is
empty/period-gated; it will silently absorb any future H2 case. (The electricity side
is closed by `eEleRetNodeBalance`; hydrogen has no retail node balance — same root as
C2's neighbourhood and the `pHydRetMaxBuy` KeyError fragility below.)

C8. **[H][verified] Stale loop variable in the pre-horizon commitment fixing.**
oM_InputData.py:1672-1678 loops `for idx in model.psnegt:` but tests
`model.n.ord(n)`, where `n` leaks from an earlier loop that only runs when
`pOptIndBinSingleNode == 0`. In single-node mode the first unit with
`UpTimeZero/DownTimeZero > 0` raises `NameError`; otherwise `n` is stuck at the last
load level, so the min-up/down carry-over is fixed for all levels or none. Should be
`model.n.ord(idx[-2])` (the index's own level).

C9. **[H] Initial-UC override marks never-on units as initially committed.**
oM_InputData.py:837-840/862-865 set `pInitialUC = 1` whenever
`UpTime - UpTimeZero > 0`, i.e. also when `UpTimeZero == 0` (the unit was never on),
overriding the merit-order pre-commitment above it. The reference openTEPES logic has
no such override. Produces a spurious first-step shut-down or masks a start-up.
Should test `UpTimeZero > 0` (resp. `DownTimeZero > 0`). **— DONE (Part C item 5):**
both carry-over conditions now require `UpTimeZero > 0` (resp. `DownTimeZero > 0`)
before they fire, on both carriers (`pEleInitialUC` lines and the identical
`pHydInitialUC` block). Latent in shipped cases (no shipped unit has a positive
min-up/down requirement with a zero pre-horizon counter), so the goldens are
unchanged; guarded in `tests/test_formulation_fixes.py`
(`test_initial_uc_carryover_guarded_by_uptime_zero`).

### MED — asymmetries and conditional bugs

C10. **e2h FCR activation never changes consumption or hydrogen output.** The egs
branch of `eEleTotalCharge` (:1251) adjusts realised charge by the four
`pOperatingReserveActivation_*` terms; the e2h branch (:1257-1259) has none, so an
activated electrolyser bid delivers no energy and makes no extra hydrogen — while
`eEleFreqDownEnduranceConv` reserves storage headroom precisely for that hydrogen.
Revenue with no modelled energy consequence biases the FCR business case upward.

C11. **The e2h start-up cost is charged only if the unit happens to be in `hgt`.**
The cost term sums over `hgt = {ConstantVarCost > 0}` where
`ConstantVarCost = ConstantTerm * factor2 * FuelCost` (oM_InputData.py:200,326); the
cold-start constraints are gated on `pHydGenStartUpCost > 0` alone
(oM_ModelFormulation.py:927,940). An electrolyser with `FuelCost = 0` (natural for a
purely electric unit) gets the constraints but never pays — the demo only works
because AEL_01 has the dummy `FuelCost = 1`. The billing should not ride on the
fuel-cost product.

C12. **A fixed-consumption electrolyser (`MinCharge == MaxCharge`) silently loses
the whole charge decomposition.** `pHydMaxCharge2ndBlock = MaxCharge - MinCharge = 0`
skips `eEleTotalCharge`'s e2h branch (:1255) and both `eE2HMax/MinCharge2ndBlock`;
the 2nd-block fixing loop runs over `ehs = egs|hgs`, which excludes e2h
(oM_InputData.py:362,1478-1490). `vEleTotalCharge[e2h]` is then free in
`[0, MaxCharge]` with no commitment link, and `eAllEnergy2Hyd` still converts it.
**— DONE (Part C item 5, branch `fix/storage-electrolyser-coupling`):** `eEleTotalCharge`
gets a fixed-consumption e2h branch (`elif pHydMaxCharge`) that defines the charge as
`MinCharge * commitment + StandByPower * standby` -- committed draws MinCharge, standby
draws the standby power, off draws zero -- so the consumption is no longer free. The
now-unused 2nd-block charge of such a unit is pinned to zero in the fixing block. Latent
in shipped cases (every shipped electrolyser has a real 2nd block, MinCharge < MaxCharge),
goldens byte-unchanged; guarded in `tests/test_formulation_fixes.py`.

C13. **Electrolyser ramps and min-up/down times are now enforced nowhere.** The
pure-load fix removed the (output-side) hydrogen-generator ramps and min-times for
e2h, but no charge-side replacement exists: `eEleMaxRampUp/DwCharge` covers `egs`
only and `eHydMaxRampUp/DwCharge` covers `hgs` only. The shipped AEL `RampUp/Down =
120` is silently ignored; consumption can swing nameplate in one step and (with C4)
nothing deters cycling.

C14. **The retail balance ignores network flows.** `eEleRetNodeBalance` counts
incident lines in its build guard but includes no flow/import/export term, so in any
multi-node case the retailer must cover the local imbalance as if the network
delivered nothing (the commented-out `eEleBuyComposition` suggests the buy-import
link was never finished). Correct only for single-node cases.
**— DONE (decision taken: finish the buy<->import coupling).** The model carries two parallel
balances: the PHYSICAL nodal balance `eEleBalance` (KCL with `vEleNetFlow` and grid
`vEleImport`/`vEleExport`; grid fees/taxes/incentives are charged on `vEleImport`/`vEleExport`),
and the COMMERCIAL per-retailer balance `eEleRetNodeBalance` (the retailer's assigned
generation/demand/charge closed by `vEleBuy`/`vEleSell`; the day-ahead energy cost is charged on
`vEleBuy`). The two were never tied together -- the energy-cost base (`vEleBuy`) and the
grid-fee base (`vEleImport`) could in principle diverge. The fix finishes the old
`eEleBuyComposition` stub as two constraints at the electricity reference node:
`eEleImportBuyLink` (`vEleImport == sum_er vEleBuy`) and `eEleExportSellLink`
(`vEleExport == sum_er vEleSell`). All external trade crosses the reference node (import/export
are fixed to zero elsewhere in network mode), so the grid import equals the total retail buy and
the grid export equals the total retail sell -- one or more retailers. For a single retailer that
owns the whole portfolio (every shipped case) cost minimisation already drives `vEleBuy` to the
net grid draw, so the coupling is non-binding and **all goldens are byte-unchanged** (the solve
is also faster, the extra equalities tighten the LP). Verified on the multi-node Grid1 (retailer
at the reference node, assets on other nodes over lines): `import == buy` and `export == sell`
exactly. Guarded by `test_retail_buy_couples_to_grid_import`. **Note:** this couples retail trade
to the grid at the *reference node*. A retailer sitting at a non-reference node (no shipped case)
would still need per-node settlement -- the full nodal multi-retailer redesign -- which remains
future work.

C15. **Duration weighting is inconsistent for several money terms.** (a) The
volumetric grid fee (`eTotalEleNetUseVarCost`, :79), energy tax (:146) and incentive
revenue (:155) are plain sums over kW imports registered as `'ps'` — no `pDuration`
anywhere — so with `pParTimeStep > 1` they undercount by the time-step factor
relative to the `'psn'` energy terms. (b) Conversely the start-up/shut-down costs sit
inside `'psn'` terms and get multiplied by `pDuration`: a start at a k-hour level
costs k times the start-up cost. Both are exact only at 1-hour resolution.
**— (a) DONE (Part C item 5, branch `fix/duration-factor1-money-terms`):** each of the
three volumetric terms now weights its inner sum over n by `pDuration[p,sc,n]`, so the
per-kWh charge counts energy like the `'psn'` market terms. Latent at 1-hour resolution
(`pDuration = 1`), so the goldens are byte-unchanged; guarded in
`tests/test_formulation_fixes.py`. **(b) DONE (Part C item 5, branch
`fix/c15b-startup-event-cost`):** the per-event start-up / shut-down cost is moved out of
the `'psn'`-aggregated `vTotalEleGCost` / `vTotalHydGCost` into new `'ps'` terms
`eTotalEleSUCost` / `eTotalHydSUCost` that sum over n without `pDuration` (dividing by
`pDuration` would be unsafe — it can be 0 on a `psn` index when `pParTimeStep > 1`). The
no-load `ConstantVarCost` stays in `GCost` (a EUR/h cost, correctly duration-weighted).
The new terms are registered `'ps'` in the objective registry and added to the temporal
Benders `TEMPORAL_HANDLED_PS_COST` allowlist (they are plain per-level sums, so each
window sums its own start-ups). No re-baseline was needed after all: the goldens check
only the total `eTotalSCost`, not the cost-component breakdown, and at 1-hour resolution
(`pDuration = 1`) regrouping `'psn'`→`'ps'` leaves the total objective and the whole
primal solution identical (solve tier byte-unchanged, temporal Benders == monolith).
Guarded in `tests/test_formulation_fixes.py`; the C11 e2h-outside-`hgt` start-up test now
checks `eTotalHydSUCost`.

C16. **factor1 is applied twice to the FCR prices.** `pOperatingReservePrice_*` is
factor1-scaled at read (oM_InputData.py:150) and the three revenue constraints
multiply by `model.factor1` again (:110,114,118). Latent at factor1=1; squares on the
unit knob otherwise (same family as the C1 secondary and the storage-bound double
scaling, C24). **— DONE (Part C item 5, branch `fix/duration-factor1-money-terms`):**
the redundant in-constraint `model.factor1` is removed from all three FCR revenue terms
(`eEleMarketFCRDUpRevenue`/`FCRDDwRevenue`/`FCRNRevenue`), matching the day-ahead energy
price convention (scaled once at read, raw in the constraint). Latent at factor1=1, so
the goldens are byte-unchanged; guarded in `tests/test_formulation_fixes.py`.

C17. **FCR revenue covers `egnr`, but caps and provisions cover only
egt/egs/e2h.** A non-RES unit that is neither thermal (`ConstantVarCost == 0`) nor
storage has bid variables (declared over `eg|e2h`), is in no cap and no
bid-provision relation, but is paid revenue — with the participation flag defaulting
to 0 ("participates") for blank numeric columns, this is an unbounded objective for
such a unit. Related fragility: `pEleGenNoFCRD/N` get no `fillna` (oM_InputData.py:
274-275), so a blank cell in a string-typed column is NaN — neither 0 nor 1 — and the
unit escapes both the fixing and every FCR constraint while staying in the revenue
sum. (The e2h flags got `.fillna(1)`; the electricity flags should too.)
**— DONE (Part C item 5, branch `fix/fcr-bound-gaps`):** the three FCR revenue terms now
pay over the backed providers (`egt` / `egs` / `e2h`) -- the same sets the caps and
provisions cover -- instead of all of `egnr`, so a non-RES unit that is neither thermal
nor storage is no longer paid for a free, unbounded bid. And `pEleGenNoFCRD` /
`pEleGenNoFCRN` now get `.map(idxDict).fillna(1).astype('int')` like the e2h flags, so a
blank cell defaults to "not participating" instead of NaN. Latent in shipped cases (an
unbacked paid unit would already make the solve unbounded), so the goldens are
byte-unchanged; guarded in `tests/test_formulation_fixes.py`.

C18. **Static `pEleMaxCharge` fallback lets non-dischargeable units sell discharge
reserve.** With `pEleGenNoDayAhead == 1` (or MaxPower ~ 0), the discharge-headroom
constraints bound `DisUpDis + NorUpDis <= pEleMaxCharge` — a static charger rating
with no SoC/commitment link; the compensating fix-to-zero for non-V2G units fires
only when `NoDayAhead == 0` (oM_InputData.py:1542-1546).
**— DONE (Part C item 5, branch `fix/fcr-bound-gaps`):** the discharge-headroom fallback
branches (`eEleFreqUpDischargeHeadroom` / `eEleFreqDownDischargeHeadroom`) now bound the
discharge reserve by the DISCHARGE rating `pEleMaxPower`, not the charge rating. A
non-dischargeable unit (MaxPower ~ 0) then gets zero discharge headroom regardless of its
`NoDayAhead` flag; a `NoDayAhead` unit with real MaxPower is bounded by MaxPower (its
`output2ndBlock` is fixed to 0, so this matches the day-ahead branch). The compensating
fix-to-zero is now redundant but harmless. Latent in shipped cases (no FCR storage unit
has a zero discharge rating), goldens byte-unchanged; guarded in
`tests/test_formulation_fixes.py`.

C19. **Demand-only nodes get no balance — demand is silently dropped at zero
cost.** The build guards of `eEleBalance`/`eHydBalance` (:425,436) count units and
lines but not demands, so a node carrying only demand is skipped and `vENS/vHNS`
stay zero. Acknowledged as a workaround in `make_sizing_cases.py` (:192-196);
should be fixed in the model (include demand in the guard) so it prices HNS or fails
loudly.

C20. **Green-H2 matching counts the standby draw and ignores the PPA flag.**
`eGreenH2Matching` caps the full `vEleTotalCharge[e2h]` (standby included) by the sum
of **all** RES output regardless of `pEleGenPPA` (oM_GreenHydrogen.py:97-100), so
with matching on and no renewable output at night, standby is forced off — a cold
stop exactly where standby matters (the demo dodges this with `green=0`). Decide:
either standby is grid-powered (exclude `StandByPower*sb` from the matched quantity)
or document that standby must be renewable-backed. The matching pool should also
respect the PPA flag, and the same renewable MWh can currently both back the
electrolyser and be sold.

C21. **Investment coupling gaps.** (a) A candidate hydrogen *storage* unit's charge
is not capped by its build decision (`eHydInvestMaxCharge` covers e2h only;
electricity storage has all three caps) — an unbuilt store can absorb at nameplate
and spill for free. (b) FCR-down headroom of candidate units (e2h :682, storage
:574) uses the full nameplate, so a fractionally built unit can sell down-reserve on
capacity it does not have.
**— DONE (Part C item 5, branch `fix/fcr-bound-gaps`):** (a) new `eHydInvestMaxStorageCharge`
caps `vHydTotalCharge` of a candidate hydrogen store by `pHydMaxCharge * build fraction`,
mirroring the electricity storage charge cap. (b) the candidate branch of
`eEleFreqDownChargeHeadroom` scales the storage nameplate by `vEleGenInvest` in place
(linear, no commitment var there); the candidate electrolyser gets a separate build-cap
constraint `eEleFreqDownChargeHeadroomConvInvest` bounding the reserve plus charge by
`pHydMaxCharge2ndBlock * vHydGenInvest` (a separate constraint because the existing
commitment-gated headroom already multiplies the nameplate by the commitment, and scaling
by the build fraction too would be bilinear). Part (a) and the rest of the group are
golden-neutral, but part (b) is real money: the FCR-providing battery *sizing* cases are
candidates, so limiting their down-reserve to the built capacity raised their cost a
little (~0.01%, net revenue down) -- their 5 goldens were deliberately re-baselined
(HomeBattNoFCR, with no FCR, is unchanged). Guarded in `tests/test_formulation_fixes.py`.

C22. **`vTotalEleDCost` is fixed to zero if *any* storage unit lacks DoD
segments.** The fix sits inside `for egs in model.egs:` (oM_InputData.py:1372-1376),
so one non-degrading unit in a mixed fleet pins the *total* degradation-cost variable
at zero while `eTotalEleDCost` equates it to the (nonzero) sum — erasing the
degrading unit's cost or making the case infeasible. Aggregate the condition over all
units first. **— DONE (Part C item 5, branch `fix/storage-electrolyser-coupling`):** the
total-cost fix is now gated by `all(DoDS1+DoDS2+DoDS3 == 0 for egs in model.egs)` and
moved out of the per-unit loop, so the total is fixed to zero only when no storage unit
degrades; the per-unit DoD-variable fixing stays inside the loop. Latent in shipped cases
(no shipped case mixes a degrading and a non-degrading storage unit), goldens
byte-unchanged; guarded in `tests/test_formulation_fixes.py`.

C23. **Hydrogen charge upper bounds are never applied.** The bound loop tests
`if idx in model.hg:` with `idx` the full `(p,sc,n,unit)` tuple
(oM_InputData.py:1245-1253) — always False (the electricity loop correctly uses
`idx[-1]`). `vHydTotalCharge(2ndBlock)` get no ub and are constrained only where the
2nd-block constraints are built (skipped when `MaxCharge2ndBlock == 0`).

C24. **Mixed single/double factor1 scaling of storage bounds.** `pVarMin/MaxStorage`
are factor1-scaled at read and the inventory bounds + invest caps multiply by factor1
again, while the `p*GenMaximumStorage` fallback is scaled once. Coincides only at
factor1=1 (extends the Part B factor1-convention cleanup). **— DONE (Part C item 5,
branch `fix/duration-factor1-money-terms`):** `VarMinStorage` / `VarMaxStorage` are now
read unscaled (excluded from the `gen_frames_suffixes` factor1 loop), so the single
factor1 is applied once at the inventory-bound / investment-cap sites — the same place
the `GenMaximumStorage` fallback gets it, and consistent with the initial inventory
(`pGenInitialStorage * factor1`, scaled once at read). Their only consumer is the
`pVar*.replace(0, pGen*)` merge. Latent at factor1=1, so the goldens are byte-unchanged;
guarded in `tests/test_formulation_fixes.py`.

C25. **Hydrogen peak-indicator variables are declared on electricity-retailer sets
but fixed over hydrogen-retailer sets.** `vHydPeakGlobalInd/MonthInd/DayInd` are
`Var(model.psner,...)` etc. but the tariff fixing loops index them with `psnhr`
tuples (oM_InputData.py:1082-1104 vs 1422-1445) — `KeyError` as soon as a case has an
active hydrogen retailer; they also appear in no constraint (dead apart from the
broken fixing). **— ALREADY FIXED by C48 (same bug):** the indicators are now declared
*and* fixed over the hydrogen retail sets `psnhr` / `psdhr` / `psdnhr`, guarded by
`test_hydrogen_peak_indicators_on_hydrogen_sets`. They are still dead variables (no
constraint references them) — the hydrogen peak-tariff cost layer itself is unbuilt, as
noted under C48. Nothing further to do here.

C26. **Compressor consumption is dead data.** `MaxCompressorConsumption` is read and
unit-factored (oM_InputData.py:176) but referenced by no variable, constraint or
cost: hydrogen storage charging draws zero electricity and pays no compression energy
— a first-order term (1-4 kWh/kg) in any BTM hydrogen business case.

C27. **`pHydGenStandByStatus`/`StandByPower` have no missing-column default.**
Unlike the FCR columns added in the same feature (explicit fallback at
oM_InputData.py:282-291), `pHydGenStandByStatus` is mapped unconditionally (:277) and
`pHydGenStandByPower` is used unguarded in `eAllEnergy2Hyd` — an older
hydrogen-generation CSV without the columns crashes.

### LOW — fragile, vacuous, or cosmetic

C28. `eE2HMinCharge2ndBlock` (:1128-1133) is vacuous: `2ndBlock/Max >= uc - 1` with a
NonNegative LHS and a nonpositive RHS can never bind. The state chain rests entirely
on the Max constraint (which suffices for FCR-up; see C3 for the down side).
**— DONE (documented, batch 1): this is a standard openTEPES min-2nd-block symmetry
row (like `eHydMinESSOutput2ndBlock` / `eHydMinOutput2ndBlock`), non-binding by design,
not a bug. A comment at the constraint records this; no logic change.**
C29. The `>= 0` gates on `pOperatingReserveRequire_*` (27 sites) are always true
(the parameter is `fillna(0)` and clamped); clearly meant `> 0`. No wrong solutions,
just dead gating and redundant rows. **— DONE (batch 1): all 28 per-unit FCR build
gates flipped `>= 0` -> `> 0`, so a zero-requirement level skips the dead rows; the
requirement caps (count-gated, not requirement-gated) still bind the bids to zero, so
the FCR goldens (HomeBattFCRDonly/FCRNonly, ElectrolyserFCR) are byte-unchanged. Guarded
by `test_reserve_require_gates_use_strict_positive`.**
C30. The endurance constraints (storage :620-632 and e2h :705-716) pair the level-n
inventory with the bid at n-1 and skip `n.first()`, so the **last** level's bid is in
no endurance constraint — end-of-horizon bids are free of the energy backing.
**— DONE (batch 3, GOLDENS RE-BASELINED): three additive terminal-level constraints
(`eEleStorageEnduranceUpEnd` / `DownEnd` for storage, `eEleFreqDownEnduranceConvEnd` for the
e2h node) back the last load level's FCR bid with the last level's inventory/store headroom
(the inventory one period ahead does not exist). The interior rolling constraints are
unchanged. This removes a free end-of-horizon reserve bid, so the four sizing cases that
exploited it cost a little more: HoodBatt -22.042 -> -19.989, HomeBattFCRNonly 56.980 ->
57.350, H2Tank 6774.093 -> 6776.720, Electrolyser 6774.090 -> 6776.716 (all UP, the correct
direction). The other goldens were not bidding at the last level and are unchanged. Guarded by
`test_terminal_endurance_constraints_exist`.**
C31. The FCR-N volume cap (:466) uses the *average* of the up/down requirements; for
a symmetric product the deliverable volume is the *minimum*. Exact when the inputs
are equal (the usual case). **— DONE (batch 3): the volume cap now uses
`min(Require_FCRN_Up, Require_FCRN_Down)`; the FCR-N revenue price average is a separate,
legitimate term and is untouched. Byte-unchanged in every shipped/sizing case because the
FCR-N up and down requirements are equal there (min == avg), so no golden moved. Guarded by
`test_fcrn_volume_cap_uses_minimum_not_average`.**
C32. RES units get FCR bid variables (declared over `eg|e2h`) that are in no cap, no
relation, no revenue, and are never fixed — dead variables that can carry arbitrary
values into the output tables. **— DONE (batch 1): the existing FCR fixing loops run
over `psnegnr` (non-RES) and `psne2h`, never touching `egr`; a new loop over `model.psnegr`
fixes the three RES bid variables to zero. They enter no constraint or objective term, so
the goldens are byte-unchanged. Guarded by `test_res_fcr_bid_variables_are_fixed`.**
C33. `eEleFreqUp/DownChargeBound` (:581,591,598,608) divide by `pEleMaxCharge` with
no positivity guard (the e2h analogues guard) — `ZeroDivisionError` for a
discharge-only ESS with default flags.
C34. With `pParNumberPowerPeaks == 0` the peak cost (:72) charges a power tariff
with no kW quantity — a dimensionally meaningless constant. **— DONE (warning, batch 2):
the constant is a fixed objective offset, so it does not change the optimal solution
(only the reported total cost). A load-time warning now fires when `pParNumberPowerPeaks
== 0` and a non-zero `pEleRetPowerTariff` is set. Zeroing the offset would move any
golden that hits this config, so it is left as an optional follow-up. Byte-unchanged.**
C35. The per-unit binary relaxation loop (oM_InputData.py:1458-1462) never relaxes
`vHydGenStandBy` and runs over `hgt` (skipping an e2h with `ConstantVarCost == 0`);
in the LP default the three-state logic is continuously gameable (the demo correctly
forces `binary_uc`). Document that standby results need binary UC. **— DONE (warning,
batch 2): a load-time warning fires when a standby-capable electrolyser is run with
relaxed commitment (`pOptIndBinGenOperat == 0`), stating the standby schedule needs
binary UC to be meaningful. Byte-unchanged.**
C36. `vHydGenShutDown[e2h] = 0` by design, but a nonzero `ShutDownCost` in the data
(AEL_01: 1000) is silently ignored — deserves a load-time warning. **— DONE (warning,
batch 2): a per-unit warning fires for any electrolyser with `ShutDownCost > 0`, noting
the shut-down variable is fixed to zero so the cost is ignored. Byte-unchanged.**
C37. Hydrogen storage outflow ramps (:1488,1498) reuse the *generation* ramp
parameter `pHydGenRampUp/Down` where electricity had dedicated outflow-ramp
parameters (commented out) — different physical limits. **— DONE (documented, batch 3):
a comment at the H2 charge/outflow ramp records that it reuses the generation ramp because
no dedicated hydrogen outflow-ramp parameter exists in the input schema (the electricity
side defines `pEleGenOutflowsRampUp/Down` but leaves the matching constraint commented out,
so electricity storage has no outflow ramp at all). Adding a dedicated `pHydGenOutflowsRamp*`
parameter with a fallback to the generation ramp (keeping existing cases unchanged) is the
documented follow-up -- a data-schema decision, not changed here. Guarded by
`test_h2_storage_ramp_reuse_is_documented`.**
C38. `eTotalICost` multiplies the lump-sum annualized investment cost by `factor1`
(oM_Investment.py:162) — dimensionally suspect unless `FixedInvestmentCost` is
per-unit-capacity (assert the convention); doc says `[MEUR]`, objective says
`[kEUR]`. **— DONE (documented, batch 4): unit labels fixed -- `vTotalICost` is added
directly to the `[EUR]` operating-cost components in `eTotalSCost` with no conversion, so
its `[MEUR]` label was wrong; it and the objective doc are now `[EUR]`. The factor1
multiplication is documented as the asserted convention: it is dimensionally consistent
only because EVERY objective term is scaled by factor1, so factor1 is a global objective
scalar that does not change the argmin (build-vs-operate trade-off invariant under the unit
choice). All shipped cases run at factor1 == 1 (a no-op), so this is latent; a factor1 != 1
regression test is the documented follow-up. Doc-only, byte-unchanged; guarded by
`test_investment_cost_unit_label_consistent`.**
**— FOLLOW-UP RESOLVED (factor1 != 1 investigation): the "global objective scalar" claim
above is WRONG and is corrected. Probing factor1 = 2 on HomeBatt changed the optimum
(cost 44.28 -> -25.48, sign flipped; total output ratio 2.48 and charge ratio 2.53, not 2.0),
proving factor1 != 1 does not preserve the solution. Root cause: variable cost terms (grid
transfer fee :83, energy tax :166, energy/FCR) are `rate * factor1 * quantity` and the
quantity is itself factor1-scaled, so they scale as ~factor1^2, while the fixed charges
(`fastavgift` :88, flat peak tariff :72) scale as ~factor1^1. So factor1 is neither a valid
unit conversion (which needs rate and quantity to scale OPPOSITELY) nor a global scalar
(which needs every term to scale by the same power); only factor1 == 1 is dimensionally
consistent. Resolution (user decision): pin factor1 to 1.0 with an `assert factor1 == 1.0`
guard and a full explanation at `oM_InputData.data_processing` (the one place it is set), and
correct the misleading comment in `oM_Investment`. Guarded by `test_factor1_is_pinned_to_one`.
Future work: make factor1 a dimensionally consistent rescaling (rate and quantity scale
oppositely; fixed charges reconciled) and THEN promote it to a `dfParameter` CSV/DB input
alongside the other `pPar*` parameters -- exposing it as input before the fix would surface a
knob that silently produces inconsistent results.**
C39. A future-dated investment candidate (`InitialPeriod > base year`) is silently
dropped from the model with no warning (the sizing generator works around it by
rewriting `InitialPeriod`). **— DONE (warning, batch 2): after the generation sets are
built, a warning lists any electricity or hydrogen unit dropped because its
`InitialPeriod` is after the economic base year (single-period run). Byte-unchanged.**
C40. Heat sector (oM_HeatSector.py): no `COP x heat-to-power efficiency < 1` data
guard (a free power-heat-power loop is representable); the thermal store has no
cyclic/terminal condition (initial stock is free energy, horizon ends empty); store
charge/discharge bounds use the *energy* capacity as a power rating with no mutual
exclusivity; a store-only node is missing from the heat-balance node list
(`n2hts` not in the union); `vHeatNotServed` is uncapped.
**— DONE (batch 5). No shipped/sizing golden carries heat tables, so all five are latent for
the cost goldens; verified against `tests/test_heat_sector.py`. Fixes:**
- **store-only node now in the balance node union (`n2hts` added), so a store on its own node
  is constrained instead of free;**
- **`vHeatNotServed` capped by demand (`eHeatNotServedCap`), so it cannot be a paid sink
  (mirrors hydrogen C41);**
- **thermal-store terminal condition added (`eHeatInventoryTerminal`: final inventory >=
  initial), so the initial stock is not free energy drained over the horizon -- the
  defensible default, matching the electricity store's cycle-time-step tie; chosen autonomously
  and flagged (a strict `== initial` cyclic form is the alternative);**
- **free power-heat-power loop now warned at load time when `COP x efficiency >= 1` (such a
  loop makes the LP unbounded);**
- **power-rating / mutual-exclusivity (charge/discharge bounded by the energy capacity, no
  charge-XOR-discharge binary): DOCUMENTED as a known limitation -- harmless at the optimum
  under `StoEff < 1`; a dedicated power-rating parameter + mutual-exclusivity binary is a
  schema/MIP follow-up, not changed here.**
**Guarded by `test_heat_store_terminal_and_not_served_cap`, `test_heat_store_only_node_enters_balance`,
`test_power_heat_power_loop_warns`.**
C41. Flexible hydrogen demand has no recovery constraint (unlike
`eEleDemandShiftBalance`) and `vHNS <= pVarMaxDemand` regardless of the flexed
demand — `vHydDemand - vHNS` can go negative (a paid sink).
C42. `eEleInflows2Commitment` / `Outflows2Commitment` families (:730-756, 954-980)
contain no commitment variable despite name and doc — parameter-bound duplicates.
**— DONE (documented, batch 1): the misleading "to commitment" doc strings and the two
section comments are corrected to state these bound the in/outflow variable by its
parameter limit (the commitment-coupled form was never wired). The attribute name
`...2Commitment` is deliberately retained to avoid renaming the constraint in result/.lp
output — a separate cosmetic refactor. Guarded by `test_inflow_outflow_bound_docs_not_commitment`.**
C43. `pHydRetMaxBuy/Sell` exist only if the optional CSV columns do — the first case
that activates a hydrogen retailer on a column-less file gets `KeyError` (no schema
default, unlike the electricity peak factors).
C44. The hydrogen day-ahead buy cost is stored in `vTotalHydMrkPPACost` under rule
name `eHydMarketDayAheadCost` registered as `eTotalHydTradeCost` — misattributed in
any report that greps by name. **— DONE (batch 2): the constraint attribute is renamed
from `eTotalHydTradeCost` to `eHydMarketDayAheadCost`, matching its rule and the
electricity analogue `eEleMarketDayAheadCost` (the old name was referenced nowhere else).
The destination variable `vTotalHydMrkPPACost` actually holds the day-ahead trade cost;
a comment records that the "PPA" in its name is historical, and the variable rename is
deferred to avoid touching the objective registry and result-table columns. Byte-unchanged;
guarded by `test_hydrogen_day_ahead_constraint_name_matches_rule`.**
C45. Tautological `(NoDayAhead==1 or NoDayAhead==0)` conjuncts (:1057,1070,1100,
1111) make the binary-gated 2nd-block branch unreachable for FCR-capable storage —
dead logic; mutual exclusion still holds via the charge/discharge decisions.
**— DONE (batch 1): the always-true conjunct is removed from the four ESS 2nd-block
output/charge bounds. Behaviour is unchanged (an always-true `and` term drops out), so
the goldens are byte-unchanged. The binary-gated `else` branch stays reachable only for
non-FCR storage, as before; making it FCR-reachable would be a separate modelling
decision. Guarded by `test_no_tautological_nodayahead_conjunct`.**
C46. First-step electricity ramp (:1340,1350) uses `pEleSystemOutput` — a *system*
aggregate, and a scalar overwritten across (p,sc) so only the last scenario's value
survives — as each unit's pre-horizon output; essentially vacuous for small units.
**— DONE (batch 3): both first-step ramp branches now use the unit's own
`pEleInitialOutput[p,sc,egt]` (per-unit, indexed over `ps * eg`) instead of the system
scalar. Latent in every shipped/sizing golden (none has a thermal `egt` unit with an active
ramp at the first level), so no golden moved. Guarded by
`test_first_step_ramp_uses_per_unit_initial_output`.**
C47. `pHydRetTariffType` is read by the peak-variable fixing loops but never created —
the hydrogen retail file carries no `TariffType` column, so the first case that
activates a hydrogen retailer crashes with `KeyError` (same family as C43). **— FIXED
(hydrogen sizing-case redesign):** optional-column default `''` (no peak tariff) for
both carriers, next to the C43 MaxBuy/MaxSell default; guarded in
`tests/test_formulation_fixes.py`.
C48. The hydrogen peak-hour indicators (`vHydPeakGlobalInd` / `vHydPeakMonthInd` /
`vHydPeakDayInd`) were declared over the *electricity* retail sets
(`psner`/`psder`/`psdner`, both domain branches), and the no-peak fixing block also
iterated the electricity sets — `KeyError` as soon as the hydrogen and electricity
retailer sets differ. **— FIXED (hydrogen sizing-case redesign):** declared and fixed
over `psnhr`/`psdhr`/`psdnhr`; guarded in `tests/test_formulation_fixes.py`. Note these
indicators appear in no constraint (dead variables) — the hydrogen peak-tariff cost
layer itself is still unbuilt.

### Suggested sequencing

1. **Money now (live in shipped cases):** C1 (O&M double-count) — then re-baseline the
   goldens deliberately. **— DONE (branch `fix/om-double-count`):** `LinearVarCost` is now
   fuel-only, O&M added once in the objective (also fixes the secondary factor1-squared
   scaling). No re-baseline was needed after all: the only O&M-bearing active unit is the
   electrolyser, and every case with a producing electrolyser is `xfail` (H2Tank /
   Electrolyser) or decision/structure-checked (the demos), so no enforced golden moves
   (solve tier 47 passed / 2 xfail). Guarded in `tests/test_formulation_fixes.py`.
2. **Crash-on-first-use:** C2 (n2g), C5 (NorUpDis indexing), C8 (stale `n`), C27
   (standby column default), C33 (zero divide). **— DONE (branch
   `fix/formulation-crash-batch`):** all five fixed and guarded in
   `tests/test_formulation_fixes.py`; latent-only, so the goldens are byte-unchanged
   (solve tier 47 passed / 2 xfail).
3. **Electrolyser FCR/three-state credibility (before using the feature in a
   study):** C3, C4, C6, C10, C11, C13, C20. **— C3/C4/C6/C10/C11/C13 DONE (branch
   `fix/electrolyser-credibility`):** FCR-down headroom state-gated + no-store endurance
   binds; standby-from-warm transition (`pHydInitialStandBy`); retail buys the full e2h
   load; FCR activation modulates the e2h charge; start-up cost billed for e2h outside
   `hgt`; C13 documented as a deliberate omission (electrolyser is a fast-ramping load,
   Hashmi 2024 / Mansouri 2026). All e2h-only, so the goldens are unchanged; guarded in
   `tests/test_formulation_fixes.py`. **C20 DONE (branch `feature/rfnbo-allocation`):**
   matching now uses a renewable->electrolyser allocation (`vEleResToE2h` + per-unit cap)
   over the PPA-flagged pool and matches only the productive draw (standby excluded, EU
   2023/1184 Art. 6). Finding: the allocation cannot bind differently from the aggregate
   bound until electricity sales carry a Guarantee-of-Origin value (Mansouri 2026) -- that
   GO/certificate layer (the same-MWh-sold-and-matched fix) is the documented follow-up,
   pending the Elsevier reference. Matching-on cases are xfail/build-only, so goldens
   unchanged. **Part C item 3 complete.**
4. **Hydrogen-case enablement (with the H2Tank/Electrolyser xfail redesign):** C7,
   C19, C23, C26, C41, C43. **— C7/C19/C23/C41/C43 DONE (branch
   `feature/hydrogen-case-enablement`):** hydrogen charge cap actually applied
   (`idx[-1]` membership test); free unpriced `vHydImport`/`vHydExport` closed wherever
   no priced hydrogen retailer composes them (single-node included); demand counted in
   the `eEleBalance`/`eHydBalance` build guards so a demand-only node is not dropped;
   `pHydRetMaxBuy/Sell` get a missing-column default (0.0 = no cap) for both carriers;
   `eHydNotServedCap` caps `vHNS <= vHydDemand` for flexible hydrogen demand (no
   paid sink). All latent in the shipped non-hydrogen cases, so the goldens are
   unchanged; guarded in `tests/test_formulation_fixes.py`. **C26 DONE (branch
   `feature/compressor-consumption`, stacked on the above):** charging a hydrogen store
   now draws `MaxCompressorConsumption * charge` electricity as a load on the store's
   node (`eEleBalance`), and the balance is built where a compressor-bearing store sits
   even with no other electricity asset. The rate sits on `PEMEL_01` (a
   `StorageType=Hourly` store), which is in the base year only for the hydrogen sizing
   cases `H2Tank`/`Electrolyser` (both `xfail`), so no enforced golden moves; the four
   headline goldens and `ElectrolyserStandby`/`FCR` (which push the store out of the
   base year, or test build/decision not cost) are unaffected. `factor1` is 1.0 so the
   rate is applied as stored; the 0.0012 magnitude (~1.2 kWh/kgH2 if MWh/kgH2) is a
   data-units note for the case author. **The H2Tank/Electrolyser xfail redesign is
   DONE (branch `feature/h2-sizing-redesign`):** the hydrogen retailer moves to the
   converter node with a buy allowance and a day/night import price (night below the
   electrolyser's ~53/kg production cost, day above it), and the tank gets finite
   ratings with an empty start (its 12 kg inventory floor and 15 kg initial fill do
   not scale with the build fraction, so a candidate tank was forced to build itself).
   Both cases now solve with the 5 kgH2/h demand fully served and make real sizing
   decisions — the tank builds in full on night-to-day arbitrage, the electrolyser
   builds a small fraction — so the two `xfail` marks are gone and the goldens are
   enforced; the build decisions are asserted separately
   (`test_h2_sizing_decisions`). Enabling the first active hydrogen retailer
   surfaced two more latent crashes, fixed on the same branch: C47 (missing
   `pHydRetTariffType` default) and C48 (hydrogen peak indicators declared over the
   electricity retail sets). **Part C item 4 complete.**
5. The rest with their subsystem.

## Status / sequencing

- **Done (merged or in flight):** Part A concept-page rewrite; ENS/HNS double-count
  (item 1); hydrogen storage charge/discharge swap (item 2); hydrogen storage-energy
  `factor1` scaling (item 1 sub-point); electricity + hydrogen storage unit labels
  (`kW`/`kWh`, `kgH2/h`/`kgH2`); heat inventory duration weighting (item 8).
- **Flagged, not changed (modelling-judgement review):** items 3-7 -- notably
  `vTotalHydDCost` with no defining constraint (item 3); the rest are low severity.
- Re-run the strict docs build (`sphinx -W`) after any docstring change (the
  `.githooks/pre-push` hook does this).
