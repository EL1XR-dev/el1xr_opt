# Scope: electrolyser (e2h) FCR provision

Concrete design for letting an electrolyser provide frequency containment reserve
(FCR-D / FCR-N) by modulating its electricity consumption. It mirrors the existing
**storage charge-side** FCR formulation (`oM_ModelFormulation.create_constraints`,
the `egs` reserve block) onto the `e2h` converter set. **Scope only — no code
changed yet.** Decisions left to the modeller are marked **[DECIDE]**.

## Context / correction

FCR in el1xr is a **revenue opportunity capped by market depth**, not a mandate: the
requirement rows are `sum(bids) <= pOperatingReserveRequire_*` (e.g.
`eEleFreqContReserveDisUpward`), and the FCR revenue terms in the objective pay for the
bids. So:

- A unit that cannot bid simply earns no FCR revenue; it does **not** make the model
  infeasible. The earlier suggestion that the missing electrolyser FCR caused the
  `H2Tank` infeasibility was wrong -- that infeasibility is on the electricity
  storage / EV state-of-charge side and persists with FCR switched off.
- Therefore this feature **adds a revenue capability** (an electrolyser earning FCR by
  offering consumption flexibility, which is physically real), but it will **not** on
  its own clear the H2 sizing-case `xfail`s.

## Physical model

An electrolyser is a controllable **load** (it only consumes electricity; no
injection). As an FCR provider it offers, around its scheduled consumption `c`:

- **FCR-up** (system needs more power / less load): the electrolyser **reduces**
  consumption. Capability is bounded by how much it is currently consuming above its
  minimum -- i.e. its 2nd-block input.
- **FCR-down** (system needs less power / more load): the electrolyser **increases**
  consumption. Capability is bounded by the remaining input headroom up to its rated
  input.

There is **no discharge side** (unlike a battery), so only the charge-side half of the
storage FCR formulation applies.

## Quantities (already in the model)

For a converter `c` in `model.e2h`:

| symbol | model object | meaning |
|---|---|---|
| `c_c` | `vEleTotalCharge[p,sc,n,c]` | electricity input (consumption) |
| `c2_c` | `vEleTotalCharge2ndBlock[p,sc,n,c]` | input above the minimum (the flexible part) |
| `C_c` | `pHydMaxCharge[c][p,sc,n]` | rated electricity input (the e2h "charge" cap; the
  same parameter `eHydInvestMaxCharge` / `eE2HMaxCharge2ndBlock` already use) |
| `u_c` | `vHydGenCommitment[p,sc,n,c]` | converter on/off (UnitInterval when UC relaxed) |
| `A_c` | `pVarFixedAvailability[c][p,sc,n]` | availability |

## New / extended variables

Reserve **provision** (charge-side only), per `(p,sc,n,c)` for `c` in `e2h`:

    f_DisUpCha[c], f_DisDownCha[c], f_NorUpCha[c], f_NorDownCha[c]   >= 0

Cleanest implementation: **extend the existing charge-side provision variables from
`egs` to `eh = egs | e2h`** (the discharge-side `...Dis` variables stay `egs`-only), and
extend the **bid** variables from `eg` to `eg | e2h`:

    vEleFreqContReserveDisUpwardBid / DisDownwardBid / NorBid   over  eg | e2h

The alternative is a parallel set of `e2h`-named variables; extending `eh`/`eg|e2h` is
less duplication and lets the requirement/revenue sums stay single expressions.

## New constraints (per `(p,sc,n,c)`, `c in e2h`), mirroring the storage charge side

**Bid = charge-side provision** (analogue of `eEleRelationFreq*Bid2Stor`, with no
discharge term):

    eEleRelationFreqDisUpBid2Conv :  bid_DisUp[c]   == f_DisUpCha[c]
    eEleRelationFreqDisDownBid2Conv: bid_DisDown[c] == f_DisDownCha[c]
    eEleRelationFreqNorUpBid2Conv :  bid_Nor[c]     == f_NorUpCha[c]
    eEleRelationFreqNorDownBid2Conv: bid_Nor[c]     == f_NorDownCha[c]

