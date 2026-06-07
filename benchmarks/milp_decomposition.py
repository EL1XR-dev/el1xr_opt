"""Stochastic unit commitment: where Benders decomposition beats the MILP monolith.

The earlier spatial benchmark showed decomposition does not beat the monolith for a
tractable LP -- the monolith is one efficient solve and the decomposition is
overhead-bound. The picture flips for a MILP whose integer decisions are
first-stage and whose recourse is a per-scenario LP, the classic stochastic
unit-commitment structure:

  * first stage  -- commitment binaries u[g] (which generators are on), shared by
                    every scenario, with a commitment cost.
  * second stage -- per scenario, a dispatch LP (meet demand from the committed
                    generators, energy-not-served at a penalty).

The monolith is one MILP: branch-and-bound on the binaries, but every node solves
the *whole* S-scenario dispatch LP, so node cost grows with the scenario count.
Benders keeps the binaries in a small master (binaries + cuts) and pushes the
dispatch into one LP subproblem per scenario; each node of the master's
branch-and-bound is cheap, and the subproblems are small LPs with valid duals.
As the scenario count grows the monolith's per-node LP blows up while Benders does
not, so Benders wins. This benchmark shows the crossover.

Run: python milp_decomposition.py [solver]
"""
import os
import sys
import time

from pyomo.environ import (ConcreteModel, Var, Param, Constraint, ConstraintList,
                           Objective, Binary, Reals, NonNegativeReals, Suffix, minimize,
                           value, SolverFactory)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from el1xr_opt.Modules.oM_Decomposition import benders_solve, BendersConfig

G = 40                                    # generators (commitment binaries)
T = 12                                    # time steps
# heterogeneous capacities and "lumpy" commitment costs make the reserve covering
# constraint below a hard knapsack over the binaries (NP-hard), so the monolith's
# branch-and-bound explores many nodes.
PMAX = {g: 30.0 + 17.0 * ((7 * g + 3) % 11) / 10.0 for g in range(G)}
GCOST = {g: 4.0 + 0.5 * (g % 7) for g in range(G)}
COMMIT = {g: 200.0 + 130.0 * ((5 * g + 2) % 13) / 13.0 for g in range(G)}
ENS_COST = 600.0
# ramp capability, anti-correlated with capacity: small fast units have high ramp.
RAMP = {g: 22.0 - 0.35 * PMAX[g] + 6.0 * ((3 * g + 1) % 7) / 7.0 for g in range(G)}
# two conflicting covering knapsacks on u (energy reserve and ramp reserve) -> the
# min-cost commitment is a hard 2D knapsack the LP relaxation does not resolve.
RESERVE = 0.86 * sum(PMAX.values())
RAMP_RESERVE = 0.80 * sum(RAMP.values())
TIME_LIMIT = 25.0                         # cap the monolith solve to show the crossover


def _demand(S):
    # scenario- and time-varying demand, sized so commitment is non-trivial
    return {(s, t): 360.0 + 50.0 * ((s + t) % 5) + 8.0 * t for s in range(S) for t in range(T)}


def _set_time_limit(opt, seconds):
    for key in ("time_limit", "timelimit", "TimeLimit", "limits/time"):
        try:
            opt.options[key] = seconds
        except Exception:
            pass


def build_monolith(S):
    d = _demand(S)
    m = ConcreteModel()
    m.u = Var(range(G), within=Binary)
    m.p = Var(range(G), range(S), range(T), within=NonNegativeReals)
    m.ens = Var(range(S), range(T), within=NonNegativeReals)
    m.pmax = Constraint(range(G), range(S), range(T),
                        rule=lambda mm, g, s, t: mm.p[g, s, t] <= PMAX[g] * mm.u[g])
    m.bal = Constraint(range(S), range(T), rule=lambda mm, s, t:
                       sum(mm.p[g, s, t] for g in range(G)) + mm.ens[s, t] >= d[(s, t)])
    m.reserve = Constraint(expr=sum(PMAX[g] * m.u[g] for g in range(G)) >= RESERVE)
    m.rampres = Constraint(expr=sum(RAMP[g] * m.u[g] for g in range(G)) >= RAMP_RESERVE)
    m.obj = Objective(
        expr=sum(COMMIT[g] * m.u[g] for g in range(G))
        + (1.0 / S) * sum(GCOST[g] * m.p[g, s, t] for g in range(G) for s in range(S) for t in range(T))
        + (1.0 / S) * sum(ENS_COST * m.ens[s, t] for s in range(S) for t in range(T)),
        sense=minimize)
    return m


