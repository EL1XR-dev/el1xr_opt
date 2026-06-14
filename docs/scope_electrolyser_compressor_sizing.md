# Scope: compressor sizing (hydrogen-storage compressor as an investment decision)

Concrete design for making the hydrogen compressor an **investment/sizing decision**, alongside the
electrolyser and the tank, which are already sized via `vHydGenInvest`. Today the compressor has no
capacity variable and no capex — its electricity draw is a fixed ratio of the tank charge flow. This
closes that gap and (optionally, Phase 2) couples the built compressor rate to FCR-down endurance.

## Motivation

The electrolyser makes hydrogen at low pressure; storing it requires compression, which draws
electricity. el1xr already captures the *energy* (`pHydGenMaxCompressorConsumption[hgs]` kWh/kg ×
`vHydTotalCharge` kg in the electricity balance), but not the compressor as a *capacity*:

- a real compressor has a **rated throughput** (kg/h) that limits how fast the tank can be filled;
- it has a **capital cost** that scales with that rating.

A sized compressor matters economically (cheap-slow vs expensive-fast) and physically (it caps the
rate at which sustained FCR-down can push extra hydrogen into the tank — the endurance story).

## Current gap

Electrolyser and tank are sized via `vHydGenInvest ∈ [0,1]` build-fractions with `pHydGenInvestCost`
capex (`oM_Investment.py`). The compressor has neither a capacity variable nor a capex term — its
draw is just a fixed ratio of `vHydTotalCharge`. It is the one asset of the three with no investment
decision.

## Design principles

- **Match the existing investment convention** (build-fraction × nameplate, optional binary), so it
  composes with `pHydGenBinaryInvestment`, the investment bounds, and `eTotalICost`.
- **Default-off ⇒ byte-unchanged.** No compressor data ⇒ no variable, no constraint, no capex ⇒
  every existing golden is bit-for-bit identical (same gating as electrolyser/tank investment).
- **Respect the factor1 classification** (Phase A): nameplate is a quantity (× factor1); capex is an
  investment lump sum (drops factor1).

## Modelling choice — size by throughput

Compressor consumption is linear in mass flow (constant kWh/kg), so throughput (kg/step) and rated
power (kW) are equivalent up to that constant. **Size by throughput** — `pHydGenCompNameplate[hgs]`
in kg/step — because it bounds `vHydTotalCharge` directly, in the same units/convention as the
existing tank-charge bound `pHydMaxCharge`. (Power-based sizing is just this divided by the kWh/kg
ratio — no added expressiveness.)

## Model objects

**Set** (candidates only, so default-off holds):

    hgcompc = [ hgs in model.hgs : pHydGenCompInvestCost[hgs] > 0 ]

**Data columns** on the hydrogen-generation input (both optional, default 0 → no-op):

| Column | Param | Meaning | Units | factor1 |
|---|---|---|---|---|
| `CompressorNameplate` | `pHydGenCompNameplate[hgs]` | rated compressor throughput | kgH2/step | quantity → x factor1 |
| `CompressorInvestCost` | `pHydGenCompInvestCost[hgs]` | annualized capex per unit nameplate | currency | lump sum → drops factor1 |

**Variable** (mirrors `vHydGenInvest`):

    vHydCompInvest[hgs] in [0,1]      for hgs in hgcompc

Continuous by default; Binary if the storage unit's `pHydGenBinaryInvestment[hgs] == 1` (reused, no
new flag in Phase 1).

## Constraints

**Core — duty bound** (`oM_Investment.py`, beside `eHydInvestMaxStorageCharge`), per `(p,sc,n)`,
`hgs in hgcompc`:

    vHydTotalCharge[p,sc,n,hgs]  <=  pHydGenCompNameplate[hgs] * factor1 * vHydCompInvest[hgs]

The compressor moves at most its built throughput. This sits alongside the tank-charge-port bound
(`vHydTotalCharge <= pHydMaxCharge * vHydGenInvest[hgsc]`); the model takes the binding one — so a big
tank with a small compressor (or the reverse) becomes a real choice.

