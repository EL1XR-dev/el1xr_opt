"""Stage 6 (heat) -- the nodal home-heat sector, coupled to electricity.

Builds a small home: a heat demand met by an electric heat pump (COP), a gas
boiler and a thermal store, with the heat pump's electricity drawn from a grid
supply. Checks the formulation: the nodal heat balance holds, the heat-pump COP
ties heat to electricity, the thermal store conserves energy, demand is served,
and the cheaper heat pump is preferred over the boiler. This exercises
``create_heat_sector`` directly (the CSV input pipeline that would populate the
heat sets is the remaining wiring).

Needs an LP solver (HiGHS via appsi); skipped otherwise.
"""
import pytest

from pyomo.environ import (ConcreteModel, Set, Var, Constraint, Objective,
                           NonNegativeReals, minimize, value, SolverFactory)

from el1xr_opt.Modules.oM_HeatSector import create_heat_sector, heat_electricity_load

LEVELS = ["t1", "t2", "t3"]
DEMAND = {"t1": 10.0, "t2": 22.0, "t3": 15.0}
COP = 3.0
ELEC_PRICE = 1.0
BOILER_COST = 8.0


def _have_highs():
    try:
        return bool(SolverFactory("appsi_highs").available(exception_flag=False))
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _have_highs(), reason="needs an LP solver (HiGHS)")


def _build():
    m = ConcreteModel()
    m.n = Set(initialize=LEVELS, ordered=True)
    m.htd = ["HD"]
    m.htg = ["HP", "BOIL"]
    m.htp = ["HP"]                                   # the heat pump
    m.hts = ["TS"]
    m.n2htd = [("H", "HD")]
    m.n2htg = [("H", "HP"), ("H", "BOIL")]
    m.n2hts = [("H", "TS")]
    m.Par = {
        "pHeatDemand":     {"HD": dict(DEMAND)},
        "pHeatGenMaxPower": {"HP": 30.0, "BOIL": 50.0},
        "pHeatGenCost":     {"HP": 0.0, "BOIL": BOILER_COST},  # HP fuel free (elec costed below)
        "pHeatPumpCOP":     {"HP": COP},
        "pHeatStoMax":      {"TS": 20.0},
        "pHeatStoEff":      {"TS": 0.95},
        "pHeatStoInitial":  {"TS": 5.0},
        "pHeatNSCost":      1000.0,
        "pDuration":        {n: 1.0 for n in LEVELS},
    }
    create_heat_sector(m, m)
    # electricity side: a grid supply that covers the heat-pump load
    m.vGrid = Var(m.n, within=NonNegativeReals)
    m.eElec = Constraint(m.n, rule=lambda mm, n: mm.vGrid[n] == heat_electricity_load(mm, ["HP"], n))
    m.obj = Objective(expr=m.HeatOperatingCost + sum(ELEC_PRICE * m.vGrid[n] for n in m.n),
                      sense=minimize)
    return m


@pytest.mark.solve
def test_heat_sector_solves_and_balances():
    m = _build()
    SolverFactory("appsi_highs").solve(m)

    # nodal heat balance holds at every level
    for n in LEVELS:
        supply = (value(m.vHeatOutput["HP", n]) + value(m.vHeatOutput["BOIL", n])
                  + value(m.vHeatDischarge["TS", n]) - value(m.vHeatCharge["TS", n])
                  + value(m.vHeatNotServed["HD", n]))
        assert abs(supply - DEMAND[n]) < 1e-5, f"heat balance off at {n}: {supply} vs {DEMAND[n]}"

    # heat-pump COP couples heat to electricity, and the grid supplies it
    for n in LEVELS:
        assert abs(value(m.vHeatOutput["HP", n]) - COP * value(m.vHeatPumpElec["HP", n])) < 1e-6
        assert abs(value(m.vGrid[n]) - value(m.vHeatPumpElec["HP", n])) < 1e-6

    # thermal store conserves energy: inv = prev + eff*charge - discharge
    prev = m.Par["pHeatStoInitial"]["TS"]
    eff = m.Par["pHeatStoEff"]["TS"]
    for n in LEVELS:
        inv = value(m.vHeatInventory["TS", n])
        assert abs(inv - (prev + eff * value(m.vHeatCharge["TS", n])
                          - value(m.vHeatDischarge["TS", n]))) < 1e-5
        prev = inv

    # demand is served (ample capacity -> no heat-not-served)
    assert sum(value(m.vHeatNotServed["HD", n]) for n in LEVELS) < 1e-5
    # the heat pump (1/COP per heat) is cheaper than the boiler, so it is used
    assert sum(value(m.vHeatPumpElec["HP", n]) for n in LEVELS) > 1e-3


@pytest.mark.solve
def test_heat_sector_noop_without_heat_sets():
    # a model with no heat sets is returned unchanged (the four golden cases path)
    m = ConcreteModel()
    m.n = Set(initialize=LEVELS, ordered=True)
    m.Par = {}
    out = create_heat_sector(m, m)
    assert out is m
    assert not hasattr(m, "eHeatBalance")
