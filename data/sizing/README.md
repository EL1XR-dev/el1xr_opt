# Sizing and variant CI cases

These are small, fast, linear cases used by the test suite to check that the
investment (sizing), tariff and frequency-market features keep working. They are
**generated, not committed**: only `make_sizing_cases.py` is in the repository,
and it rebuilds the cases from the `H2VPP` base case.

```bash
python data/sizing/make_sizing_cases.py            # writes data/sizing/<Case>.duckdb
python data/sizing/make_sizing_cases.py --keep-csv # also keep the CSV folders
```

Each case is written as a single `<Case>.duckdb` file (read through the same
interface as a CSV folder). The test suite regenerates them before running, so
nothing here needs to be committed.

## Why generate instead of commit?

The goal was to keep the repository small. For these small cases a DuckDB file is
actually *larger* than the CSV folder (about 4 MB vs 0.5 MB), because DuckDB
reserves at least one storage block per table and a case has ~120 tables. So the
smallest option is to commit only the generator (a few kB) and rebuild the cases
on demand. DuckDB still pays off as an input format for *large* cases, where its
columnar compression beats the CSV text.

## Cases

All cases are derived from `H2VPP`, cut to the first 168 load levels (one week),
with unit commitment relaxed so the model is an LP and the cost is reproducible.
Day-ahead market participation is on in every case.

| Case               | What it exercises                                   |
|--------------------|-----------------------------------------------------|
| `HomeBatt`         | size a home battery; FCR-D and FCR-N on             |
| `HoodBatt`         | size a larger (neighbourhood) battery; FCR on       |
| `HomeBattNoTariff` | same as HomeBatt but no power/peak tariff           |
| `HomeBattNoFCR`    | home battery, no frequency markets                  |
| `HomeBattFCRDonly` | home battery, FCR-D only                            |
| `HomeBattFCRNonly` | home battery, FCR-N only                            |
| `H2Tank`           | size a hydrogen storage tank (see caveat)           |
| `Electrolyser`     | size an electrolyser (see caveat)                   |

The frequency-market variants behave as expected: the net cost falls as more
products are offered (no FCR > FCR-D only > FCR-N only > both), because the
battery earns reserve revenue.

## Assumptions to review

These cases are for regression testing, not for drawing economic conclusions.
The numbers depend on assumptions set in `make_sizing_cases.py`:

- Horizon cut to one week; unit commitment relaxed to keep the LP reproducible.
- The FCR requirement is capped to 20 kW per product so home/neighbourhood-scale
  assets can meet it (the base case is sized for a much larger system).
- Investment costs (`FixedInvestmentCost`, `FixedChargeRate`) are illustrative.
- The neighbourhood battery is the home battery scaled to 50 kW / 100 kWh.

The hydrogen cases need two fixes applied by the generator to work at all:

1. The base-case hydrogen units start in 2040, after `EconomicBaseYear`, so they
   are inactive and the electricity-to-hydrogen set `e2h` is empty. The generator
   moves them into the base year.
2. The base-case hydrogen demand sits at `Node1`, but the electrolyser and tank
   are at `Node2` with no pipeline between them. The hydrogen balance is only
   built at nodes that have a local hydrogen asset, so a demand on an asset-less
   node is silently dropped and nothing is produced. The generator moves the
   demand onto the electrolyser's node.

With both, the hydrogen demand is served (120 kgH2 over the week) and **`H2Tank`
sizes the hydrogen tank** (it builds about half of it).

## Caveats

- **`Electrolyser`** solves and is reproducible but builds nothing, because the
  existing hydrogen storage already covers the small demand, so the candidate
  electrolyser is redundant. Forcing it to build by removing the existing storage
  makes the case infeasible: with no buffer and green-hydrogen matching (no
  production at night) a constant demand cannot be met hour by hour. Making this a
  real electrolyser-sizing study needs a base case without surplus existing
  hydrogen capacity and with storage or relaxed matching - a modelling choice.
- **Demand-only nodes**: the hydrogen (and electricity) balance is skipped at a
  node with no local generation, storage or line, which silently drops any demand
  there instead of forcing not-served energy. That is why fix 2 above is needed.
  It is a latent fragility in the formulation worth revisiting separately.
- **Power-tariff variant**: `HomeBattNoTariff` is reproducible but the cost
  difference versus `HomeBatt` should be reviewed before being interpreted.
- **Depth-of-discharge variants** are not generated yet: the model has no single
  switch for them, so that toggle needs the model author's input.
