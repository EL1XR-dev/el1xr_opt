# Developed by: Erik F. Alvarez
#
# Electric Power System Unit
# RISE
# erik.alvarez@ri.se
#
# Unbalanced linear OPF (LinDist3Flow) for el1xr_opt (architecture Stage C).
#
# LinDist3Flow is the linearised three-phase branch-flow model: per-phase squared
# voltages and active/reactive flows on a radial feeder, with a linear voltage-drop
# law that keeps the phase coupling (the 3x3 line impedance) to first order and
# drops the loss term. It is therefore an **LP** — unlike the exact unbalanced AC
# OPF (NLP/SOCP, the PowerModelsDistribution.jl path of Phase 5c) — so it can be
# built by linopy and solved by HiGHS, and it is the in-Python "linear unbalanced"
# screening option referred to by the network-mode catalogue (oM_Features).
#
# This is a standalone analysis module (like oM_ACOPF): it builds its own Pyomo
# model on a network snapshot (buses, 3-phase branches, per-phase nodal loads) and
# returns per-phase voltages. It does not touch the main operational model.
#
# Voltage-drop law (per branch i->j, 3-vector of squared voltages w):
#     w_j = w_i - (A_P @ P_ij + A_Q @ Q_ij)
# where, for the branch 3x3 resistance R and reactance X (entries r_pq, x_pq over
# phases a,b,c) and s3 = sqrt(3), the LinDist3Flow coupling matrices are
#     A_P = [[ 2 r_aa,        -r_ab+s3 x_ab, -r_ac-s3 x_ac],
#            [-r_ba-s3 x_ba,   2 r_bb,       -r_bc+s3 x_bc],
#            [-r_ca+s3 x_ca,  -r_cb-s3 x_cb,  2 r_cc]]
#     A_Q = [[ 2 x_aa,        -x_ab-s3 r_ab, -x_ac+s3 r_ac],
#            [-x_ba+s3 r_ba,   2 x_bb,       -x_bc-s3 r_bc],
#            [-x_ca-s3 r_ca,  -x_cb+s3 r_cb,  2 x_cc]]
# (Arnold/Sankur form.) For a balanced feeder with diagonal impedance this reduces
# to the per-phase single-phase LinDistFlow w_j = w_i - 2(r P + x Q), which is the
# correctness check used in the tests. The off-diagonal (mutual) terms are the
# genuinely three-phase part; validating them against OpenDSS / PMD.jl is the
# Phase-5c follow-on.

import math

from pyomo.environ import (ConcreteModel, Var, Constraint, Objective, Reals,
                           NonNegativeReals, minimize, value)

PHASES = ("a", "b", "c")
_S3 = math.sqrt(3.0)


def coupling_matrices(R, X):
    """Build the LinDist3Flow A_P, A_Q 3x3 matrices from branch R, X (3x3 each).

    R, X are dicts or 3x3 nested lists indexed by phase order (a,b,c).
    Returns (A_P, A_Q) as dict-of-dicts keyed by (row_phase, col_phase).
    """
    def get(M, p, q):
        if isinstance(M, dict):
            return float(M.get((p, q), 0.0))
        i, j = PHASES.index(p), PHASES.index(q)
        return float(M[i][j])

    A_P, A_Q = {}, {}
    for p in PHASES:
        for q in PHASES:
            r, x = get(R, p, q), get(X, p, q)
            if p == q:
                A_P[(p, q)] = 2.0 * r
                A_Q[(p, q)] = 2.0 * x
            else:
                # sign of the sqrt(3) cross term depends on phase order (p before q
                # in a,b,c sequence vs after); use the cyclic convention.
                seq = (PHASES.index(q) - PHASES.index(p)) % 3 == 1  # p->q forward in a,b,c
                sp = 1.0 if seq else -1.0
                A_P[(p, q)] = -r + sp * _S3 * x
                A_Q[(p, q)] = -x - sp * _S3 * r
    return A_P, A_Q


