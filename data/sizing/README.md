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

All cases are derived from `H2VPP`, cut to the first 168 load levels, with unit
commitment relaxed so the model is an LP and the cost is reproducible. The base
case only gives the first 24 load levels a nonzero `Duration`, so the solved
horizon is one day. Day-ahead market participation is on in every case.

| Case               | What it exercises                                   |
|--------------------|-----------------------------------------------------|
| `HomeBatt`         | size a home battery; FCR-D and FCR-N on             |
| `HoodBatt`         | size a larger (neighbourhood) battery; FCR on       |
| `HomeBattNoTariff` | same as HomeBatt but no power/peak tariff           |
| `HomeBattNoFCR`    | home battery, no frequency markets                  |
| `HomeBattFCRDonly` | home battery, FCR-D only                            |
| `HomeBattFCRNonly` | home battery, FCR-N only                            |
| `H2Tank`           | size a hydrogen tank against a day/night import     |
| `Electrolyser`     | size an electrolyser against the day import price   |

The frequency-market variants behave as expected: the net cost falls as more
products are offered (no FCR > FCR-D only > FCR-N only > both), because the
battery earns reserve revenue.

## Assumptions to review

These cases are for regression testing, not for drawing economic conclusions.
The numbers depend on assumptions set in `make_sizing_cases.py`:

- Horizon is one day (set by the base-case durations); unit commitment relaxed
  to keep the LP reproducible.
- The FCR requirement is capped to 20 kW per product so home/neighbourhood-scale
  assets can meet it (the base case is sized for a much larger system).
- Investment costs (`FixedInvestmentCost`, `FixedChargeRate`) are illustrative.
- The neighbourhood battery is the home battery scaled to 50 kW / 100 kWh.

The hydrogen cases rework the base data so a sound hydrogen system exists:

1. The base-case hydrogen units start in 2040, after `EconomicBaseYear`, so they
   are inactive and the electricity-to-hydrogen set `e2h` is empty. The generator
   moves them into the base year.
2. The base-case hydrogen demand sits at `Node1`, but the electrolyser and tank
   are at `Node2` with no pipeline between them. The generator moves the demand
   onto the electrolyser's node.
3. The hydrogen retailer is also moved to `Node2` and given a buy allowance, so
   hydrogen can be imported there at a price: cheap at night (40 per kg), expensive
   in the day (80 per kg). The electrolyser's own hydrogen costs about 53 per kg
   (retail electricity incl. fees and tax, plus O&M), in between the two.
4. The tank gets finite ratings (10 kgH2/h charge/discharge, the base data has
   900+) and starts empty with no minimum-inventory floor: the inventory floor and
   the initial fill do not scale with the build fraction, so a candidate tank was
   otherwise forced to be built just to satisfy its own floor.

With these, the 120 kgH2/day demand is fully served and both cases make real
investment decisions: **`H2Tank` builds the tank in full** (night-to-day arbitrage
pays for it many times over) and **`Electrolyser` builds a small fraction** (only
the day hours where producing beats importing). The build decisions are asserted
in `tests/test_run.py::test_h2_sizing_decisions`, because the investment-cost
share of the total cost is below the golden tolerance.

## Caveats

- **Green-hydrogen matching** is off in the two hydrogen cases: the base case's
  rooftop solar (~0.2 kW) cannot supply an electrolyser drawing kilowatts, so with
  matching on the electrolyser would simply never run.
- **Power-tariff variant**: `HomeBattNoTariff` is reproducible but the cost
  difference versus `HomeBatt` should be reviewed before being interpreted.
- **Depth-of-discharge variants** are not generated yet: the model has no single
  switch for them, so that toggle needs the model author's input.
