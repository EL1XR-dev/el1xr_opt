"""Build-speed prototype (SDP): semidefinite relaxation, AC-OPF style.

SDP is the one class that only JuMP and CVXPY can express — Pyomo, pyoframe and
linopy have no PSD-matrix variable. So the Python side here is CVXPY only; JuMP is
in build_speed_sdp.jl.

The instance is the core structure of the Lavaei–Low SDP relaxation of AC OPF: a
Hermitian/symmetric matrix W = V V* relaxed to W ⪰ 0 (dropping the rank-1
condition), with the diagonal fixed by the (normalised) squared voltage magnitudes
and a linear objective in W. Concretely, scalable by matrix dimension n (= buses):

    minimise  trace(L W)
    s.t.      diag(W) = 1            (normalised |V_k|^2)
              W ⪰ 0                  (the PSD relaxation)

with L the Laplacian of the network graph (here a path/feeder). This is the same
modelling object as the AC-OPF SDP relaxation — a PSD matrix variable plus linear
trace constraints — which is what stresses the modeller.

Usage:
    python benchmarks/build_speed_sdp.py --check
    python benchmarks/build_speed_sdp.py --repeats 2
"""
from __future__ import annotations

import argparse
import sys
import time

for _opt in ("cplex", "mosek"):
    sys.modules.setdefault(_opt, None)

import numpy as np


def cost_matrix(n):
    """Adjacency of a ring graph (cycle C_n) — the classic max-cut SDP cost.

    ``min trace(C W) s.t. diag(W)=1, W >= 0`` is the (negated) max-cut SDP
    relaxation; it is indefinite so the optimum is non-trivial (and fractional for
    odd n, the famous SDP gap), making the cross-tool correctness check
    meaningful. Same deterministic instance in Python and Julia.
    """
    C = np.zeros((n, n))
    for k in range(n):
        j = (k + 1) % n
        C[k, j] = 1.0
        C[j, k] = 1.0
    return C


def build_cvxpy(n, solve=False, solver="CLARABEL"):
    import cvxpy as cp
    t0 = time.perf_counter()
    W = cp.Variable((n, n), symmetric=True)
    cons = [W >> 0, cp.diag(W) == np.ones(n)]
    prob = cp.Problem(cp.Minimize(cp.trace(cost_matrix(n) @ W)), cons)
    prob.get_problem_data(solver)   # force canonicalisation (lazy otherwise)
    build = time.perf_counter() - t0
    obj = None
    if solve:
        prob.solve(solver=solver)
        obj = float(prob.value)
    return build, n, obj


BUILDERS = {"cvxpy": build_cvxpy}


def run_sweep(sizes, repeats=1):
    print(f"{'builder':10s} {'n(dim)':>7s} {'vars~':>9s} {'build_s':>9s}")
    for n in sizes:
        best = None
        for _ in range(repeats):
            b, _, _ = build_cvxpy(n)
            best = b if best is None else min(best, b)
        print(f"{'cvxpy':10s} {n:7d} {n * (n + 1) // 2:9d} {best:9.3f}")


def correctness_check():
    n = 10
    _, _, obj = build_cvxpy(n, solve=True)
    print(f"\nCorrectness (small SDP solve, n={n}):")
    print(f"  cvxpy   obj={obj:.8f}   (JuMP should match)")
    return obj


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repeats", type=int, default=1)
    p.add_argument("--check", action="store_true")
    p.add_argument("--n", type=int, default=None)
    args = p.parse_args(argv)
    sizes = [args.n] if args.n else [50, 100, 200]
    run_sweep(sizes, repeats=args.repeats)
    if args.check:
        correctness_check()


if __name__ == "__main__":
    main()
