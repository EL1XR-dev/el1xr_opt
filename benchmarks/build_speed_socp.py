"""Build-speed prototype (SOCP): branch-flow / DistFlow relaxation of AC OPF.

This is the conic test that linopy cannot express (no quadratic constraints), so
the field is pyomo / pyoframe / CVXPY (Python) and JuMP (Julia, separate file).
It is a real power-systems SOCP: the second-order-cone (Baran-Wu / DistFlow)
relaxation of optimal power flow on a radial feeder.

Network: a radial feeder, bus 0 = slack (v0 fixed), buses 1..N each with a load.
Branch j connects bus j-1 to bus j with impedance (r_j, x_j). Per branch:

    P[j] - r_j l[j] - P[j+1] = p[j]                              (active balance)
    Q[j] - x_j l[j] - Q[j+1] = q[j]                              (reactive balance)
    v[j] = v[j-1] - 2(r_j P[j] + x_j Q[j]) + (r_j^2 + x_j^2) l[j] (voltage drop)
    P[j]^2 + Q[j]^2 <= l[j] * v[j-1]                             (rotated SOC)

with l[j] >= 0, v[j] >= 0, v[0] = V0. Objective: minimise losses sum_j r_j l[j].
The SOC is a rotated cone (convex, since l,v >= 0); solvers handle it as SOCP.

Usage:
    python benchmarks/build_speed_socp.py --check       # solve small, compare objectives
    python benchmarks/build_speed_socp.py --repeats 2   # build-time sweep
"""
from __future__ import annotations

import argparse
import sys
import time

for _opt in ("cplex", "mosek"):
    sys.modules.setdefault(_opt, None)

import numpy as np

V0 = 1.0


def _data(N):
    # Small, uniform loads/impedances so the feeder stays feasible at the solve
    # size; values are illustrative (the benchmark is about build time).
    r = np.full(N, 0.01)
    x = np.full(N, 0.02)
    p = np.full(N, 0.02)
    q = np.full(N, 0.01)
    return r, x, p, q


# --------------------------------------------------------------------------- #
# Pyomo (reference) — per-branch rule, quadratic (rotated-cone) constraint
# --------------------------------------------------------------------------- #
def build_pyomo(N, data, solve=False, solver="gurobi"):
    import pyomo.environ as pyo
    r, x, p, q = data
    t0 = time.perf_counter()
    m = pyo.ConcreteModel()
    m.J = pyo.RangeSet(1, N)
    m.P = pyo.Var(m.J)
    m.Q = pyo.Var(m.J)
    m.l = pyo.Var(m.J, domain=pyo.NonNegativeReals)
    m.v = pyo.Var(m.J, domain=pyo.NonNegativeReals)

    def vprev(j):
        return V0 if j == 1 else m.v[j - 1]

    def pbal(m, j):
        Pn = 0.0 if j == N else m.P[j + 1]
        return m.P[j] - r[j - 1] * m.l[j] - Pn == p[j - 1]

    def qbal(m, j):
        Qn = 0.0 if j == N else m.Q[j + 1]
        return m.Q[j] - x[j - 1] * m.l[j] - Qn == q[j - 1]

    def volt(m, j):
        return m.v[j] == vprev(j) - 2 * (r[j - 1] * m.P[j] + x[j - 1] * m.Q[j]) \
            + (r[j - 1] ** 2 + x[j - 1] ** 2) * m.l[j]

    def soc(m, j):
        return m.P[j] ** 2 + m.Q[j] ** 2 <= m.l[j] * vprev(j)

    m.pbal = pyo.Constraint(m.J, rule=pbal)
    m.qbal = pyo.Constraint(m.J, rule=qbal)
    m.volt = pyo.Constraint(m.J, rule=volt)
    m.soc = pyo.Constraint(m.J, rule=soc)
    m.obj = pyo.Objective(expr=sum(r[j - 1] * m.l[j] for j in m.J))
    build = time.perf_counter() - t0
    obj = None
    if solve:
        pyo.SolverFactory(solver).solve(m)
        obj = float(pyo.value(m.obj))
    return build, 4 * N, obj