**Core — capex** (extend `eTotalICost`):

    + sum_{hgs in hgcompc} pHydGenCompInvestCost[hgs] * vHydCompInvest[hgs]

**Optional (Phase 2) — FCR-down rate coupling** (`oM_ModelFormulation.py`, mirroring the node-level
`eEleFreqDownEnduranceConv`). FCR-down endurance currently bounds the extra hydrogen by tank
*headroom* (a volume limit). Physically it is also bounded by the compressor *rate*: the extra
production from a held down-bid must fit through the spare compressor throughput at the node:

    sum_{e2h @ nd} bid_down[e2h] / PF[e2h]
      <= sum_{hgs @ nd} ( pHydGenCompNameplate[hgs]*factor1*vHydCompInvest[hgs] - vHydTotalCharge[hgs] )

This makes FCR-down need both empty volume (existing) and a fast-enough compressor (new) — the
physically complete picture.

## What stays untouched

- The electricity-balance term (`ratio * vHydTotalCharge`) is unchanged; we add a cap on the flow and
  a capex, not a new per-kg energy.
- No commitment/standby on the compressor — it stays a continuous capacity bound (consistent with how
  el1xr models it today). Explicit non-goal.

## Files

- `oM_InputData.py` — read the two columns (default 0); build `hgcompc`.
- `oM_Investment.py` — declare `vHydCompInvest`; add `eHydInvestMaxCompressor` (duty bound); extend
  `eTotalICost`.
- `oM_ModelFormulation.py` — Phase 2 only — add the FCR-down rate coupling.
- `data/sizing/make_sizing_cases.py` — add the columns to whichever case(s) should size a compressor.
- `tests/test_run.py` — structural test, default-off byte-unchanged check, a sizing-response test,
  factor1 invariance.

## Validation & tests

- **Input guard:** `pHydGenCompInvestCost > 0` with `pHydGenCompNameplate == 0` → hard error (would
  silently force `charge = 0`).
- **Byte-unchanged:** full solve tier with compressor off.
- **Sizing response:** high compressor capex → smaller compressor, throttled charge flow; low capex →
  full build. Assert `vHydCompInvest` moves and the duty bound binds.
- **factor1 invariance:** ratio 1.00000 at factor1 = 1 vs 2 with compressor sizing on.

## Phasing

- **Phase 1 (core):** duty bound + capex. Default-off, byte-unchanged, small and safe. Closes the
  el1xr feature gap so all three assets are sized.
- **Phase 2 (DONE, novelty):** the FCR-down rate coupling — `eEleFreqDownCompressorRate` in
  oM_ModelFormulation. Per node and load level, the extra hydrogen a held FCR-down bid would make
  (sum of DisDownward + Nor bids / ProductionFunction) plus the baseline charge must fit the built
  compressor throughput. Gated on a node having BOTH FCR-flagged electrolysers and a compressor-sizing
  candidate, so it is default-off byte-unchanged: the existing e2h FCR goldens are NOT re-baselined
  (no shipped case combines compressor sizing with FCR). Demonstrated by the new
  `ElectrolyserFCRCompressor` case (structural + solve tests). This is the contribution — Johnsen 2026
  folds the compressor away entirely, and no reviewed paper gates FCR-down by compressor throughput.

## Novelty note

Phase 1 alone is NOT novel — Dadkhah 2022 already sizes a compressor with ancillary-service revenue;
it is a correctness/completeness fix. Phase 2 (compressor rate gating FCR-down) is the differentiator.
See `docs/lit_review_electrolyser_fcr.md` for the prior-art assessment.

## Decisions (resolved 2026-06-14)

1. Build-fraction × nameplate (consistent with existing investment layer). **Chosen.**
2. Throughput-based nameplate. **Chosen.**
3. Phase 1 first (goldens clean), Phase 2 as its own re-baselined PR. **Chosen.**
4. Sizing case(s) to carry a compressor: TBD during implementation (a case that already has H2 tank +
   compressor consumption).
5. Reuse the storage unit's binary/bounds flags (no new flag in Phase 1). **Chosen.**
