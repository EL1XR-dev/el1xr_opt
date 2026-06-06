"""Build-speed prototype: the storage inventory balance, three ways.

Why this constraint: in el1xr_opt the energy-storage inventory balance is one of
the largest constraint families and is built with a per-element Python rule, which
is the kind of construction that dominates model-build time (see
docs/computational_efficiency.md). This script builds the *same* constraint at a
realistic scale three ways and times only the model BUILD (not the solve):

  A. pyomo-rule     - the current idiom: Constraint(index, rule=fn) with the body
                      written as a normal Pyomo expression (operator overloading).
  B. pyomo-linexpr  - same Pyomo, but each body built as a LinearExpression, the
                      documented fast path that skips the expression-tree overhead.
  C. linopy         - vectorised over (time, unit) with xarray; one array op builds
                      the whole family.

The constraint (one simple cyclic storage balance per unit and time step):

    inv[t,g] - inv[t-1,g] - dt[t] * (eta_c * cha[t,g] - dis[t,g] / eta_d) = 0   (t >= 1)
    inv[0,g] - dt[0] * (eta_c * cha[0,g] - dis[0,g] / eta_d) = inv0[g]          (t = 0)

It is a faithful, self-contained stand-in for the real ``eEleInventory`` family,
so it needs no case data and runs anywhere pyomo + linopy are installed - in
particular on the Comillas desktop for the authoritative numbers.

Usage:
    python benchmarks/build_speed_storage.py                 # default sweep
    python benchmarks/build_speed_storage.py --t 8760 --g 10 # one size
    python benchmarks/build_speed_storage.py --check         # also solve small, compare objectives
"""
from __future__ import annotations

import argparse
import sys
import time

# Some shared machines ship broken optional-solver stubs (e.g. a CPLEX built for
# another Python version, or a partial mosek) that crash linopy's solver-detection
# on import. Mark them unavailable in THIS process so linopy skips them. This does
# not change anything installed on the machine, and is a no-op where they are
# absent (the local dev box).
for _opt in ("cplex", "mosek"):
    sys.modules.setdefault(_opt, None)

import numpy as np


# Fixed technical data (shape only matters for the benchmark).
ETA_C = 0.95
ETA_D = 0.95


def _data(T, G, seed=0):
    rng = np.random.default_rng(seed)
    dt = np.ones(T)                      # step duration [h]
    inv0 = rng.uniform(0.0, 1.0, G)      # initial inventory per unit
    return dt, inv0


# --------------------------------------------------------------------------- #
# A. Pyomo, current idiom (operator-overloaded expression in a rule)
# --------------------------------------------------------------------------- #
def build_pyomo_rule(T, G, dt, inv0, with_obj=False):
    import pyomo.environ as pyo

    t0 = time.perf_counter()
    m = pyo.ConcreteModel()
    m.T = pyo.RangeSet(0, T - 1)
    m.G = pyo.RangeSet(0, G - 1)
    m.inv = pyo.Var(m.T, m.G, domain=pyo.NonNegativeReals)
    m.cha = pyo.Var(m.T, m.G, domain=pyo.NonNegativeReals)
    m.dis = pyo.Var(m.T, m.G, domain=pyo.NonNegativeReals)

    def bal(m, t, g):
        body = m.inv[t, g] - dt[t] * (ETA_C * m.cha[t, g] - m.dis[t, g] / ETA_D)
        if t == 0:
            return body == inv0[g]
        return body - m.inv[t - 1, g] == 0.0

    m.bal = pyo.Constraint(m.T, m.G, rule=bal)
    if with_obj:
        m.obj = pyo.Objective(expr=sum(m.cha[t, g] + m.dis[t, g] for t in m.T for g in m.G))
    build = time.perf_counter() - t0
    return m, build, len(m.bal)


# --------------------------------------------------------------------------- #
# B. Pyomo, LinearExpression body (skip the operator-overload expression tree)
# --------------------------------------------------------------------------- #
def build_pyomo_linexpr(T, G, dt, inv0, with_obj=False):
    import pyomo.environ as pyo
    from pyomo.core.expr.numeric_expr import LinearExpression

    t0 = time.perf_counter()
    m = pyo.ConcreteModel()
    m.T = pyo.RangeSet(0, T - 1)
    m.G = pyo.RangeSet(0, G - 1)
    m.inv = pyo.Var(m.T, m.G, domain=pyo.NonNegativeReals)
    m.cha = pyo.Var(m.T, m.G, domain=pyo.NonNegativeReals)
    m.dis = pyo.Var(m.T, m.G, domain=pyo.NonNegativeReals)

    def bal(m, t, g):
        cc = -ETA_C * dt[t]
        cd = dt[t] / ETA_D
        if t == 0:
            le = LinearExpression(constant=0.0,
                                  linear_coefs=[1.0, cc, cd],
                                  linear_vars=[m.inv[t, g], m.cha[t, g], m.dis[t, g]])
            return le == inv0[g]
        le = LinearExpression(constant=0.0,
                              linear_coefs=[1.0, -1.0, cc, cd],
                              linear_vars=[m.inv[t, g], m.inv[t - 1, g], m.cha[t, g], m.dis[t, g]])
        return le == 0.0

    m.bal = pyo.Constraint(m.T, m.G, rule=bal)
    if with_obj:
        m.obj = pyo.Objective(expr=sum(m.cha[t, g] + m.dis[t, g] for t in m.T for g in m.G))
    build = time.perf_counter() - t0
    return m, build, len(m.bal)


