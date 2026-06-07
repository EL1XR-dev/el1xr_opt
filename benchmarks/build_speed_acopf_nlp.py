"""Build-speed prototype (NLP): exact AC optimal power flow, polar form.

This is the *non-convex* class that the roadmap's exact unbalanced AC OPF needs.
Only Pyomo and JuMP can express general NLP (linopy/pyoframe are linear, CVXPY is
convex-only), so this is the Pyomo-vs-JuMP head-to-head for the AC-OPF backbone.
JuMP version: build_speed_acopf_nlp.jl. Times the model BUILD; solves a small case
with Ipopt for the correctness check.

Model: standard polar-form AC OPF on a radial feeder of N+1 buses (bus 0 = slack,
V0=1, theta0=0). Series admittance per line from (r, x); a generator and a load at
each bus. The non-convexity is the bus power-injection equations:

    P_i = V_i^2 G_ii + sum_{j~i} V_i V_j (G_ij cos(t_i-t_j) + B_ij sin(t_i-t_j))
    Q_i = -V_i^2 B_ii + sum_{j~i} V_i V_j (G_ij sin(t_i-t_j) - B_ij cos(t_i-t_j))
    Pg_i - Pd_i = P_i,   Qg_i - Qd_i = Q_i

minimise sum_i c_i Pg_i, with voltage and generation bounds.

Usage:
    python benchmarks/build_speed_acopf_nlp.py --check
    python benchmarks/build_speed_acopf_nlp.py --repeats 2
"""
from __future__ import annotations

import argparse
import time

import numpy as np


def _data(N):
    r = np.full(N, 0.01)
    x = np.full(N, 0.03)
    g = r / (r ** 2 + x ** 2)          # series conductance per line
    b = -x / (r ** 2 + x ** 2)         # series susceptance per line
    Pd = np.concatenate([[0.0], np.full(N, 0.10)])   # load per bus 0..N
    Qd = np.concatenate([[0.0], np.full(N, 0.05)])
    cost = 1.0 + 0.05 * np.arange(N + 1)             # gen cost per bus (cheapest at slack)
    return g, b, Pd, Qd, cost


def _ybus_feeder(g, b, N):
    """Tridiagonal Ybus of the feeder. Returns Gd,Bd (diagonals, len N+1) and a
    function nbr_adm(i,j)->(Gij,Bij) for adjacent buses."""
    Gd = np.zeros(N + 1)
    Bd = np.zeros(N + 1)
    for k in range(1, N + 1):           # line k between bus k-1 and k
        for i in (k - 1, k):
            Gd[i] += g[k - 1]
            Bd[i] += b[k - 1]

    def nbr_adm(i, j):
        k = max(i, j)                   # the line index between i and j
        return -g[k - 1], -b[k - 1]
    return Gd, Bd, nbr_adm


def build_pyomo(N, data, solve=False):
    import pyomo.environ as pyo
    g, b, Pd, Qd, cost = data
    Gd, Bd, nbr_adm = _ybus_feeder(g, b, N)
    t0 = time.perf_counter()
    m = pyo.ConcreteModel()
    m.bus = pyo.RangeSet(0, N)
    m.V = pyo.Var(m.bus, bounds=(0.9, 1.1), initialize=1.0)
    m.th = pyo.Var(m.bus, initialize=0.0)
    m.Pg = pyo.Var(m.bus, bounds=(0.0, 5.0), initialize=0.0)
    m.Qg = pyo.Var(m.bus, bounds=(-3.0, 3.0), initialize=0.0)
    m.V[0].fix(1.0)
    m.th[0].fix(0.0)

    def nbrs(i):
        return [j for j in (i - 1, i + 1) if 0 <= j <= N]

    def pbal(m, i):
        inj = m.V[i] ** 2 * Gd[i]
        for j in nbrs(i):
            Gij, Bij = nbr_adm(i, j)
            inj += m.V[i] * m.V[j] * (Gij * pyo.cos(m.th[i] - m.th[j]) + Bij * pyo.sin(m.th[i] - m.th[j]))
        return m.Pg[i] - Pd[i] == inj

    def qbal(m, i):
        inj = -m.V[i] ** 2 * Bd[i]
        for j in nbrs(i):
            Gij, Bij = nbr_adm(i, j)
            inj += m.V[i] * m.V[j] * (Gij * pyo.sin(m.th[i] - m.th[j]) - Bij * pyo.cos(m.th[i] - m.th[j]))
        return m.Qg[i] - Qd[i] == inj

    m.pbal = pyo.Constraint(m.bus, rule=pbal)
    m.qbal = pyo.Constraint(m.bus, rule=qbal)
    m.obj = pyo.Objective(expr=sum(cost[i] * m.Pg[i] for i in m.bus))
    build = time.perf_counter() - t0
    obj = None
    if solve:
        pyo.SolverFactory("ipopt").solve(m)
        obj = float(pyo.value(m.obj))
    return build, 2 * (N + 1), obj


BUILDERS = {"pyomo": build_pyomo}


def run_sweep(sizes, repeats=1):
    print(f"{'builder':10s} {'N buses':>8s} {'cons':>8s} {'build_s':>9s}")
    for N in sizes:
        data = _data(N)
        best = None
        for _ in range(repeats):
            bld, ncon, _ = build_pyomo(N, data)
            best = bld if best is None else min(best, bld)
        print(f"{'pyomo':10s} {N:8d} {ncon:8d} {best:9.3f}")


def correctness_check():
    N = 8
    _, _, obj = build_pyomo(N, _data(N), solve=True)
    print(f"\nCorrectness (small AC OPF NLP solve, n={N}):")
    print(f"  pyomo   obj={obj}")
    return obj


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repeats", type=int, default=1)
    p.add_argument("--check", action="store_true")
    p.add_argument("--n", type=int, default=None)
    args = p.parse_args(argv)
    sizes = [args.n] if args.n else [100, 1000, 10000]
    run_sweep(sizes, repeats=args.repeats)
    if args.check:
        correctness_check()


if __name__ == "__main__":
    main()
