"""Stage 6 (heat) -- the nodal home-heat sector, coupled to electricity.

Builds a small home over a single (period, scenario): a heat demand met by an
electric heat pump (COP), a gas boiler and a thermal store, with the heat pump's
electricity drawn from a grid supply. Checks the formulation: the nodal heat
balance holds, the heat-pump COP ties heat to electricity, the thermal store
conserves energy, demand is served, the cheaper heat pump is preferred over the
boiler, and a heat-to-power unit closes the power-heat loop. All quantities are
indexed by (period, scenario, load level), like the electricity sector.

Needs an LP solver (HiGHS via appsi); skipped otherwise.
"""
import pytest

from pyomo.environ import (ConcreteModel, Set, Var, Constraint, Objective,
                           NonNegativeReals, minimize, value, SolverFactory)

from el1xr_opt.Modules.oM_HeatSector import (create_heat_sector, heat_electricity_load,
                                            heat_to_power_output)

P, S = "P", "S"                                  # one period, one scenario
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


def _psn(d):
    """Lift an n-keyed dict to a (period, scenario, n)-keyed one."""
    return {(P, S, n): v for n, v in d.items()}


def _build():
    m = ConcreteModel()
    m.n = Set(initialize=LEVELS, ordered=True)
    m.ps = [(P, S)]
    m.htd = ["HD"]
    m.htg = ["HP", "BOIL"]
    m.htp = ["HP"]                                   # the heat pump
    m.hts = ["TS"]
    m.n2htd = [("H", "HD")]
    m.n2htg = [("H", "HP"), ("H", "BOIL")]
    m.n2hts = [("H", "TS")]
    m.Par = {
        "pHeatDemand":     {"HD": _psn(DEMAND)},
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
    m.vGrid = Var(m.n, within=NonNegativeReals)
    m.eElec = Constraint(m.n, rule=lambda mm, n:
                         mm.vGrid[n] == heat_electricity_load(mm, ["HP"], P, S, n))
    m.obj = Objective(expr=m.HeatOperatingCost + sum(ELEC_PRICE * m.vGrid[n] for n in m.n),
                      sense=minimize)
    return m


@pytest.mark.solve
def test_heat_sector_solves_and_balances():
    m = _build()
    SolverFactory("appsi_highs").solve(m)
    for n in LEVELS:
        supply = (value(m.vHeatOutput[P, S, n, "HP"]) + value(m.vHeatOutput[P, S, n, "BOIL"])
                  + value(m.vHeatDischarge[P, S, n, "TS"]) - value(m.vHeatCharge[P, S, n, "TS"])
                  + value(m.vHeatNotServed[P, S, n, "HD"]))
        assert abs(supply - DEMAND[n]) < 1e-5, f"heat balance off at {n}: {supply} vs {DEMAND[n]}"
        assert abs(value(m.vHeatOutput[P, S, n, "HP"])
                   - COP * value(m.vHeatPumpElec[P, S, n, "HP"])) < 1e-6
        assert abs(value(m.vGrid[n]) - value(m.vHeatPumpElec[P, S, n, "HP"])) < 1e-6

    prev = m.Par["pHeatStoInitial"]["TS"]
    eff = m.Par["pHeatStoEff"]["TS"]
    for n in LEVELS:
        inv = value(m.vHeatInventory[P, S, n, "TS"])
        assert abs(inv - (prev + eff * value(m.vHeatCharge[P, S, n, "TS"])
                          - value(m.vHeatDischarge[P, S, n, "TS"]))) < 1e-5
        prev = inv

    assert sum(value(m.vHeatNotServed[P, S, n, "HD"]) for n in LEVELS) < 1e-5
    assert sum(value(m.vHeatPumpElec[P, S, n, "HP"]) for n in LEVELS) > 1e-3


@pytest.mark.solve
def test_heat_sector_noop_without_heat_sets():
    m = ConcreteModel()
    m.n = Set(initialize=LEVELS, ordered=True)
    m.ps = [(P, S)]
    m.Par = {}
    out = create_heat_sector(m, m)
    assert out is m
    assert not hasattr(m, "eHeatBalance")


@pytest.mark.solve
def test_heat_to_power_closes_the_loop():
    """A heat-to-power unit (ORC/CHP) consumes heat and makes electricity -- the
    analogue of the hydrogen fuel cell. A cheap boiler makes heat, the unit turns
    it into electricity to meet an electricity demand (the grid is expensive), so
    the power<->heat loop runs in the heat->power direction."""
    m = ConcreteModel()
    m.n = Set(initialize=LEVELS, ordered=True)
    m.ps = [(P, S)]
    m.htd = ["HD"]
    m.htg = ["BOIL"]
    m.htp = []
    m.htw = ["ORC"]
    m.hts = []
    m.n2htd = [("H", "HD")]
    m.n2htg = [("H", "BOIL")]
    m.n2hts = []
    m.n2htw = [("H", "ORC")]
    eff = 0.4
    elec_dem = {"t1": 6.0, "t2": 8.0, "t3": 5.0}
    m.Par = {
        "pHeatDemand":       {"HD": _psn({"t1": 3.0, "t2": 4.0, "t3": 2.0})},
        "pHeatGenMaxPower":   {"BOIL": 100.0},
        "pHeatGenCost":       {"BOIL": 1.0},
        "pHeatPumpCOP":       {},
        "pHeatToEleMaxHeat":  {"ORC": 80.0},
        "pHeatToEleEff":      {"ORC": eff},
        "pHeatStoMax":        {}, "pHeatStoEff": {}, "pHeatStoInitial": {},
        "pHeatNSCost":        1000.0,
        "pDuration":          {n: 1.0 for n in LEVELS},
    }
    create_heat_sector(m, m)
    m.vGrid = Var(m.n, within=NonNegativeReals)
    m.eElec = Constraint(m.n, rule=lambda mm, n:
                         heat_to_power_output(mm, ["ORC"], P, S, n) + mm.vGrid[n] == elec_dem[n])
    m.obj = Objective(expr=m.HeatOperatingCost + sum(50.0 * m.vGrid[n] for n in m.n),
                      sense=minimize)
    SolverFactory("appsi_highs").solve(m)

    for n in LEVELS:
        assert abs(value(m.vHeatToEle[P, S, n, "ORC"])
                   - eff * value(m.vHeatConsumed[P, S, n, "ORC"])) < 1e-6
        assert abs(value(m.vHeatOutput[P, S, n, "BOIL"])
                   - (m.Par["pHeatDemand"]["HD"][(P, S, n)]
                      + value(m.vHeatConsumed[P, S, n, "ORC"]))) < 1e-5
        assert abs(value(m.vHeatToEle[P, S, n, "ORC"]) + value(m.vGrid[n]) - elec_dem[n]) < 1e-6
    assert sum(value(m.vHeatToEle[P, S, n, "ORC"]) for n in LEVELS) > 1e-3
    assert sum(value(m.vGrid[n]) for n in LEVELS) < 1e-5


@pytest.mark.solve
def test_heat_case_runs_through_build_model():
    """End-to-end via the CSV pipeline: a real case carrying heat tables is read by
    load_heat_data, built by create_heat_sector, and coupled into the electricity
    balance and objective -- it builds and solves with the heat demand met by a
    heat pump whose electricity is drawn from the electricity node."""
    import os
    import sys
    import datetime
    import tempfile
    import pandas as pd
    sys.path.insert(0, os.path.dirname(__file__))
    import _make_2scenario as gen
    from el1xr_opt.Modules.oM_Sequence import build_model

    trunc = 6
    work = tempfile.mkdtemp(prefix="heatcase_")
    gen.build(work, n_scenarios=1, trunc=trunc)
    case_dir = os.path.join(work, "Home1")

    def hpath(stem):
        return os.path.join(case_dir, f"oM_Data_{stem}_Home1.csv")

    # heat generation: a heat pump and a boiler at the electricity node (Node1)
    g = pd.DataFrame(
        {"Node": ["Node1", "Node1"], "Type": ["HeatPump", "Boiler"],
         "MaximumPower": [1000.0, 1000.0], "Cost": [0.0, 9.0], "COP": [3.0, 0.0],
         "Efficiency": [0.0, 0.0], "MaxStorage": [0.0, 0.0], "StoEff": [0.0, 0.0],
         "InitialStorage": [0.0, 0.0]},
        index=["HP1", "BOIL1"])
    g.to_csv(hpath("HeatGeneration"))
    pd.DataFrame({"Node": ["Node1"]}, index=["HD1"]).to_csv(hpath("HeatDemand"))
    levels = [f"t{i + 1:04d}" for i in range(trunc)]
    idx = pd.MultiIndex.from_tuples([("period1", "sc01", t) for t in levels])
    pd.DataFrame({"HD1": [5.0 + 2.0 * (i % 3) for i in range(trunc)]}, index=idx).to_csv(
        hpath("VarMaxHeatDemand"))

    date = datetime.datetime.now().replace(second=0, microsecond=0)
    m = build_model(work, "Home1", date)
    # the heat sector was built from the CSVs
    assert list(m.htd) == ["HD1"] and "HP1" in list(m.htp) and "BOIL1" in list(m.htg)
    assert hasattr(m, "eHeatBalance") and hasattr(m, "HeatOperatingCost")

    solver = SolverFactory("gurobi") if SolverFactory("gurobi").available(exception_flag=False) \
        else SolverFactory("appsi_highs")
    res = solver.solve(m, load_solutions=False)
    assert str(res.solver.termination_condition) == "optimal"
    m.solutions.load_from(res)

    p, sc = list(m.ps)[0]
    # heat demand is met (heat-not-served is ~0) and the heat pump runs
    total_demand = sum(5.0 + 2.0 * (i % 3) for i in range(trunc))
    served = sum(value(m.vHeatOutput[p, sc, n, g]) for n in m.n for g in ["HP1", "BOIL1"])
    hns = sum(value(m.vHeatNotServed[p, sc, n, "HD1"]) for n in m.n)
    assert hns < 1e-4 and abs(served - total_demand) < 1e-3
    # the heat pump drew electricity (the cross-sector coupling fired)
    assert sum(value(m.vHeatPumpElec[p, sc, n, "HP1"]) for n in m.n) > 1e-3
