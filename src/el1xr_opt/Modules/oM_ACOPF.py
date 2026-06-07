# Developed by: Erik F. Alvarez
#
# Electric Power System Unit
# RISE
# erik.alvarez@ri.se
#
# AC optimal power flow analysis module for el1xr_opt (Phase 5a).
#
# A standalone, single-phase (balanced) AC OPF that runs on a network snapshot:
# the buses and branches from a case's electricity-network data plus a set of
# nodal net injections (e.g. taken from a chosen period of a solved operational
# model). It is decoupled from the main linear/MILP solve on purpose — a full-year
# AC MINLP is intractable — so AC feasibility (voltages, losses, reactive power)
# is checked on selected snapshots instead.
#
# Two formulations, chosen by ``formulation``:
#   * "nlp"  — exact polar-form AC OPF (non-convex), solved with Ipopt. Works for
#              any topology (radial or meshed).
#   * "socp" — second-order-cone (branch-flow / DistFlow) relaxation, convex,
#              solved with Gurobi. Requires a radial network; it also returns the
#              relaxation gap (how far P^2+Q^2 is from l*v), the standard exactness
#              check.
#
# Network data uses the existing el1xr columns: branches indexed by
# (InitialNode, FinalNode, Circuit) with Reactance and (optionally) Resistance;
# a lossless line (no Resistance) is allowed but then there are no active losses.
#
# This is the Phase-5a baseline (single-phase). Three-phase unbalanced AC OPF
# (Phase 5c) is a separate, larger effort; see docs/scope_acopf_community.md.

import math

from pyomo.environ import (ConcreteModel, Var, Constraint, Objective, Reals,
                           NonNegativeReals, minimize, cos, sin, value, sqrt)


def build_branches(network_df):
    """Turn an el1xr ElectricityNetwork DataFrame into a list of branch dicts.

    Expects the (InitialNode, FinalNode, Circuit) multi-index (the unnamed index
    columns) and ``Reactance`` / optional ``Resistance`` columns. Per-unit values
    are used as given. A missing/zero reactance branch is skipped (not a real
    series element).
    """
    branches = []
    for idx, row in network_df.iterrows():
        i, j, c = idx if isinstance(idx, tuple) else (idx, None, None)
        x = float(row.get("Reactance", 0.0) or 0.0)
        if x == 0.0:
            continue
        r = row.get("Resistance", 0.0)
        r = 0.0 if (r is None or (isinstance(r, float) and math.isnan(r))) else float(r)
        ttc = float(row.get("TTC", 0.0) or 0.0)
        branches.append({"i": i, "j": j, "c": c, "r": r, "x": x, "ttc": ttc})
    return branches


def _buses(branches):
    bs = []
    for b in branches:
        for n in (b["i"], b["j"]):
            if n not in bs:
                bs.append(n)
    return bs


def _orient_radial(branches, slack):
    """Orient each branch parent->child away from the slack by BFS. Returns the
    oriented branch list (with 'up' = parent bus) or raises if the network is not
    a radial tree (needed by the DistFlow SOCP)."""
    adj = {}
    for k, b in enumerate(branches):
        adj.setdefault(b["i"], []).append((b["j"], k))
        adj.setdefault(b["j"], []).append((b["i"], k))
    seen = {slack}
    oriented = []
    queue = [slack]
    used = set()
    while queue:
        u = queue.pop(0)
        for v, k in adj.get(u, []):
            if k in used:
                continue
            if v in seen:
                raise ValueError("network is not radial (cycle found); use formulation='nlp'")
            used.add(k)
            seen.add(v)
            ob = dict(branches[k])
            ob["up"], ob["dn"] = u, v
            oriented.append(ob)
            queue.append(v)
    if len(oriented) != len(branches):
        raise ValueError("network is not radial (parallel/extra branches); use formulation='nlp'")
    return oriented


