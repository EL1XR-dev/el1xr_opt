"""Spatial decomposition of the block-angular form vs the nodal monolith.

The per-asset/arc balance is block-angular, but for economic dispatch the useful
blocks are not single assets (those are trivial) -- they are **regions** weakly
coupled by a few inter-region tie-lines. This benchmark builds a ring of R regions,
each an internal dispatch problem, connected by one tie-line between neighbours,
and solves it two ways:

  * monolith -- the full nodal LP (HiGHS).
  * Benders  -- the tie-line flows are the complicating variables in the master;
                each region is a subproblem given its tie-line import/export, made
                always-feasible by an energy-not-served penalty. Reuses the
                validated ``benders_solve``.

It reports the objective (must match), the monolith solve time, and the Benders
time and iteration count. The question it answers honestly: does decomposing the
block-angular form beat the monolith, and in what regime.

Run: python spatial_decomposition.py [solver]
"""
import os
import sys
import time

from pyomo.environ import (ConcreteModel, Var, Param, Constraint, ConstraintList,
                           Objective, Reals, NonNegativeReals, Suffix, minimize, value,
                           SolverFactory)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from el1xr_opt.Modules.oM_Decomposition import benders_solve, BendersConfig

GCOST = 5.0
ENS_COST = 1000.0
GCAP = 100.0
TIECAP = 60.0


def _data(R, nodes_per_region, T):
    steps = list(range(T))
    regions = list(range(R))
    # per region: a list of nodes; node 0 is the border node carrying the tie-line
    demand = {(r, i, t): 8.0 + 4.0 * ((r + i + t) % 4)
              for r in regions for i in range(nodes_per_region) for t in steps}
    return regions, steps, nodes_per_region, demand


def build_monolith(R, npr, T):
    regions, steps, npr, demand = _data(R, npr, T)
    m = ConcreteModel()
    m.gen = Var(regions, range(npr), steps, within=NonNegativeReals, bounds=(0, GCAP))
    m.ens = Var(regions, range(npr), steps, within=NonNegativeReals)
    m.tf = Var(regions, steps, within=Reals, bounds=(-TIECAP, TIECAP))   # r -> r+1

    # internal-region transfer is free (a region's nodes share a bus); the only
    # spatial coupling is the tie-line. Region balance per (r, t): generation +
    # ENS + net tie injection == region demand.
    def bal(mm, r, t):
        tie_in = mm.tf[(r - 1) % R, t] - mm.tf[r, t]
        return (sum(mm.gen[r, i, t] + mm.ens[r, i, t] for i in range(npr)) + tie_in
                == sum(demand[(r, i, t)] for i in range(npr)))
    m.bal = Constraint(regions, steps, rule=bal)
    m.obj = Objective(expr=sum(GCOST * m.gen[r, i, t] + ENS_COST * m.ens[r, i, t]
                               for r in regions for i in range(npr) for t in steps),
                      sense=minimize)
    return m


def _solve_monolith(R, npr, T, solver):
    m = build_monolith(R, npr, T)
    t0 = time.time()
    SolverFactory(solver).solve(m)
    return float(value(m.obj)), time.time() - t0


def _benders(R, npr, T, solver):
    regions, steps, npr, demand = _data(R, npr, T)
    tie_names = [(r, t) for r in regions for t in steps]

    def make_master():
        mm = ConcreteModel()
        mm.tf = Var(regions, steps, within=Reals, bounds=(-TIECAP, TIECAP), initialize=0.0)
        mm.theta = Var(regions, within=Reals, bounds=(-1e7, 1e12), initialize=0.0)
        mm.cuts = ConstraintList()
        mm.obj = Objective(expr=sum(mm.theta[r] for r in regions), sense=minimize)
        x = {(r, t): mm.tf[r, t] for (r, t) in tie_names}
        return {"model": mm, "x": x, "theta": {r: mm.theta[r] for r in regions}, "cuts": mm.cuts}

    def make_subproblem(region):
        r = region
        s = ConcreteModel()
        s.dual = Suffix(direction=Suffix.IMPORT)
        s.gen = Var(range(npr), steps, within=NonNegativeReals, bounds=(0, GCAP))
        s.ens = Var(range(npr), steps, within=NonNegativeReals)
        s.tfc = Var(regions, steps, within=Reals)            # free copy of every tie
        s.xhat = Param(regions, steps, mutable=True, initialize=0.0)
        s.fix = Constraint(regions, steps, rule=lambda mm, rr, t: mm.tfc[rr, t] == mm.xhat[rr, t])

        def bal(mm, t):
            tie_in = mm.tfc[(r - 1) % R, t] - mm.tfc[r, t]
            return (sum(mm.gen[i, t] + mm.ens[i, t] for i in range(npr)) + tie_in
                    == sum(demand[(r, i, t)] for i in range(npr)))
        s.bal = Constraint(steps, rule=bal)
        s.obj = Objective(expr=sum(GCOST * s.gen[i, t] + ENS_COST * s.ens[i, t]
                                   for i in range(npr) for t in steps), sense=minimize)

        def set_xhat(x_hat):
            for (rr, t) in tie_names:
                s.xhat[rr, t] = x_hat[(rr, t)]

        return {"model": s, "xcopy": {(rr, t): s.tfc[rr, t] for (rr, t) in tie_names},
                "fix": {(rr, t): s.fix[rr, t] for (rr, t) in tie_names},
                "set_xhat": set_xhat, "obj": s.obj}

    t0 = time.time()
    res = benders_solve(make_master, make_subproblem, regions,
                        config=BendersConfig(max_iterations=200, relative_gap=1e-7),
                        solver=solver)
    return res["objective"], time.time() - t0, res["iterations"], res["converged"]


def main():
    solver = sys.argv[1] if len(sys.argv) > 1 else "appsi_highs"
    print(f"# spatial decomposition vs nodal monolith, solver={solver}", flush=True)
    print(f"{'regions':>7} {'nodes/r':>7} {'steps':>5} {'mono_s':>8} {'bend_s':>8} "
          f"{'iters':>5} {'speedup':>8} {'match':>6}", flush=True)
    for R, npr, T in ((6, 5, 24), (12, 8, 24), (24, 10, 48), (48, 10, 48)):
        mo, mt = _solve_monolith(R, npr, T, solver)
        bo, bt, it, conv = _benders(R, npr, T, solver)
        match = abs(mo - bo) / (abs(mo) + 1e-9) < 1e-5 and conv
        print(f"{R:>7} {npr:>7} {T:>5} {mt:>8.3f} {bt:>8.3f} {it:>5} "
              f"{mt / bt:>8.2f} {str(match):>6}", flush=True)


if __name__ == "__main__":
    main()
