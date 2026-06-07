"""End-to-end build check: construct + export-to-solver, linopy vs Pyomo.

The other build benchmarks time *modelling-layer construction* only. That excludes
the step where the model is handed to the solver (Pyomo writes an LP/NL file or
loads an in-memory matrix; linopy assembles a scipy sparse matrix). Both tools
defer that step, so a construct-only number flatters whichever tool has the
cheaper construct. This script times the full path to solver-ready so the
comparison is honest, on the storage inventory family (the same model as
build_speed_storage_window.py).

For Pyomo, two export paths are timed: the LP file (a common path) and the
in-memory appsi-HiGHS load (what the test suite actually uses). For linopy, the
matrices assembly that its solve uses.

Usage:  python benchmarks/build_speed_endtoend.py            # default sizes
        python benchmarks/build_speed_endtoend.py --b 365 --g 50
"""
from __future__ import annotations

import argparse
import os
import sys
import tempfile
import time

for _opt in ("cplex", "mosek"):
    sys.modules.setdefault(_opt, None)

import numpy as np

EC, ED = 0.95, 0.95


def linopy_endtoend(B, C, G, inv0):
    import linopy
    import pandas as pd
    import xarray as xr
    t0 = time.perf_counter()
    m = linopy.Model()
    Bi, Ci, Gi = pd.RangeIndex(B, name="b"), pd.RangeIndex(C, name="c"), pd.RangeIndex(G, name="g")
    inv = m.add_variables(lower=0.0, coords=[Bi, Gi], name="inv")
    cha = m.add_variables(lower=0.0, coords=[Bi, Ci, Gi], name="cha")
    dis = m.add_variables(lower=0.0, coords=[Bi, Ci, Gi], name="dis")
    flow = (EC * cha - dis / ED).sum("c")
    m.add_constraints(inv - inv.shift(b=1) - flow == 0.0,
                      mask=xr.DataArray(np.arange(B) >= 1, coords=[Bi], dims=["b"]), name="bal")
    m.add_constraints(inv.isel(b=0) - flow.isel(b=0) == xr.DataArray(inv0, coords=[Gi], dims=["g"]),
                      name="bal_init")
    construct = time.perf_counter() - t0
    t1 = time.perf_counter()
    _ = m.matrices.A
    _ = m.matrices.c
    export = time.perf_counter() - t1
    return construct, export


def _pyomo_model(B, C, G, inv0):
    import pyomo.environ as pyo
    mp = pyo.ConcreteModel()
    mp.B, mp.C, mp.G = pyo.RangeSet(0, B - 1), pyo.RangeSet(0, C - 1), pyo.RangeSet(0, G - 1)
    mp.inv = pyo.Var(mp.B, mp.G, domain=pyo.NonNegativeReals)
    mp.cha = pyo.Var(mp.B, mp.C, mp.G, domain=pyo.NonNegativeReals)
    mp.dis = pyo.Var(mp.B, mp.C, mp.G, domain=pyo.NonNegativeReals)

    def bal(m, b, g):
        fl = sum(EC * m.cha[b, c, g] - m.dis[b, c, g] / ED for c in m.C)
        return (m.inv[b, g] - fl == inv0[g]) if b == 0 else (m.inv[b, g] - m.inv[b - 1, g] - fl == 0.0)
    mp.bal = pyo.Constraint(mp.B, mp.G, rule=bal)
    mp.obj = pyo.Objective(expr=sum(mp.cha[b, c, g] + mp.dis[b, c, g] for b in mp.B for c in mp.C for g in mp.G))
    return mp


def pyomo_endtoend(B, C, G, inv0):
    t0 = time.perf_counter()
    mp = _pyomo_model(B, C, G, inv0)
    construct = time.perf_counter() - t0
    fd, fn = tempfile.mkstemp(suffix=".lp")
    os.close(fd)
    t1 = time.perf_counter()
    mp.write(fn)
    export_lp = time.perf_counter() - t1
    os.remove(fn)
    export_appsi = float("nan")
    try:
        from pyomo.contrib.appsi.solvers import Highs
        mp2 = _pyomo_model(B, C, G, inv0)
        s = Highs()
        s.config.load_solution = False
        t1 = time.perf_counter()
        s.set_instance(mp2)
        export_appsi = time.perf_counter() - t1
    except Exception:
        pass
    return construct, export_lp, export_appsi


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--b", type=int, default=None)
    p.add_argument("--g", type=int, default=None)
    p.add_argument("--cycle", type=int, default=24)
    args = p.parse_args(argv)
    C = args.cycle
    sizes = [(args.b, C, args.g)] if (args.b and args.g) else [(365, C, 10), (365, C, 50), (1000, C, 50)]
    print(f"{'size B*C*G':16s} {'rows':>8s} {'linopy_tot':>11s} {'pyomo_lp':>9s} {'pyomo_appsi':>12s} "
          f"{'x(lp)':>6s} {'x(appsi)':>9s}")
    for (B, C, G) in sizes:
        inv0 = np.random.default_rng(0).uniform(0, 1, G)
        lc, le = linopy_endtoend(B, C, G, inv0)
        pc, plp, pap = pyomo_endtoend(B, C, G, inv0)
        lin_tot = lc + le
        pyo_lp = pc + plp
        pyo_ap = pc + pap
        print(f"{f'{B}x{C}x{G}':16s} {B*G:8d} {lin_tot:11.3f} {pyo_lp:9.3f} {pyo_ap:12.3f} "
              f"{pyo_lp/lin_tot:6.1f} {pyo_ap/lin_tot:9.1f}")
        print(f"  (linopy construct={lc:.3f}+export={le:.3f}; pyomo construct={pc:.3f}+lp={plp:.3f}+appsi={pap:.3f})")


if __name__ == "__main__":
    main()
