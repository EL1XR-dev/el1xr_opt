"""Build-speed prototype (harder family): cycle-window storage balance.

This is the more faithful version of `build_speed_storage.py`. The real
el1xr_opt inventory balance does not link only to the previous step; it links a
cycle-boundary inventory to the **sum over a window of steps in that cycle**, and
it is built only at the cycle boundaries (so the constraint index is sparse in
time). That windowed sum + sparse index is exactly what is hard to vectorise, so
it is the honest test before trusting the easy-case speed-ups.

Model (non-overlapping cycles, the block-equivalent of the real windowed rule):
B cycles (blocks), C steps per cycle, G storage units. Charge/discharge live on
every step; inventory lives at each cycle boundary.

    inv[b,g] - inv[b-1,g] - sum_{c} (eta_c*cha[b,c,g] - dis[b,c,g]/eta_d) = 0   (b >= 1)
    inv[0,g] - sum_{c} (eta_c*cha[0,c,g] - dis[0,c,g]/eta_d) = inv0[g]          (b = 0)

Four builders, build time only (not solve): pyomo-rule, pyomo-LinearExpression,
linopy, pyoframe. Run anywhere pyomo+linopy+pyoframe are installed (e.g. Comillas).

Usage:
    python benchmarks/build_speed_storage_window.py --check
    python benchmarks/build_speed_storage_window.py --repeats 2
"""
from __future__ import annotations

import argparse
import sys
import time

# Block broken optional-solver stubs (CPLEX built for another Python, partial
# mosek) that crash linopy/pyoframe solver detection on shared machines. No-op
# where absent; changes nothing installed.
for _opt in ("cplex", "mosek"):
    sys.modules.setdefault(_opt, None)

import numpy as np

ETA_C = 0.95
ETA_D = 0.95


def _data(B, C, G, seed=0):
    rng = np.random.default_rng(seed)
    inv0 = rng.uniform(0.0, 1.0, G)
    return inv0


# --------------------------------------------------------------------------- #
# A. Pyomo, current idiom: per-(block,unit) rule that sums the within-cycle steps
# --------------------------------------------------------------------------- #
def build_pyomo_rule(B, C, G, inv0, with_obj=False):
    import pyomo.environ as pyo

    t0 = time.perf_counter()
    m = pyo.ConcreteModel()
    m.B = pyo.RangeSet(0, B - 1)
    m.C = pyo.RangeSet(0, C - 1)
    m.G = pyo.RangeSet(0, G - 1)
    m.inv = pyo.Var(m.B, m.G, domain=pyo.NonNegativeReals)
    m.cha = pyo.Var(m.B, m.C, m.G, domain=pyo.NonNegativeReals)
    m.dis = pyo.Var(m.B, m.C, m.G, domain=pyo.NonNegativeReals)

    def bal(m, b, g):
        flow = sum(ETA_C * m.cha[b, c, g] - m.dis[b, c, g] / ETA_D for c in m.C)
        if b == 0:
            return m.inv[b, g] - flow == inv0[g]
        return m.inv[b, g] - m.inv[b - 1, g] - flow == 0.0

    m.bal = pyo.Constraint(m.B, m.G, rule=bal)
    if with_obj:
        m.obj = pyo.Objective(expr=sum(m.cha[b, c, g] + m.dis[b, c, g]
                                       for b in m.B for c in m.C for g in m.G))
    build = time.perf_counter() - t0
    return m, build, len(m.bal)


# --------------------------------------------------------------------------- #
# B. Pyomo, LinearExpression body
# --------------------------------------------------------------------------- #
def build_pyomo_linexpr(B, C, G, inv0, with_obj=False):
    import pyomo.environ as pyo
    from pyomo.core.expr.numeric_expr import LinearExpression

    t0 = time.perf_counter()
    m = pyo.ConcreteModel()
    m.B = pyo.RangeSet(0, B - 1)
    m.C = pyo.RangeSet(0, C - 1)
    m.G = pyo.RangeSet(0, G - 1)
    m.inv = pyo.Var(m.B, m.G, domain=pyo.NonNegativeReals)
    m.cha = pyo.Var(m.B, m.C, m.G, domain=pyo.NonNegativeReals)
    m.dis = pyo.Var(m.B, m.C, m.G, domain=pyo.NonNegativeReals)

    def bal(m, b, g):
        coefs = [1.0]
        lvars = [m.inv[b, g]]
        if b != 0:
            coefs.append(-1.0)
            lvars.append(m.inv[b - 1, g])
        for c in m.C:
            coefs.append(-ETA_C)
            lvars.append(m.cha[b, c, g])
            coefs.append(1.0 / ETA_D)
            lvars.append(m.dis[b, c, g])
        le = LinearExpression(constant=0.0, linear_coefs=coefs, linear_vars=lvars)
        return le == (inv0[g] if b == 0 else 0.0)

    m.bal = pyo.Constraint(m.B, m.G, rule=bal)
    if with_obj:
        m.obj = pyo.Objective(expr=sum(m.cha[b, c, g] + m.dis[b, c, g]
                                       for b in m.B for c in m.C for g in m.G))
    build = time.perf_counter() - t0
    return m, build, len(m.bal)