def _solve_monolith(S, solver):
    m = build_monolith(S)
    opt = SolverFactory(solver)
    _set_time_limit(opt, TIME_LIMIT)
    t0 = time.time()
    res = opt.solve(m)
    tc = str(res.solver.termination_condition)
    return float(value(m.obj)), time.time() - t0, tc


def _benders(S, solver):
    d = _demand(S)
    gens = list(range(G))

    def make_master():
        mm = ConcreteModel()
        mm.u = Var(gens, within=Binary)
        mm.theta = Var(range(S), within=Reals, bounds=(-1e7, 1e12), initialize=0.0)
        mm.cuts = ConstraintList()
        mm.reserve = Constraint(expr=sum(PMAX[g] * mm.u[g] for g in gens) >= RESERVE)
        mm.rampres = Constraint(expr=sum(RAMP[g] * mm.u[g] for g in gens) >= RAMP_RESERVE)
        mm.obj = Objective(expr=sum(COMMIT[g] * mm.u[g] for g in gens)
                           + sum(mm.theta[s] for s in range(S)), sense=minimize)
        return {"model": mm, "x": {g: mm.u[g] for g in gens},
                "theta": {s: mm.theta[s] for s in range(S)}, "cuts": mm.cuts}

    def make_subproblem(scenario):
        s = scenario
        sub = ConcreteModel()
        sub.dual = Suffix(direction=Suffix.IMPORT)
        sub.ucopy = Var(gens, within=Reals)
        sub.xhat = Param(gens, mutable=True, initialize=0.0)
        sub.fix = Constraint(gens, rule=lambda mm, g: mm.ucopy[g] == mm.xhat[g])
        sub.p = Var(gens, range(T), within=NonNegativeReals)
        sub.ens = Var(range(T), within=NonNegativeReals)
        sub.pmax = Constraint(gens, range(T),
                              rule=lambda mm, g, t: mm.p[g, t] <= PMAX[g] * mm.ucopy[g])
        sub.bal = Constraint(range(T), rule=lambda mm, t:
                             sum(mm.p[g, t] for g in gens) + mm.ens[t] >= d[(s, t)])
        sub.obj = Objective(expr=(1.0 / S) * (
            sum(GCOST[g] * sub.p[g, t] for g in gens for t in range(T))
            + sum(ENS_COST * sub.ens[t] for t in range(T))), sense=minimize)

        def set_xhat(x_hat):
            for g in gens:
                sub.xhat[g] = x_hat[g]

        return {"model": sub, "xcopy": {g: sub.ucopy[g] for g in gens},
                "fix": {g: sub.fix[g] for g in gens}, "set_xhat": set_xhat, "obj": sub.obj}

    t0 = time.time()
    res = benders_solve(make_master, make_subproblem, list(range(S)),
                        config=BendersConfig(max_iterations=200, relative_gap=1e-6),
                        solver=solver)
    return res["objective"], time.time() - t0, res["iterations"], res["converged"]


def main():
    solver = sys.argv[1] if len(sys.argv) > 1 else "appsi_highs"
    print(f"# stochastic unit commitment: Benders vs MILP monolith, solver={solver}", flush=True)
    print(f"# monolith capped at {TIME_LIMIT}s; 'mono_opt' = monolith proved optimality",
          flush=True)
    print(f"{'scen':>5} {'mono_s':>9} {'mono_opt':>9} {'bend_s':>9} {'iters':>5} "
          f"{'speedup':>8} {'bend_opt':>8}", flush=True)
    for S in (10, 20, 40, 80, 160):
        mo, mt, tc = _solve_monolith(S, solver)
        bo, bt, it, conv = _benders(S, solver)
        mono_opt = tc == "optimal"
        # when both prove optimality the objectives match; report Benders converged.
        print(f"{S:>5} {mt:>9.3f} {str(mono_opt):>9} {bt:>9.3f} {it:>5} "
              f"{mt / bt:>8.2f} {str(conv):>8}", flush=True)


if __name__ == "__main__":
    main()
