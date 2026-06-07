"""Nodal balance vs per-asset / arc balance: size and solve-time comparison.

The decomposition note (docs/decomposition.md, section 3) claims the per-asset /
arc-balance form describes the same feasible region as the nodal form (same
optimum), is slightly *larger* to build (it adds an injection variable and a
defining constraint per asset), and is not a standalone solver speed-up -- its
value is the block-angular structure it exposes for decomposition. This benchmark
tests that empirically on a synthetic multi-period transmission-and-storage model,
built two ways:

  * nodal   -- one balance per node: sum of the assets' contributions == demand.
  * arc     -- one injection variable and balance per asset, the node reduced to a
               flow-conservation constraint (sum of incident injections == 0). This
               is block-angular: each asset's variables and its injection-defining
               constraint form a block, coupled only through the node sums.

It reports the model size (variables / constraints), the build time and the solve
time for each, and checks the objective matches. Run: python balance_formulation.py
"""
import sys
import time

from pyomo.environ import (ConcreteModel, Var, Constraint, Objective, Reals,
                           NonNegativeReals, minimize, value, SolverFactory)


def _data(n_nodes, n_steps):
    nodes = list(range(n_nodes))
    steps = list(range(n_steps))
    lines = [(i, (i + 1) % n_nodes) for i in range(n_nodes)]      # a ring
    gcost = {n: 5.0 + n for n in nodes}
    gcap = {n: 60.0 for n in nodes}
    demand = {(n, t): 20.0 + 10.0 * ((n + t) % 3) for n in nodes for t in steps}
    fcap = 40.0
    sto_node = 0
    eff, smax = 0.9, 50.0
    return nodes, steps, lines, gcost, gcap, demand, fcap, sto_node, eff, smax


def build_nodal(n_nodes, n_steps):
    nodes, steps, lines, gcost, gcap, demand, fcap, sn, eff, smax = _data(n_nodes, n_steps)
    m = ConcreteModel()
    m.gen = Var(nodes, steps, within=NonNegativeReals, bounds=lambda mm, n, t: (0, gcap[n]))
    m.f = Var(range(len(lines)), steps, within=Reals, bounds=(-fcap, fcap))
    m.ch = Var(steps, within=NonNegativeReals, bounds=(0, smax))
    m.dis = Var(steps, within=NonNegativeReals, bounds=(0, smax))
    m.soc = Var(steps, within=NonNegativeReals, bounds=(0, smax))

    def bal(mm, n, t):
        inflow = sum(mm.f[li, t] for li, (i, j) in enumerate(lines) if j == n)
        outflow = sum(mm.f[li, t] for li, (i, j) in enumerate(lines) if i == n)
        sto = (mm.dis[t] - mm.ch[t]) if n == sn else 0.0
        return mm.gen[n, t] + inflow - outflow + sto == demand[(n, t)]
    m.bal = Constraint(nodes, steps, rule=bal)
    m.socbal = Constraint(steps, rule=lambda mm, t: mm.soc[t] == (
        (mm.soc[t - 1] if t > 0 else 0.5 * smax) + eff * mm.ch[t] - mm.dis[t] / eff))
    m.obj = Objective(expr=sum(gcost[n] * m.gen[n, t] for n in nodes for t in steps),
                      sense=minimize)
    return m


def build_arc(n_nodes, n_steps):
    nodes, steps, lines, gcost, gcap, demand, fcap, sn, eff, smax = _data(n_nodes, n_steps)
    m = ConcreteModel()
    m.gen = Var(nodes, steps, within=NonNegativeReals, bounds=lambda mm, n, t: (0, gcap[n]))
    m.f = Var(range(len(lines)), steps, within=Reals, bounds=(-fcap, fcap))
    m.ch = Var(steps, within=NonNegativeReals, bounds=(0, smax))
    m.dis = Var(steps, within=NonNegativeReals, bounds=(0, smax))
    m.soc = Var(steps, within=NonNegativeReals, bounds=(0, smax))
    # one injection variable per asset-at-node, with a per-asset defining constraint
    assets = ([("g", n, n) for n in nodes] + [("d", n, n) for n in nodes]
              + [("s", sn, sn)]
              + [("lf", li, i) for li, (i, j) in enumerate(lines)]
              + [("lt", li, j) for li, (i, j) in enumerate(lines)])
    m.inj = Var(range(len(assets)), steps, within=Reals)

    def define(mm, ai, t):
        kind, key, nd = assets[ai]
        if kind == "g":
            return mm.inj[ai, t] == mm.gen[key, t]
        if kind == "d":
            return mm.inj[ai, t] == -demand[(key, t)]
        if kind == "s":
            return mm.inj[ai, t] == mm.dis[t] - mm.ch[t]
        if kind == "lf":
            return mm.inj[ai, t] == -mm.f[key, t]
        return mm.inj[ai, t] == mm.f[key, t]
    m.define = Constraint(range(len(assets)), steps, rule=define)
    m.node = Constraint(nodes, steps, rule=lambda mm, n, t: sum(
        mm.inj[ai, t] for ai, (k, key, nd) in enumerate(assets) if nd == n) == 0)
    m.socbal = Constraint(steps, rule=lambda mm, t: mm.soc[t] == (
        (mm.soc[t - 1] if t > 0 else 0.5 * smax) + eff * mm.ch[t] - mm.dis[t] / eff))
    m.obj = Objective(expr=sum(gcost[n] * m.gen[n, t] for n in nodes for t in steps),
                      sense=minimize)
    return m


def _size(m):
    nv = sum(1 for _ in m.component_data_objects(Var))
    nc = sum(1 for _ in m.component_data_objects(Constraint))
    return nv, nc


def run(n_nodes, n_steps, solver):
    opt = SolverFactory(solver)
    out = {}
    for name, builder in (("nodal", build_nodal), ("arc", build_arc)):
        t0 = time.time()
        m = builder(n_nodes, n_steps)
        tb = time.time() - t0
        nv, nc = _size(m)
        t0 = time.time()
        opt.solve(m)
        ts = time.time() - t0
        out[name] = (nv, nc, tb, ts, float(value(m.obj)))
    return out


def main():
    solver = sys.argv[1] if len(sys.argv) > 1 else "appsi_highs"
    print(f"# nodal vs arc/asset balance, solver={solver}", flush=True)
    print(f"{'nodes':>5} {'steps':>5} {'form':>6} {'vars':>8} {'cons':>8} "
          f"{'build_s':>9} {'solve_s':>9} {'objective':>14}", flush=True)
    for n_nodes, n_steps in ((10, 24), (20, 168), (40, 168), (60, 336)):
        res = run(n_nodes, n_steps, solver)
        match = abs(res["nodal"][4] - res["arc"][4]) / (abs(res["nodal"][4]) + 1e-9) < 1e-6
        for form in ("nodal", "arc"):
            nv, nc, tb, ts, obj = res[form]
            print(f"{n_nodes:>5} {n_steps:>5} {form:>6} {nv:>8} {nc:>8} "
                  f"{tb:>9.3f} {ts:>9.3f} {obj:>14.2f}", flush=True)
        print(f"# {n_nodes}x{n_steps}: objective match = {match}", flush=True)


if __name__ == "__main__":
    main()