def solve_acopf_nlp(branches, Pd, Qd, slack, v0=1.0, vmin=0.9, vmax=1.1,
                    qlim=3.0, plim=10.0, solver="ipopt", init_v=None, init_th=None):
    """Exact polar-form AC OPF. Pd/Qd: dict bus->net load (p.u.). Returns a result
    dict (objective = total slack-bus injection ~ losses + net import).

    ``init_v`` / ``init_th`` give a warm start (bus -> value); on a stressed radial
    feeder a flat start often fails, so passing the SOC relaxation's voltages is
    the reliable way to converge.
    """
    buses = _buses(branches)
    # Series admittance y = 1/(r+jx) = gs + j bs (gs>0, bs<0). The bus-admittance
    # matrix has diagonal Y_ii = sum of series admittances, and off-diagonal
    # Y_ij = -y_ij. So the off-diagonal G/B used in the injection equations are the
    # NEGATED series values; the diagonal is the (positive) series sum.
    gs = {}
    bs = {}
    for br in branches:
        denom = br["r"] ** 2 + br["x"] ** 2
        gs[(br["i"], br["j"])] = br["r"] / denom
        bs[(br["i"], br["j"])] = -br["x"] / denom
    nbr = {n: [] for n in buses}
    for br in branches:
        nbr[br["i"]].append(br["j"])
        nbr[br["j"]].append(br["i"])

    def _series_g(i, j):
        return gs.get((i, j), gs.get((j, i), 0.0))

    def _series_b(i, j):
        return bs.get((i, j), bs.get((j, i), 0.0))

    def goff(i, j):
        return -_series_g(i, j)          # Ybus off-diagonal conductance

    def boff(i, j):
        return -_series_b(i, j)          # Ybus off-diagonal susceptance

    Gii = {n: sum(_series_g(n, m) for m in nbr[n]) for n in buses}
    Bii = {n: sum(_series_b(n, m) for m in nbr[n]) for n in buses}

    init_v = init_v or {}
    init_th = init_th or {}
    m = ConcreteModel()
    m.V = Var(buses, bounds=(vmin, vmax), initialize=lambda mm, n: init_v.get(n, 1.0))
    m.th = Var(buses, initialize=lambda mm, n: init_th.get(n, 0.0))
    m.Pg = Var(buses, bounds=(-plim, plim), initialize=0.0)
    m.Qg = Var(buses, bounds=(-qlim, qlim), initialize=0.0)
    m.V[slack].fix(v0)
    m.th[slack].fix(0.0)

    def pinj(mm, i):
        return mm.Pg[i] - Pd.get(i, 0.0) == mm.V[i] ** 2 * Gii[i] + sum(
            mm.V[i] * mm.V[j] * (goff(i, j) * cos(mm.th[i] - mm.th[j]) + boff(i, j) * sin(mm.th[i] - mm.th[j]))
            for j in nbr[i])
    m.pinj = Constraint(buses, rule=pinj)

    def qinj(mm, i):
        return mm.Qg[i] - Qd.get(i, 0.0) == -mm.V[i] ** 2 * Bii[i] + sum(
            mm.V[i] * mm.V[j] * (goff(i, j) * sin(mm.th[i] - mm.th[j]) - boff(i, j) * cos(mm.th[i] - mm.th[j]))
            for j in nbr[i])
    m.qinj = Constraint(buses, rule=qinj)
    # only the slack injects (a single supply point); other buses are loads
    for n in buses:
        if n != slack:
            m.Pg[n].fix(0.0)
            m.Qg[n].fix(0.0)
    m.obj = Objective(expr=m.Pg[slack], sense=minimize)

    from pyomo.environ import SolverFactory
    res = SolverFactory(solver).solve(m)
    return {
        "formulation": "nlp",
        "objective": float(value(m.obj)),
        "V": {n: float(value(m.V[n])) for n in buses},
        "theta": {n: float(value(m.th[n])) for n in buses},
        "solver_status": str(res.solver.termination_condition),
    }


