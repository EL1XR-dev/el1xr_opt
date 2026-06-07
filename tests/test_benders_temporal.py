"""Stage D -- temporal (storage-boundary) Benders against the monolithic optimum.

Temporal block splitting decomposes one operating horizon into contiguous time
blocks. Unlike scenarios, the blocks are coupled *sequentially*: the storage
inventory carried across a block boundary links block t to block t+1. The standard
way to decompose this is to put the boundary inventory levels in the master (they
are the complicating / linking variables, just like investment in the scenario
split) and give each block its incoming and outgoing boundary levels as fixed
values; the duals of those fixing constraints are the cuts. This test shows the
generic ``benders_solve`` already handles that -- a temporal subproblem simply
depends on two complicating variables (its two boundary states) instead of all of
them -- by reproducing the monolithic optimum on a small multistage storage
problem.

The model: T stages, each meeting a demand from a generator (cost) or
energy-not-served (penalty), with one storage whose level s_t evolves as
s_t = s_{t-1} + eff*charge_t - discharge_t/eff. The storage is cyclic
(s_0 = s_T = s_init), so the free boundary states are s_1..s_{T-1}.

Needs an LP solver (HiGHS via appsi); skipped if unavailable.
"""
import pytest

from pyomo.environ import (ConcreteModel, Var, Param, Constraint, ConstraintList,
                           Objective, NonNegativeReals, Reals, Suffix, minimize, value,
                           SolverFactory)

from el1xr_opt.Modules.oM_Decomposition import benders_solve, BendersConfig

# data: 4 stages, one storage
T = 4
STAGES = list(range(1, T + 1))
BOUNDARIES = list(range(1, T))                 # free boundary states s_1..s_{T-1}
DEMAND = {1: 30.0, 2: 70.0, 3: 40.0, 4: 60.0}
GEN_COST = 5.0
ENS_COST = 500.0
SMAX = 50.0
EFF = 0.9
S_INIT = 20.0                                  # s_0 = s_T (cyclic)


def _have_highs():
    try:
        return bool(SolverFactory("appsi_highs").available(exception_flag=False))
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _have_highs(), reason="needs an LP solver (HiGHS)")


def _s_of(m, t):
    """Boundary level at the end of stage t: s_0=s_T=S_INIT fixed, else a Var."""
    if t == 0 or t == T:
        return S_INIT
    return m.s[t]


def _solve_monolithic():
    m = ConcreteModel()
    m.s = Var(BOUNDARIES, within=NonNegativeReals, bounds=(0, SMAX))
    m.gen = Var(STAGES, within=NonNegativeReals)
    m.ens = Var(STAGES, within=NonNegativeReals)
    m.ch = Var(STAGES, within=NonNegativeReals)
    m.dis = Var(STAGES, within=NonNegativeReals)
    m.bal = Constraint(STAGES, rule=lambda mm, t:
                       mm.gen[t] + mm.dis[t] - mm.ch[t] + mm.ens[t] >= DEMAND[t])
    m.sbal = Constraint(STAGES, rule=lambda mm, t:
                        _s_of(mm, t) == _s_of(mm, t - 1) + EFF * mm.ch[t] - mm.dis[t] / EFF)
    m.obj = Objective(expr=sum(GEN_COST * m.gen[t] + ENS_COST * m.ens[t] for t in STAGES),
                      sense=minimize)
    SolverFactory("appsi_highs").solve(m)
    return float(value(m.obj)), {t: float(value(m.s[t])) for t in BOUNDARIES}


def _make_master():
    m = ConcreteModel()
    # initialise the boundary states: until cuts arrive they appear in no
    # constraint and the solver would leave them unvalued (they carry no master
    # cost, unlike investment in the scenario split).
    m.s = Var(BOUNDARIES, within=NonNegativeReals, bounds=(0, SMAX), initialize=S_INIT)
    m.theta = Var(STAGES, within=Reals, bounds=(-1e7, 1e9), initialize=0.0)
    m.cuts = ConstraintList()
    m.obj = Objective(expr=sum(m.theta[t] for t in STAGES), sense=minimize)
    return {"model": m, "x": {t: m.s[t] for t in BOUNDARIES},
            "theta": {t: m.theta[t] for t in STAGES}, "cuts": m.cuts}


def _make_subproblem(stage):
    t = stage
    m = ConcreteModel()
    m.dual = Suffix(direction=Suffix.IMPORT)
    # a free copy of every boundary state, each fixed to the master value; only the
    # two this stage touches enter its constraints, the rest have zero dual.
    m.scopy = Var(BOUNDARIES, within=Reals)
    m.xhat = Param(BOUNDARIES, mutable=True, initialize=0.0)
    m.fix = Constraint(BOUNDARIES, rule=lambda mm, b: mm.scopy[b] == mm.xhat[b])

    def s_in(mm):
        return S_INIT if t - 1 == 0 else mm.scopy[t - 1]

    def s_out(mm):
        return S_INIT if t == T else mm.scopy[t]

    m.gen = Var(within=NonNegativeReals)
    m.ens = Var(within=NonNegativeReals)
    m.ch = Var(within=NonNegativeReals)
    m.dis = Var(within=NonNegativeReals)
    m.bal = Constraint(expr=m.gen + m.dis - m.ch + m.ens >= DEMAND[t])
    m.sbal = Constraint(expr=s_out(m) == s_in(m) + EFF * m.ch - m.dis / EFF)
    m.obj = Objective(expr=GEN_COST * m.gen + ENS_COST * m.ens, sense=minimize)

    def set_xhat(x_hat):
        for b in BOUNDARIES:
            m.xhat[b] = x_hat[b]

    return {"model": m, "xcopy": {b: m.scopy[b] for b in BOUNDARIES},
            "fix": {b: m.fix[b] for b in BOUNDARIES}, "set_xhat": set_xhat, "obj": m.obj}


@pytest.mark.solve
def test_temporal_benders_matches_monolithic():
    mono_obj, _ = _solve_monolithic()
    res = benders_solve(_make_master, _make_subproblem, STAGES,
                        config=BendersConfig(max_iterations=100, relative_gap=1e-7))
    assert res["converged"], f"did not converge: gap={res['gap']:.2e}"
    assert abs(res["objective"] - mono_obj) / abs(mono_obj) < 1e-5, \
        f"temporal benders {res['objective']:.4f} vs monolithic {mono_obj:.4f}"