# --------------------------------------------------------------------------- #
# C. linopy, vectorised (sum over the within-cycle step dim, shift over blocks)
# --------------------------------------------------------------------------- #
def build_linopy(B, C, G, inv0, with_obj=False):
    import linopy
    import pandas as pd
    import xarray as xr

    t0 = time.perf_counter()
    m = linopy.Model()
    Bi = pd.RangeIndex(B, name="b")
    Ci = pd.RangeIndex(C, name="c")
    Gi = pd.RangeIndex(G, name="g")
    inv = m.add_variables(lower=0.0, coords=[Bi, Gi], name="inv")
    cha = m.add_variables(lower=0.0, coords=[Bi, Ci, Gi], name="cha")
    dis = m.add_variables(lower=0.0, coords=[Bi, Ci, Gi], name="dis")

    flow = (ETA_C * cha - dis / ETA_D).sum("c")            # -> dims b, g
    inv0_da = xr.DataArray(inv0, coords=[Gi], dims=["g"])

    lhs = inv - inv.shift(b=1) - flow
    m.add_constraints(lhs == 0.0, mask=xr.DataArray(np.arange(B) >= 1, coords=[Bi], dims=["b"]),
                      name="bal")
    m.add_constraints(inv.isel(b=0) - flow.isel(b=0) == inv0_da, name="bal_init")
    if with_obj:
        m.add_objective((cha + dis).sum())
    build = time.perf_counter() - t0
    return m, build, int(m.constraints.ncons)


# --------------------------------------------------------------------------- #
# D. pyoframe, vectorised over Polars frames (sum over c, block lag via index shift)
# --------------------------------------------------------------------------- #
def build_pyoframe(B, C, G, inv0, with_obj=False):
    import pyoframe as pf
    import polars as pl

    t0 = time.perf_counter()
    bb, gg = np.meshgrid(np.arange(B), np.arange(G), indexing="ij")
    bg = pl.DataFrame({"b": bb.ravel(), "g": gg.ravel()})
    bbc, cbc, gbc = np.meshgrid(np.arange(B), np.arange(C), np.arange(G), indexing="ij")
    bcg = pl.DataFrame({"b": bbc.ravel(), "c": cbc.ravel(), "g": gbc.ravel()})

    m = pf.Model()
    m.inv = pf.Variable(bg, lb=0)
    m.cha = pf.Variable(bcg, lb=0)
    m.dis = pf.Variable(bcg, lb=0)

    flow = pf.sum("c", ETA_C * m.cha - m.dis / ETA_D)      # -> dims b, g

    # inv[b-1] aligned at b: shift the block index of inv up by one.
    inv_prev = m.inv.to_expr().with_columns(pl.col("b") + 1)
    # b >= 1 recurrence. Filter every operand to the matching block range so the
    # labels line up exactly (pyoframe checks alignment eagerly on each binary op).
    lhs = m.inv.filter(pl.col("b") >= 1)
    prev_f = inv_prev.filter(pl.col("b") <= B - 1)
    flow_f = flow.filter(pl.col("b") >= 1)
    m.bal = (lhs - prev_f - flow_f) == 0
    # b = 0 initial condition.
    inv0_df = pl.DataFrame({"b": np.zeros(G, dtype=int), "g": np.arange(G), "v": inv0})
    m.bal0 = (m.inv - flow).filter(pl.col("b") == 0) == pf.Param(inv0_df)
    if with_obj:
        m.minimize = pf.sum(m.cha + m.dis)
    build = time.perf_counter() - t0
    return m, build, B * G   # (B-1)*G recurrence rows + G initial rows


BUILDERS = {
    "pyomo-rule": build_pyomo_rule,
    "pyomo-linexpr": build_pyomo_linexpr,
    "linopy": build_linopy,
    "pyoframe": build_pyoframe,
}