def solve_acopf_socp(branches, Pd, Qd, slack, v0=1.0, vmin=0.9, vmax=1.1, solver="gurobi"):
    """Branch-flow (DistFlow) SOC relaxation on a radial network. Returns a result
    dict including the per-branch relaxation gap l*v - (P^2+Q^2) (0 = exact)."""
    ob = _orient_radial(branches, slack)
    buses = _buses(branches)
    children = {n: [] for n in buses}
    for k, br in enumerate(ob):
        children[br["up"]].append(k)

    m = ConcreteModel()
    m.K = range(len(ob))
    m.P = Var(m.K, within=Reals)            # active flow into branch k (from parent)
    m.Q = Var(m.K, within=Reals)
    m.l = Var(m.K, within=NonNegativeReals)  # squared current
    m.w = Var(buses, within=NonNegativeReals, initialize=1.0)   # squared voltage
    m.w[slack].fix(v0 ** 2)
    for n in buses:
        if n != slack:
            m.w[n].setlb(vmin ** 2)
            m.w[n].setub(vmax ** 2)

    # active/reactive balance at each downstream bus
    def pbal(mm, k):
        br = ob[k]
        dn = br["dn"]
        out = sum(mm.P[kk] for kk in children[dn])
        return mm.P[k] - br["r"] * mm.l[k] - out == Pd.get(dn, 0.0)
    m.pbal = Constraint(m.K, rule=pbal)

    def qbal(mm, k):
        br = ob[k]
        dn = br["dn"]
        out = sum(mm.Q[kk] for kk in children[dn])
        return mm.Q[k] - br["x"] * mm.l[k] - out == Qd.get(dn, 0.0)
    m.qbal = Constraint(m.K, rule=qbal)

    def volt(mm, k):
        br = ob[k]
        return mm.w[br["dn"]] == mm.w[br["up"]] - 2 * (br["r"] * mm.P[k] + br["x"] * mm.Q[k]) \
            + (br["r"] ** 2 + br["x"] ** 2) * mm.l[k]
    m.volt = Constraint(m.K, rule=volt)

    def soc(mm, k):
        br = ob[k]
        return mm.P[k] ** 2 + mm.Q[k] ** 2 <= mm.l[k] * mm.w[br["up"]]
    m.soc = Constraint(m.K, rule=soc)

    m.obj = Objective(expr=sum(ob[k]["r"] * m.l[k] for k in m.K), sense=minimize)  # total losses

    from pyomo.environ import SolverFactory
    res = SolverFactory(solver).solve(m)
    gap = {}
    for k in m.K:
        lhs = value(m.P[k]) ** 2 + value(m.Q[k]) ** 2
        rhs = value(m.l[k]) * value(m.w[ob[k]["up"]])
        gap[(ob[k]["up"], ob[k]["dn"])] = float(rhs - lhs)
    return {
        "formulation": "socp",
        "objective": float(value(m.obj)),
        "V": {n: math.sqrt(max(0.0, float(value(m.w[n])))) for n in buses},
        "losses": float(value(m.obj)),
        "relaxation_gap_max": max(gap.values()) if gap else 0.0,
        "relaxation_gap": gap,
        "solver_status": str(res.solver.termination_condition),
    }


def solve_acopf(network_df, Pd, Qd, slack, formulation="socp", warm_start=True, **kw):
    """Dispatch by formulation. Pd/Qd are dicts bus -> net load in per unit.

    For ``formulation='nlp'`` on a radial network the SOC relaxation is solved
    first (cheap, convex) and its voltages are used to warm-start the non-convex
    NLP, which otherwise often fails from a flat start on a stressed feeder.
    """
    branches = build_branches(network_df)
    if formulation == "socp":
        return solve_acopf_socp(branches, Pd, Qd, slack, **kw)
    if formulation == "nlp":
        if warm_start and "init_v" not in kw:
            try:
                socp = solve_acopf_socp(branches, Pd, Qd, slack,
                                        v0=kw.get("v0", 1.0),
                                        vmin=kw.get("vmin", 0.9), vmax=kw.get("vmax", 1.1))
                kw.setdefault("init_v", socp["V"])
            except Exception:
                pass            # non-radial or no SOC solver; fall back to flat start
        return solve_acopf_nlp(branches, Pd, Qd, slack, **kw)
    raise ValueError(f"unknown AC OPF formulation '{formulation}' (use 'socp' or 'nlp')")


def write_acopf_results(db_path, case, result):
    """Append AC OPF results (per-bus voltages + summary) to a DuckDB file."""
    import duckdb
    import pandas as pd
    volt = pd.DataFrame({"bus": list(result["V"].keys()),
                         "voltage_pu": list(result["V"].values())})
    summary = pd.DataFrame({
        "key": ["case", "formulation", "objective", "solver_status", "relaxation_gap_max"],
        "value": [case, result["formulation"], result["objective"],
                  result.get("solver_status", ""), result.get("relaxation_gap_max", "")],
    })
    con = duckdb.connect(db_path)
    try:
        import duckdb as _d
        _d.from_df(volt, connection=con).create("oM_Result_ACOPF_Voltage")
        _d.from_df(summary, connection=con).create("oM_Result_ACOPF_Summary")
    finally:
        con.close()
    return db_path
