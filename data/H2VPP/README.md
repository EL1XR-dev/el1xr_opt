# H2VPP — small hydrogen-VPP test case

A trimmed version of the EEM26 `Home1` microgrid, used to solve-test the
investment (capacity-sizing) layer (`oM_Investment.py`) and the green-hydrogen
layer (`oM_GreenHydrogen.py`). It solves in about one second.

## How it differs from EEM26/Home1

- **24 active load levels** instead of 8736. The other load levels are switched
  off by setting their `Duration` to 0 (the model keeps only load levels with a
  positive duration), so no time-series file had to be shortened.
- **Investment candidates**: `Solar_01` and `BESS_01` are given a fixed
  investment cost, so they become build candidates. The model chooses a build
  fraction in [0, 1] for each.
- **Electricity PPA**: `Solar_02` is activated at the base year and flagged
  `PPA=1` with a `PPAPrice`, so the take-as-produced PPA cost is defined.
- **Green-hydrogen matching**: the `GreenH2Matching` option is on. In this case
  there is no electrolyser active at the base year, so the matching constraint is
  skipped (the model logs this). To exercise matching, activate an electrolyser
  (a hydrogen generator with a positive `ProductionFunction`) and a hydrogen
  demand at the base year — see the note below.

## Run it

```
python -c "import datetime; from el1xr_opt.Modules.oM_Sequence import routine; \
routine('data/H2VPP','Home1','gurobi',datetime.datetime(2023,1,1,1,0,0),'False','False','False')"
```

Expected: optimal solution, total cost about 354 SEK, `Solar_01` and `BESS_01`
built, a positive PPA cost during daytime hours.

## To extend matching into a binding test

Activate the electrolyser supply chain at the base year (2025): set the
electrolyser's and a hydrogen demand's `InitialPeriod` to 2020, give the demand a
profile, and make sure the electrolyser's storage/energy-type fields are
consistent. Then the electrolyser must consume electricity to make hydrogen, and
the hourly matching constraint caps that consumption by the available renewable
generation.
