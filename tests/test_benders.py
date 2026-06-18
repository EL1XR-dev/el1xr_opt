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


def _have_gurobi():
    try:
        return bool(SolverFactory("gurobi").available(exception_flag=False))
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


# --- integer recourse: Lagrangian cut_mode (SDDiP-style) closes the integrality gap -------
#
# A two-stage problem with a binarised inter-stage STATE and an INTEGER recourse (a fixed
# commitment charge makes the recourse value non-convex). LP optimality cuts (relaxed
# subproblem) stall at the convex-envelope bound; Lagrangian cuts from the MILP subproblem,
# tight at the binary state, reach the integer monolith optimum. This guards the integer
# decomposition engine (the paper's solving contribution).
_A, _D2, _FC, _M = 3.0, 3.0, 5.0, 100.0
_W = {"b0": 1.0, "b1": 2.0}; _NM = ["b0", "b1"]; _BLK = [0]


def _lag_master():
    m = ConcreteModel()
    from pyomo.environ import Binary
    m.b = Var(_NM, within=Binary); m.th = Var(_BLK, bounds=(0, None)); m.s = Var(bounds=(0, 3))
    m.sdef = Constraint(expr=m.s == sum(_W[n] * m.b[n] for n in _NM))
    m.cuts = ConstraintList(); m.obj = Objective(expr=_A * m.s + sum(m.th[b] for b in _BLK))
    return {"model": m, "x": {n: m.b[n] for n in _NM}, "theta": {b: m.th[b] for b in _BLK}, "cuts": m.cuts}


def _lag_sub_factory(integer):
    from pyomo.environ import Binary, UnitInterval

    def _make(block):
        m = ConcreteModel()
        m.zc = Var(_NM, bounds=(0, 1)); m.u = Var(within=Binary if integer else UnitInterval)
        m.p = Var(within=NonNegativeReals); m.s = Var(bounds=(0, 3))
        m.bhat = Param(_NM, mutable=True, initialize=0.0)
        m.fixc = Constraint(_NM, rule=lambda mm, n: mm.zc[n] == mm.bhat[n])
        m.sdef = Constraint(expr=m.s == sum(_W[n] * m.zc[n] for n in _NM))
        m.dem = Constraint(expr=m.s + m.p >= _D2); m.cap = Constraint(expr=m.p <= _M * m.u)
        m.obj = Objective(expr=_FC * m.u + m.p, sense=minimize); m.dual = Suffix(direction=Suffix.IMPORT)

        def set_xhat(x_hat):
            for n in _NM:
                m.bhat[n] = x_hat[n]
        return {"model": m, "xcopy": {n: m.zc[n] for n in _NM},
                "fix": {n: m.fixc[n] for n in _NM}, "set_xhat": set_xhat, "obj": m.obj}
    return _make


def _lag_monolith():
    from pyomo.environ import Binary
    m = ConcreteModel(); m.b = Var(_NM, within=Binary); m.u = Var(within=Binary)
    m.p = Var(within=NonNegativeReals); m.s = Var(bounds=(0, 3))
    m.sdef = Constraint(expr=m.s == sum(_W[n] * m.b[n] for n in _NM))
    m.dem = Constraint(expr=m.s + m.p >= _D2); m.cap = Constraint(expr=m.p <= _M * m.u)
    m.obj = Objective(expr=_A * m.s + _FC * m.u + m.p)
    SolverFactory("gurobi").solve(m)
    return value(m.obj)


@pytest.mark.solve
@pytest.mark.skipif(not _have_gurobi(), reason="needs gurobi (integer recourse + duals)")
def test_lagrangian_cut_closes_integrality_gap():
    mono = _lag_monolith()
    cfg = BendersConfig(max_iterations=40, relative_gap=1e-6)
    cfg.extra["lag_steps"] = 60; cfg.extra["lag_step0"] = 4.0
    lp = benders_solve(_lag_master, _lag_sub_factory(False), _BLK, config=cfg,
                       solver="gurobi", cut_mode="lp")
    lg = benders_solve(_lag_master, _lag_sub_factory(True), _BLK, config=cfg,
                       solver="gurobi", cut_mode="lagrangian")
    # LP cuts are inexact: their lower bound stalls strictly below the integer optimum.
    assert mono - lp["lower_bound"] > 1e-2, \
        f"LP cuts unexpectedly tight: LB={lp['lower_bound']:.4f} vs monolith {mono:.4f}"
    # Lagrangian cuts on the binarised state reach the integer optimum.
    assert abs(lg["lower_bound"] - mono) < 1e-2, \
        f"lagrangian LB={lg['lower_bound']:.4f} did not reach monolith {mono:.4f}"


@pytest.mark.solve
@pytest.mark.skipif(not _have_highs(), reason="needs an LP/MILP solver")
def test_lp_fix_cut_runs_on_integer_recourse():
    """Fix-and-resolve LP cuts (``cut_mode='lp_fix'``) let the lp-style path RUN on an INTEGER
    subproblem that has no native duals: solve the block MILP, fix its discrete vars (relaxing
    their domain), and re-solve the continuous restriction to recover the x-fixing duals. The
    bound is inexact in general (``cut_mode='lagrangian'`` is the valid one); here we only
    require that it runs and returns a finite bound rather than erroring on the missing duals."""
    cfg = BendersConfig(max_iterations=30, relative_gap=1e-6)
    res = benders_solve(_lag_master, _lag_sub_factory(True), _BLK, config=cfg,
                        solver="appsi_highs", cut_mode="lp_fix")
    assert res["lower_bound"] is not None and abs(res["lower_bound"]) < 1e6, \
        f"lp_fix did not produce a finite bound: {res.get('lower_bound')}"