def _orient_radial(branches, slack):
    """Orient branches parent->child away from the slack (BFS); raise if not radial."""
    adj = {}
    for k, b in enumerate(branches):
        adj.setdefault(b["i"], []).append((b["j"], k))
        adj.setdefault(b["j"], []).append((b["i"], k))
    seen, used, oriented, queue = {slack}, set(), [], [slack]
    while queue:
        u = queue.pop(0)
        for v, k in adj.get(u, []):
            if k in used:
                continue
            if v in seen:
                raise ValueError("network is not radial; LinDist3Flow needs a radial feeder")
            used.add(k)
            seen.add(v)
            ob = dict(branches[k])
            ob["up"], ob["dn"] = u, v
            oriented.append(ob)
            queue.append(v)
    return oriented


def solve_lindist3flow(branches, loads, slack, v0=1.0, solver="appsi_highs"):
    """Solve the LinDist3Flow LP on a radial three-phase feeder.

    branches: list of dicts {i, j, R, X} with 3x3 R/X (ohm or pu, consistent).
    loads:    dict bus -> dict phase -> (P, Q) net load (consistent units).
    Returns dict bus -> dict phase -> voltage magnitude (pu, = sqrt(w)).
    """
    ob = _orient_radial(branches, slack)
    buses = []
    for b in branches:
        for n in (b["i"], b["j"]):
            if n not in buses:
                buses.append(n)
    children = {n: [] for n in buses}
    for k, b in enumerate(ob):
        children[b["up"]].append(k)
    A = [coupling_matrices(b["R"], b["X"]) for b in ob]

    m = ConcreteModel()
    m.K = range(len(ob))
    idxKP = [(k, p) for k in m.K for p in PHASES]
    idxBP = [(n, p) for n in buses for p in PHASES]
    m.P = Var(idxKP, within=Reals)          # active flow into branch k, per phase
    m.Q = Var(idxKP, within=Reals)
    m.w = Var(idxBP, within=NonNegativeReals, initialize=v0 ** 2)
    for p in PHASES:
        m.w[(slack, p)].fix(v0 ** 2)

    def pbal(mm, k, p):
        dn = ob[k]["dn"]
        out = sum(mm.P[(kk, p)] for kk in children[dn])
        Pd = loads.get(dn, {}).get(p, (0.0, 0.0))[0]
        return mm.P[(k, p)] - out == Pd
    m.pbal = Constraint(idxKP, rule=pbal)

    def qbal(mm, k, p):
        dn = ob[k]["dn"]
        out = sum(mm.Q[(kk, p)] for kk in children[dn])
        Qd = loads.get(dn, {}).get(p, (0.0, 0.0))[1]
        return mm.Q[(k, p)] - out == Qd
    m.qbal = Constraint(idxKP, rule=qbal)

    def volt(mm, k, p):
        AP, AQ = A[k]
        up = ob[k]["up"]
        drop = sum(AP[(p, q)] * mm.P[(k, q)] + AQ[(p, q)] * mm.Q[(k, q)] for q in PHASES)
        return mm.w[(ob[k]["dn"], p)] == mm.w[(up, p)] - drop
    m.volt = Constraint(idxKP, rule=volt)

    # well-posed LP: minimise total substation injection (the head-of-feeder flows)
    head = [k for k in m.K if ob[k]["up"] == slack]
    m.obj = Objective(expr=sum(m.P[(k, p)] for k in head for p in PHASES), sense=minimize)

    from pyomo.environ import SolverFactory
    SolverFactory(solver).solve(m)
    return {n: {p: math.sqrt(max(0.0, float(value(m.w[(n, p)])))) for p in PHASES} for n in buses}


def balanced_branch(r, x, n_buses=None):
    """Helper: a diagonal (uncoupled) balanced 3x3 R, X from scalars r, x."""
    R = [[r if i == j else 0.0 for j in range(3)] for i in range(3)]
    X = [[x if i == j else 0.0 for j in range(3)] for i in range(3)]
    return R, X