def run_sweep(sizes, repeats=1):
    print(f"{'builder':16s} {'B':>5s} {'C':>4s} {'G':>4s} {'cons':>8s} {'build_s':>9s}")
    results = {}
    for (B, C, G) in sizes:
        inv0 = _data(B, C, G)
        for name, fn in BUILDERS.items():
            best, ncon = None, 0
            for _ in range(repeats):
                try:
                    _, build, ncon = fn(B, C, G, inv0)
                except Exception as e:
                    print(f"{name:16s} ERROR: {type(e).__name__}: {str(e)[:80]}")
                    best = None
                    break
                best = build if best is None else min(best, build)
            if best is not None:
                results[(name, B, C, G)] = best
                print(f"{name:16s} {B:5d} {C:4d} {G:4d} {ncon:8d} {best:9.3f}")
        base = results.get(("pyomo-rule", B, C, G))
        if base:
            line = []
            for n in BUILDERS:
                if (n, B, C, G) in results:
                    line.append(f"{n} {base / results[(n, B, C, G)]:.1f}x")
            print("  -> vs pyomo-rule: " + "  ".join(line))
    return results


def correctness_check():
    import pyomo.environ as pyo
    B, C, G = 6, 4, 2
    inv0 = _data(B, C, G)
    target = inv0 + 1.0
    objs = {}

    for name in ("pyomo-rule", "pyomo-linexpr"):
        m, _, _ = BUILDERS[name](B, C, G, inv0, with_obj=True)
        m.term = pyo.Constraint(m.G, rule=lambda mm, g: mm.inv[B - 1, g] == target[g])
        pyo.SolverFactory("appsi_highs").solve(m)
        objs[name] = round(pyo.value(m.obj), 6)

    import xarray as xr
    import pandas as pd
    m, _, _ = build_linopy(B, C, G, inv0, with_obj=True)
    inv = m.variables["inv"]
    m.add_constraints(inv.isel(b=B - 1) == xr.DataArray(target, coords=[pd.RangeIndex(G, name="g")], dims=["g"]),
                      name="term")
    m.solve(solver_name="highs")
    objs["linopy"] = round(float(m.objective.value), 6)

    import pyoframe as pf
    import polars as pl
    m, _, _ = build_pyoframe(B, C, G, inv0, with_obj=True)
    tdf = pl.DataFrame({"b": np.full(G, B - 1), "g": np.arange(G), "v": target})
    m.term = m.inv.filter(pl.col("b") == B - 1) == pf.Param(tdf)
    m.optimize()
    objs["pyoframe"] = round(float(m.objective.value), 6)

    print("\nCorrectness (small solve with forced charging, objectives should match):")
    for n, v in objs.items():
        print(f"  {n:16s} obj={v}")
    vals = set(objs.values())
    print(f"  -> all equal and non-trivial: {len(vals) == 1 and next(iter(vals)) > 0}")
    return objs


def duals_probe():
    """Confirm marginal prices (duals) are retrievable from linopy and pyoframe on
    this family - the open question for using them for LMPs / shadow prices. (This
    is an LP; MILP duals would need a fix-and-resolve step in either tool.)"""
    B, C, G = 6, 4, 2
    inv0 = _data(B, C, G)
    target = inv0 + 1.0
    out = {}

    import xarray as xr
    import pandas as pd
    m, _, _ = build_linopy(B, C, G, inv0, with_obj=True)
    inv = m.variables["inv"]
    m.add_constraints(inv.isel(b=B - 1) == xr.DataArray(target, coords=[pd.RangeIndex(G, name="g")], dims=["g"]),
                      name="term")
    m.solve(solver_name="highs")
    out["linopy"] = float(m.constraints["bal_init"].dual.values.ravel()[0])

    import pyoframe as pf
    import polars as pl
    m, _, _ = build_pyoframe(B, C, G, inv0, with_obj=True)
    tdf = pl.DataFrame({"b": np.full(G, B - 1), "g": np.arange(G), "v": target})
    m.term = m.inv.filter(pl.col("b") == B - 1) == pf.Param(tdf)
    m.optimize()
    out["pyoframe"] = float(m.bal0.dual["dual"][0])

    print("\nDuals probe (shadow price on the b=0 inventory balance; both should return a number):")
    for k, v in out.items():
        print(f"  {k:16s} dual={v:.6f}")
    return out


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repeats", type=int, default=1)
    p.add_argument("--check", action="store_true")
    p.add_argument("--duals", action="store_true", help="confirm linopy/pyoframe return duals")
    p.add_argument("--cycle", type=int, default=24, help="steps per cycle (C)")
    args = p.parse_args(argv)

    C = args.cycle
    sizes = [(7, C, 10), (365, C, 10), (365, C, 50)]   # week, year, year x50 units
    run_sweep(sizes, repeats=args.repeats)
    if args.check:
        correctness_check()
    if args.duals:
        duals_probe()


if __name__ == "__main__":
    main()