# --------------------------------------------------------------------------- #
# CVXPY — vectorised; rotated cone via the norm form ||(2P,2Q,l-v)|| <= l+v
# --------------------------------------------------------------------------- #
def build_cvxpy(N, data, solve=False, solver="CLARABEL"):
    import cvxpy as cp
    r, x, p, q = data
    t0 = time.perf_counter()
    P = cp.Variable(N)
    Q = cp.Variable(N)
    lc = cp.Variable(N, nonneg=True)
    v = cp.Variable(N, nonneg=True)
    vprev = cp.hstack([V0, v[:-1]])               # v[j-1], with v[0]=V0
    Pnext = cp.hstack([P[1:], 0.0])               # P[j+1], 0 at the end
    Qnext = cp.hstack([Q[1:], 0.0])
    cons = [
        P - cp.multiply(r, lc) - Pnext == p,
        Q - cp.multiply(x, lc) - Qnext == q,
        v == vprev - 2 * (cp.multiply(r, P) + cp.multiply(x, Q)) + cp.multiply(r ** 2 + x ** 2, lc),
    ]
    # Rotated cone P^2+Q^2 <= l*vprev  <=>  ||(2P, 2Q, l-vprev)|| <= l+vprev
    cons.append(cp.SOC(lc + vprev, cp.vstack([2 * P, 2 * Q, lc - vprev])))
    prob = cp.Problem(cp.Minimize(r @ lc), cons)
    # CVXPY builds the model lazily; the real work is canonicalisation to conic
    # form, which happens at solve. Force it here so the build time is comparable
    # to the eager builders (pyomo/pyoframe/JuMP) rather than ~0.
    prob.get_problem_data(solver)
    build = time.perf_counter() - t0
    obj = None
    if solve:
        prob.solve(solver=solver)
        obj = float(prob.value)
    return build, 4 * N, obj


# --------------------------------------------------------------------------- #
# pyoframe — vectorised over Polars; v[j-1] and P[j+1] via index shifts, with the
# boundaries (j=1 uses V0; j=N has no downstream flow) as separate constraints.
# --------------------------------------------------------------------------- #
def build_pyoframe(N, data, solve=False):
    import pyoframe as pf
    import polars as pl
    r, x, p, q = data
    t0 = time.perf_counter()
    j = np.arange(1, N + 1)
    branch = pl.DataFrame({"j": j})
    m = pf.Model()
    m.P = pf.Variable(branch)
    m.Q = pf.Variable(branch)
    m.l = pf.Variable(branch, lb=0)
    m.v = pf.Variable(branch, lb=0)

    def par(vals):
        return pf.Param(pl.DataFrame({"j": j, "v": np.asarray(vals, float)}))
    rP, xP, pP, qP = par(r), par(x), par(p), par(q)
    rsq = par(r ** 2 + x ** 2)

    def fb(expr, lo, hi):   # filter an expression/var to a branch range [lo, hi]
        return expr.filter((pl.col("j") >= lo) & (pl.col("j") <= hi))

    # v[j-1] aligned at branch j (only defined for j>=2; j=1 uses the V0 constant).
    vprev = m.v.to_expr().with_columns(pl.col("j") + 1)   # at j holds v[j-1]

    # --- power balance ---
    # interior j=1..N-1: P[j] - r l[j] - P[j+1] = p[j]
    Pnext = m.P.to_expr().with_columns(pl.col("j") - 1)   # at j holds P[j+1]
    Qnext = m.Q.to_expr().with_columns(pl.col("j") - 1)
    m.pbal_in = (fb(m.P, 1, N - 1) - fb(rP, 1, N - 1) * fb(m.l, 1, N - 1) - fb(Pnext, 1, N - 1)) == fb(pP, 1, N - 1)
    m.qbal_in = (fb(m.Q, 1, N - 1) - fb(xP, 1, N - 1) * fb(m.l, 1, N - 1) - fb(Qnext, 1, N - 1)) == fb(qP, 1, N - 1)
    # last bus j=N: no downstream flow
    m.pbal_end = (fb(m.P, N, N) - fb(rP, N, N) * fb(m.l, N, N)) == fb(pP, N, N)
    m.qbal_end = (fb(m.Q, N, N) - fb(xP, N, N) * fb(m.l, N, N)) == fb(qP, N, N)

    # --- voltage drop ---
    # j=1: v[1] = V0 - 2(r P + x Q) + rsq l
    m.volt1 = (fb(m.v, 1, 1) - (-2) * (fb(rP, 1, 1) * fb(m.P, 1, 1) + fb(xP, 1, 1) * fb(m.Q, 1, 1))
               - fb(rsq, 1, 1) * fb(m.l, 1, 1)) == V0
    # j=2..N: v[j] = v[j-1] - 2(r P + x Q) + rsq l
    m.volt_in = (fb(m.v, 2, N) - fb(vprev, 2, N) + 2 * (fb(rP, 2, N) * fb(m.P, 2, N) + fb(xP, 2, N) * fb(m.Q, 2, N))
                 - fb(rsq, 2, N) * fb(m.l, 2, N)) == 0

    # --- rotated SOC: P^2 + Q^2 <= l * vprev ---
    m.soc1 = (fb(m.P, 1, 1) * fb(m.P, 1, 1) + fb(m.Q, 1, 1) * fb(m.Q, 1, 1)) <= V0 * fb(m.l, 1, 1)
    m.soc_in = (fb(m.P, 2, N) * fb(m.P, 2, N) + fb(m.Q, 2, N) * fb(m.Q, 2, N)) <= fb(m.l, 2, N) * fb(vprev, 2, N)

    m.minimize = pf.sum(rP * m.l)
    build = time.perf_counter() - t0
    obj = None
    if solve:
        m.optimize()
        obj = float(m.objective.value)
    return build, 4 * N, obj