**FCR-N symmetry** (analogue of `eEleSymmFreqNorStor2Ch`):

    eEleSymmFreqNorConv :  f_NorUpCha[c] == f_NorDownCha[c]

**Headroom** (analogue of `eEleFreqUpChargeHeadroom` / `eEleFreqDownChargeHeadroom`):

    eEleFreqUpChargeHeadroomConv :   f_DisUpCha[c]   + f_NorUpCha[c]   <= c2_c
    eEleFreqDownChargeHeadroomConv:  f_DisDownCha[c] + f_NorDownCha[c] <= C_c - c2_c

(up = reduce consumption, bounded by the flexible input already scheduled; down =
increase consumption, bounded by the remaining input headroom.)

**Availability bound** (analogue of `eEleFreqUpChargeBound` / `eEleFreqDownChargeBound`):

    eEleFreqUpChargeBoundConv :   (f_DisUpCha[c]   + f_NorUpCha[c])   / C_c <= A_c
    eEleFreqDownChargeBoundConv:  (f_DisDownCha[c] + f_NorDownCha[c]) / C_c <= A_c

## Plug into existing aggregates

**Requirement caps** -- add the `e2h` bids to the three requirement sums
(`eEleFreqContReserveDisUpward` / `...DisDownward` / `...Nor`), exactly like the `egs`
term is already added:

    sum_egt bid + sum_egs bid + sum_{c in e2h} bid_*[c]  <=  pOperatingReserveRequire_*

**Revenue** -- add the `e2h` bids to the FCR revenue terms
(`eEleMarketFCRDUpRevenue` / `...FCRDDwRevenue` / `...FCRNRevenue`, which today sum over
`egnr`), so the electrolyser is paid for the reserve it offers.

## Decisions for the modeller [DECIDE]

1. **Participation flag.** Storage gates on `pEleGenNoFCRD` / `pEleGenNoFCRN`. The
   electrolyser is a *hydrogen* unit, so it needs an equivalent flag -- add
   `NoFCRD` / `NoFCRN` columns to the hydrogen-generation data (read as
   `pHydGenNoFCRD` / `pHydGenNoFCRN`) and gate the new constraints on them. Default:
   not participating, so existing cases are unchanged.
2. **Products.** FCR-D only, FCR-N only, or both? (The mirror above includes both.)
3. **Endurance.** Storage has `eEleStorageEndurance{Up,Down}` tying a sustained bid to
   stored energy. A load is different: FCR-up (cutting consumption) needs no stored
   energy, but FCR-down (raising consumption) only makes sense if the extra hydrogen can
   be absorbed -- by the downstream H2 storage headroom or demand. Options: (a) no
   endurance constraint for `e2h` (simplest, treats FCR as an instantaneous capability),
   or (b) tie FCR-down to the H2-store headroom / tank state. **Recommend (a) first**,
   add (b) only if over-crediting becomes an issue.
4. **Set wiring.** Extend `egs`->`eh` and `eg`->`eg|e2h` on the existing
   variables/sums (recommended), vs. a parallel `e2h` variable family.

## Validation plan

- A small case with an electrolyser, a non-zero FCR requirement, and cheap/zero H2
  demand: the electrolyser should bid FCR up to the lower of its headroom and the
  requirement, and earn the corresponding revenue; objective should drop by exactly the
  FCR revenue vs. the no-FCR-for-e2h baseline.
- Goldens: gate the new constraints on the new participation flag (default off), so the
  four validation cases and the existing sizing cases are byte-for-byte unchanged.
- A regression test asserting the `e2h` bid variable and the headroom/bound constraints
  exist and reference the electrolyser's `vEleTotalCharge` (mirror of the storage FCR
  tests).

## Effort

Moderate: ~6 new constraint families (all close mirrors of existing `egs` ones), 1 set
extension, 2 aggregate-sum edits, 1 new data flag, plus tests. No new variable *types*
if the existing charge-side/bid variables are extended to `eh` / `eg|e2h`.
