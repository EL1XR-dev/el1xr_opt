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

from el1xr_opt.Modules.oM_HeatSector import (create_heat_sector, heat_electricity_load,
                                            heat_to_power_output)

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


@pytest.mark.solve
def test_heat_to_power_closes_the_loop():
    """A heat-to-power unit (ORC/CHP) consumes heat and makes electricity -- the
    analogue of the hydrogen fuel cell. Here a cheap boiler makes heat, the
    heat-to-power unit turns it into electricity to meet an electricity demand
    (the grid is expensive), so the power<->heat loop is exercised in the
    heat->power direction."""
    m = ConcreteModel()
    m.n = Set(initialize=LEVELS, ordered=True)
    m.htd = ["HD"]
    m.htg = ["BOIL"]
    m.htp = []                                       # no heat pump here
    m.htw = ["ORC"]                                  # heat-to-power unit
    m.hts = []
    m.n2htd = [("H", "HD")]
    m.n2htg = [("H", "BOIL")]
    m.n2hts = []
    m.n2htw = [("H", "ORC")]
    eff = 0.4
    elec_dem = {"t1": 6.0, "t2": 8.0, "t3": 5.0}
    m.Par = {
        "pHeatDemand":       {"HD": {"t1": 3.0, "t2": 4.0, "t3": 2.0}},
        "pHeatGenMaxPower":   {"BOIL": 100.0},
        "pHeatGenCost":       {"BOIL": 1.0},          # cheap heat
        "pHeatPumpCOP":       {},
        "pHeatToEleMaxHeat":  {"ORC": 80.0},
        "pHeatToEleEff":      {"ORC": eff},
        "pHeatStoMax":        {}, "pHeatStoEff": {}, "pHeatStoInitial": {},
        "pHeatNSCost":        1000.0,
        "pDuration":          {n: 1.0 for n in LEVELS},
    }
    create_heat_sector(m, m)
    # electricity side: meet a demand from the heat-to-power unit or an expensive grid
    m.vGrid = Var(m.n, within=NonNegativeReals)
    m.eElec = Constraint(m.n, rule=lambda mm, n:
                         heat_to_power_output(mm, ["ORC"], n) + mm.vGrid[n] == elec_dem[n])
    m.obj = Objective(expr=m.HeatOperatingCost + sum(50.0 * m.vGrid[n] for n in m.n),
                      sense=minimize)
    SolverFactory("appsi_highs").solve(m)

    for n in LEVELS:
        # heat-to-power coupling: electricity = efficiency x heat consumed
        assert abs(value(m.vHeatToEle["ORC", n]) - eff * value(m.vHeatConsumed["ORC", n])) < 1e-6
        # heat balance: boiler == heat demand + heat consumed by the ORC
        assert abs(value(m.vHeatOutput["BOIL", n])
                   - (m.Par["pHeatDemand"]["HD"][n] + value(m.vHeatConsumed["ORC", n]))) < 1e-5
        # electricity demand met, and the ORC (not the expensive grid) supplies it
        assert abs(value(m.vHeatToEle["ORC", n]) + value(m.vGrid[n]) - elec_dem[n]) < 1e-6
    assert sum(value(m.vHeatToEle["ORC", n]) for n in LEVELS) > 1e-3
    assert sum(value(m.vGrid[n]) for n in LEVELS) < 1e-5      # grid too expensive