# --------------------------------------------------------------------------- #
# C. linopy, vectorised over (t, g)
# --------------------------------------------------------------------------- #
def build_linopy(T, G, dt, inv0, with_obj=False):
    import linopy
    import pandas as pd
    import xarray as xr

    t0 = time.perf_counter()
    m = linopy.Model()
    Ti = pd.RangeIndex(T, name="t")
    Gi = pd.RangeIndex(G, name="g")
    inv = m.add_variables(lower=0.0, coords=[Ti, Gi], name="inv")
    cha = m.add_variables(lower=0.0, coords=[Ti, Gi], name="cha")
    dis = m.add_variables(lower=0.0, coords=[Ti, Gi], name="dis")

    dt_da = xr.DataArray(dt, coords=[Ti], dims=["t"])
    inv0_da = xr.DataArray(inv0, coords=[Gi], dims=["g"])

    # Recurrence for t >= 1 (the shifted term is NaN at t=0, masked out).
    lhs = inv - inv.shift(t=1) - dt_da * (ETA_C * cha - dis / ETA_D)
    m.add_constraints(lhs == 0.0, mask=xr.DataArray(np.arange(T) >= 1, coords=[Ti], dims=["t"]),
                      name="bal")
    # Initial condition at t = 0.
    init = inv.isel(t=0) - dt_da.isel(t=0) * (ETA_C * cha.isel(t=0) - dis.isel(t=0) / ETA_D)
    m.add_constraints(init == inv0_da, name="bal_init")
    if with_obj:
        m.add_objective((cha + dis).sum())
    build = time.perf_counter() - t0
    ncon = int(m.constraints.ncons)
    return m, build, ncon


BUILDERS = {
    "pyomo-rule": build_pyomo_rule,
    "pyomo-linexpr": build_pyomo_linexpr,
    "linopy": build_linopy,
}


def run_sweep(sizes, repeats=1):
    print(f"{'builder':16s} {'T':>6s} {'G':>4s} {'cons':>9s} {'build_s':>9s}")
    results = {}
    for (T, G) in sizes:
        dt, inv0 = _data(T, G)
        for name, fn in BUILDERS.items():
            best = None
            ncon = 0
            for _ in range(repeats):
                _, build, ncon = fn(T, G, dt, inv0)
                best = build if best is None else min(best, build)
            results[(name, T, G)] = best
            print(f"{name:16s} {T:6d} {G:4d} {ncon:9d} {best:9.3f}")
        base = results.get(("pyomo-rule", T, G))
        if base:
            speed = {n: base / results[(n, T, G)] for n in BUILDERS}
            print(f"  -> speedup vs pyomo-rule: " +
                  "  ".join(f"{n} {speed[n]:.1f}x" for n in BUILDERS))
    return results


def correctness_check():
    """Build small with each backend, force charging via a terminal inventory
    target, solve with HiGHS, and compare objectives. A non-trivial (non-zero)
    objective that matches across backends shows the three constraint families are
    the same model."""
    import pyomo.environ as pyo
    T, G = 24, 2
    dt, inv0 = _data(T, G)
    target = inv0 + 1.0          # force the storage to charge up
    objs = {}

    for name in ("pyomo-rule", "pyomo-linexpr"):
        m, _, _ = BUILDERS[name](T, G, dt, inv0, with_obj=True)
        m.term = pyo.Constraint(m.G, rule=lambda mm, g: mm.inv[T - 1, g] == target[g])
        pyo.SolverFactory("appsi_highs").solve(m)
        objs[name] = round(pyo.value(m.obj), 6)

    m, _, _ = build_linopy(T, G, dt, inv0, with_obj=True)
    inv = m.variables["inv"]
    import xarray as xr
    import pandas as pd
    tgt = xr.DataArray(target, coords=[pd.RangeIndex(G, name="g")], dims=["g"])
    m.add_constraints(inv.isel(t=T - 1) == tgt, name="term")
    m.solve(solver_name="highs")
    objs["linopy"] = round(float(m.objective.value), 6)

    print("\nCorrectness (small solve with forced charging, objectives should match):")
    for n, v in objs.items():
        print(f"  {n:16s} obj={v}")
    same = len({v for v in objs.values()}) == 1 and next(iter(objs.values())) > 0
    print(f"  -> all equal and non-trivial: {same}")
    return same


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--t", type=int, default=None, help="single run: number of time steps")
    p.add_argument("--g", type=int, default=10, help="number of storage units")
    p.add_argument("--repeats", type=int, default=1, help="take the fastest of N builds")
    p.add_argument("--check", action="store_true", help="also run the small solve correctness check")
    args = p.parse_args(argv)

    if args.t:
        sizes = [(args.t, args.g)]
    else:
        sizes = [(168, 10), (1000, 10), (8760, 10), (8760, 50)]

    run_sweep(sizes, repeats=args.repeats)
    if args.check:
        correctness_check()


if __name__ == "__main__":
    main()