BUILDERS = {
    "pyomo": build_pyomo,
    "pyoframe": build_pyoframe,
    "cvxpy": build_cvxpy,
}


def run_sweep(sizes, repeats=1, only=None):
    builders = {k: v for k, v in BUILDERS.items() if (only is None or k in only)}
    print(f"{'builder':12s} {'N(buses)':>9s} {'cons':>9s} {'build_s':>9s}")
    results = {}
    for N in sizes:
        data = _data(N)
        for name, fn in builders.items():
            best, ncon = None, 0
            for _ in range(repeats):
                try:
                    b, ncon, _ = fn(N, data)
                except Exception as e:
                    print(f"{name:12s} ERROR: {type(e).__name__}: {str(e)[:80]}")
                    best = None
                    break
                best = b if best is None else min(best, b)
            if best is not None:
                results[(name, N)] = best
                print(f"{name:12s} {N:9d} {ncon:9d} {best:9.3f}")
        base = results.get(("pyomo", N))
        if base:
            print("  -> vs pyomo: " + "  ".join(
                f"{n} {base / results[(n, N)]:.1f}x" for n in builders if (n, N) in results))
    return results


def correctness_check():
    N = 8
    data = _data(N)
    objs = {}
    _, _, objs["pyomo"] = build_pyomo(N, data, solve=True)
    _, _, objs["pyoframe"] = build_pyoframe(N, data, solve=True)
    _, _, objs["cvxpy"] = build_cvxpy(N, data, solve=True)
    print("\nCorrectness (small SOCP solve, objective = losses, should match):")
    for k, val in objs.items():
        print(f"  {k:10s} obj={val:.8f}")
    vals = [v for v in objs.values() if v is not None]
    print(f"  -> max abs diff: {max(vals) - min(vals):.2e}")
    return objs


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repeats", type=int, default=1)
    p.add_argument("--check", action="store_true")
    p.add_argument("--n", type=int, default=None, help="custom single size (number of buses)")
    p.add_argument("--only", type=str, default=None)
    args = p.parse_args(argv)
    only = set(args.only.split(",")) if args.only else None
    sizes = [args.n] if args.n else [100, 1000, 10000]
    run_sweep(sizes, repeats=args.repeats, only=only)
    if args.check:
        correctness_check()


if __name__ == "__main__":
    main()
