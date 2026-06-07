"""Stage D — validate the generic Benders solver against the monolithic optimum.

A small two-stage stochastic capacity-expansion problem with the same structure as
el1xr (first stage: build capacity at a per-unit cost; second stage, per scenario:
dispatch the built capacity to meet demand, paying generation cost and a high
energy-not-served penalty for any shortfall). Solving it monolithically (the
deterministic-equivalent LP) and by Benders must give the same optimum.

Needs an LP solver (HiGHS via appsi); skipped if unavailable.
"""
import pytest

from pyomo.environ import (ConcreteModel, Var, Param, Constraint, ConstraintList,
                           Objective, NonNegativeReals, Suffix, minimize, value, SolverFactory)

from el1xr_opt.Modules.oM_Decomposition import benders_solve, BendersConfig

# problem data: 2 generators, 3 demand scenarios
INV = {"g1": 10.0, "g2": 7.0}          # per-unit capacity build cost
GEN = {"g1": 2.0, "g2": 4.0}           # per-unit dispatch cost
ENS_COST = 1000.0                       # energy-not-served penalty
SCEN = {"low": (0.3, 30.0), "mid": (0.4, 55.0), "high": (0.3, 80.0)}  # prob, demand
GENS = list(INV)


def _have_highs():
    try:
        return bool(SolverFactory("appsi_highs").available(exception_flag=False))
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _have_highs(), reason="needs an LP solver (HiGHS)")


def _solve_monolithic():
    m = ConcreteModel()
    m.cap = Var(GENS, within=NonNegativeReals)
    idx = [(g, s) for g in GENS for s in SCEN]
    m.gen = Var(idx, within=NonNegativeReals)
    m.ens = Var(list(SCEN), within=NonNegativeReals)
    m.captrack = Constraint(idx, rule=lambda mm, g, s: mm.gen[g, s] <= mm.cap[g])
    m.bal = Constraint(list(SCEN),
                       rule=lambda mm, s: sum(mm.gen[g, s] for g in GENS) + mm.ens[s] >= SCEN[s][1])
    m.obj = Objective(expr=sum(INV[g] * m.cap[g] for g in GENS)
                      + sum(SCEN[s][0] * (sum(GEN[g] * m.gen[g, s] for g in GENS) + ENS_COST * m.ens[s])
                            for s in SCEN), sense=minimize)
    SolverFactory("appsi_highs").solve(m)
    return float(value(m.obj)), {g: float(value(m.cap[g])) for g in GENS}


def _make_master():
    m = ConcreteModel()
    m.cap = Var(GENS, within=NonNegativeReals)
    m.theta = Var(list(SCEN), within=NonNegativeReals)   # >= 0: recourse cost is nonneg
    m.cuts = ConstraintList()
    m.obj = Objective(expr=sum(INV[g] * m.cap[g] for g in GENS) + sum(m.theta[s] for s in SCEN),
                      sense=minimize)
    return {"model": m, "x": {g: m.cap[g] for g in GENS}, "theta": {s: m.theta[s] for s in SCEN},
            "cuts": m.cuts}


def _make_subproblem(scenario):
    prob, demand = SCEN[scenario]
    m = ConcreteModel()
    m.dual = Suffix(direction=Suffix.IMPORT)
    m.capcopy = Var(GENS, within=NonNegativeReals)        # free copy of first-stage
    m.xhat = Param(GENS, mutable=True, initialize=0.0)
    m.fix = Constraint(GENS, rule=lambda mm, g: mm.capcopy[g] == mm.xhat[g])
    m.gen = Var(GENS, within=NonNegativeReals)
    m.ens = Var(within=NonNegativeReals)
    m.captrack = Constraint(GENS, rule=lambda mm, g: mm.gen[g] <= mm.capcopy[g])
    m.bal = Constraint(expr=sum(m.gen[g] for g in GENS) + m.ens >= demand)
    m.obj = Objective(expr=prob * (sum(GEN[g] * m.gen[g] for g in GENS) + ENS_COST * m.ens),
                      sense=minimize)

    def set_xhat(x_hat):
        for g in GENS:
            m.xhat[g] = x_hat[g]

    return {"model": m, "xcopy": {g: m.capcopy[g] for g in GENS},
            "fix": {g: m.fix[g] for g in GENS}, "set_xhat": set_xhat, "obj": m.obj}


@pytest.mark.solve
def test_benders_matches_monolithic():
    mono_obj, mono_cap = _solve_monolithic()
    res = benders_solve(_make_master, _make_subproblem, list(SCEN),
                        config=BendersConfig(max_iterations=50, relative_gap=1e-7))
    assert res["converged"], f"did not converge: gap={res['gap']:.2e}"
    assert abs(res["objective"] - mono_obj) / abs(mono_obj) < 1e-5, \
        f"benders {res['objective']:.4f} vs monolithic {mono_obj:.4f}"
    for g in GENS:
        assert abs(res["x"][g] - mono_cap[g]) < 1e-3, f"cap[{g}] {res['x'][g]} vs {mono_cap[g]}"
