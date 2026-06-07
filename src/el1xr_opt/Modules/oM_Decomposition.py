"""Decomposition and parallelization groundwork (scaffold).

See ``docs/decomposition.md`` for the design. This module marks out the block
structure the model can be split along and gives a usable block partition, so
that a Benders (and later Dantzig-Wolfe / column-generation) solver and parallel
model building can be built on top. The actual decomposition loop is not
implemented yet; the relevant entry points raise ``NotImplementedError``.

What is real now:
  * ``partition_blocks`` returns the independent operating blocks of the problem.
  * ``first_stage_components`` names the complicating and linking variables.

What is a stub:
  * ``BendersConfig`` / ``solve_benders`` — the place to implement the loop,
    mirroring openTEPES ``openTEPES_ProblemSolvingBenders``.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Block:
    """One independent operating block of the problem.

    A block is solved on its own given the first-stage (investment) decisions.
    ``load_levels`` is the slice of the time axis the block covers; for a pure
    period/scenario split it is the whole horizon, for a temporal split it is one
    time block.
    """
    period: object
    scenario: object
    load_levels: tuple
    index: int


def partition_blocks(periods, scenarios, load_levels, n_time_blocks: int = 1) -> list:
    """Split the problem into independent operating blocks.

    One block per ``(period, scenario)`` and, if ``n_time_blocks > 1``, per
    contiguous chunk of the time axis. The blocks are independent given the
    investment decisions (and, across time blocks, given the storage level at the
    block boundaries), so they can be built and solved in parallel.

    Returns a list of :class:`Block`. This is the partition step that runs before
    model building.
    """
    periods = list(periods)
    scenarios = list(scenarios)
    levels = list(load_levels)
    if n_time_blocks < 1:
        raise ValueError("n_time_blocks must be >= 1")

    # Contiguous, near-equal chunks of the time axis.
    size = max(1, (len(levels) + n_time_blocks - 1) // n_time_blocks)
    chunks = [tuple(levels[i:i + size]) for i in range(0, len(levels), size)] or [()]

    blocks = []
    idx = 0
    for p in periods:
        for sc in scenarios:
            for chunk in chunks:
                blocks.append(Block(period=p, scenario=sc, load_levels=chunk, index=idx))
                idx += 1
    return blocks


def first_stage_components() -> dict:
    """Names of the variables that couple the blocks.

    * ``complicating`` — first-stage decisions shared by every block (the Benders
      master variables): the investment / sizing build fractions.
    * ``linking`` — variables shared only between consecutive time blocks when the
      time axis is split: the storage inventory at each block boundary.
    """
    return {
        "complicating": ["vEleGenInvest", "vHydGenInvest", "vTotalICost"],
        "linking": ["vEleInventory", "vHydInventory"],
    }


@dataclass
class BendersConfig:
    """Settings for a (future) Benders solve."""
    max_iterations: int = 50
    relative_gap: float = 1e-3
    n_workers: int = 1                     # parallel subproblem solves
    n_time_blocks: int = 1                 # 1 = split by (period, scenario) only
    extra: dict = field(default_factory=dict)


def benders_solve(make_master, make_subproblem, blocks, config=None,
                  solver="appsi_highs"):
    """Generic multi-cut (L-shaped) Benders decomposition.

    Assumes relative complete recourse (subproblems are always feasible — true for
    the el1xr operating model thanks to energy-not-served), so it adds optimality
    cuts only. Returns a result dict with the objective, the first-stage solution,
    the iteration count and the final gap.

    Callbacks return plain Pyomo objects (so this works for the el1xr blocks or any
    two-stage stochastic program). ``make_master()`` returns a dict with keys
    ``model`` (master, minimise first-stage cost + sum theta), ``x``
    (name -> first-stage Var), ``theta`` (block -> recourse Var) and ``cuts`` (a
    ConstraintList the solver appends optimality cuts to). ``make_subproblem(block)``
    returns a dict with keys ``model`` (the operating subproblem), ``xcopy``
    (name -> free copy of the first-stage Var), ``fix`` (name -> Constraint fixing
    the copy to a mutable-Param value, whose dual is the cut subgradient),
    ``set_xhat`` (callable setting the fixing-constraint values) and ``obj`` (the
    subproblem Objective). The subproblem must carry a ``dual`` Suffix.
    """
    from pyomo.environ import SolverFactory, value
    cfg = config or BendersConfig()
    opt = SolverFactory(solver)

    def _solve(mdl):
        # appsi solvers raise on load if not optimal; ask not to auto-load and load
        # explicitly so duals come through and a clear error is raised on failure.
        try:
            res = opt.solve(mdl)
        except (ValueError, RuntimeError):
            res = opt.solve(mdl, load_solutions=False)
            mdl.solutions.load_from(res)
        return res

    M = make_master()
    subs = {b: make_subproblem(b) for b in blocks}
    names = list(M["x"].keys())

    best_ub = float("inf")
    gap = float("inf")
    it = 0
    for it in range(1, cfg.max_iterations + 1):
        _solve(M["model"])
        lb = value(M["model"].obj)
        x_hat = {n: float(value(M["x"][n])) for n in names}
        theta_hat = {b: float(value(M["theta"][b])) for b in blocks}
        first_stage_cost = lb - sum(theta_hat.values())

        recourse = 0.0
        new_cuts = []
        for b in blocks:
            sub = subs[b]
            sub["set_xhat"](x_hat)
            _solve(sub["model"])
            q_b = float(value(sub["obj"]))
            recourse += q_b
            lam = {n: float(sub["model"].dual[sub["fix"][n]]) for n in names}
            new_cuts.append((b, q_b, lam))

        ub = first_stage_cost + recourse
        best_ub = min(best_ub, ub)
        gap = abs(best_ub - lb) / (abs(best_ub) + 1e-12)
        if gap <= cfg.relative_gap:
            break

        # add an optimality cut per block: theta_b >= q_b + sum_n lam_n (x_n - x_hat_n)
        for (b, q_b, lam) in new_cuts:
            M["cuts"].add(
                M["theta"][b] >= q_b + sum(lam[n] * (M["x"][n] - x_hat[n]) for n in names))

    return {
        "objective": best_ub,
        "lower_bound": lb,
        "x": x_hat,
        "iterations": it,
        "gap": gap,
        "converged": gap <= cfg.relative_gap,
    }


def _build_block(dir_name, case_name, date, keep_scenario):
    """Build the el1xr model restricted to one scenario, by copying the case and
    zeroing the probability of every other scenario (so only the kept scenario's
    operating model is built). Reuses the validated full build."""
    import os
    import shutil
    import tempfile
    import pandas as pd
    from .oM_Sequence import build_model

    work = tempfile.mkdtemp(prefix="benders_blk_")
    src = os.path.join(dir_name, case_name)
    dst = os.path.join(work, case_name)
    shutil.copytree(src, dst)
    sp = os.path.join(dst, f"oM_Data_Scenario_{case_name}.csv")
    df = pd.read_csv(sp)
    scen_col = df.columns[1]
    df.loc[df[scen_col] != keep_scenario, "Probability"] = 0.0
    df.to_csv(sp, index=False)
    model = build_model(work, case_name, date)
    shutil.rmtree(work, ignore_errors=True)
    return model


def el1xr_benders(dir_name, case_name, date, solver="appsi_highs", config=None):
    """Solve the el1xr investment + operating model by Benders decomposition.

    Master: the investment build fractions plus a recourse variable per
    (period, scenario) block. Subproblem per block: the operating model restricted
    to that scenario, with the investment variables fixed (their fixing-constraint
    duals give the cut). Calls the validated :func:`benders_solve`. Returns its
    result dict. Validate against the monolithic optimum before trusting (see
    ``tests/test_benders_el1xr.py``)."""
    from pyomo.environ import (ConcreteModel, Var, Constraint, ConstraintList, Param,
                               Objective, Suffix, Reals, Binary, UnitInterval, minimize)
    from .oM_Sequence import build_model

    cfg = config or BendersConfig()

    # one full build to read the investment structure and the block list
    full = build_model(dir_name, case_name, date)
    egc, hgc = list(full.egc), list(full.hgc)
    blocks = list(full.ps)                                   # (period, scenario) tuples
    factor1 = float(full.factor1)
    period_weight = sum(float(full.Par['pDiscountFactor'][p]) for p in full.p)
    discount = {p: float(full.Par['pDiscountFactor'][p]) for p in full.p}
    invcost = {("e", g): float(full.Par['pEleGenInvestCost'][g]) for g in egc}
    invcost.update({("h", g): float(full.Par['pHydGenInvestCost'][g]) for g in hgc})
    names = list(invcost)

    def _binary(kind, g):
        key = 'pEleGenBinaryInvestment' if kind == "e" else 'pHydGenBinaryInvestment'
        try:
            return int(full.Par[key][g]) == 1
        except (KeyError, TypeError):
            return False

    def make_master():
        m = ConcreteModel()
        m.xe = Var(egc, within=UnitInterval)
        m.xh = Var(hgc, within=UnitInterval)
        for g in egc:
            if _binary("e", g):
                m.xe[g].domain = Binary
        for g in hgc:
            if _binary("h", g):
                m.xh[g].domain = Binary
        x = {("e", g): m.xe[g] for g in egc}
        x.update({("h", g): m.xh[g] for g in hgc})
        m.theta = Var(blocks, within=Reals, bounds=(-1e9, 1e12))   # recourse cost-to-go
        m.cuts = ConstraintList()
        inv = period_weight * factor1 * sum(invcost[nm] * x[nm] for nm in names)
        m.obj = Objective(expr=inv + sum(m.theta[b] for b in blocks), sense=minimize)
        return {"model": m, "x": x, "theta": {b: m.theta[b] for b in blocks}, "cuts": m.cuts}

    def make_subproblem(block):
        p, sc = block
        sub = _build_block(dir_name, case_name, date, sc)
        sub.dual = Suffix(direction=Suffix.IMPORT)
        sub._bxe = Param(egc, mutable=True, initialize=0.0)
        sub._bxh = Param(hgc, mutable=True, initialize=0.0)
        sub.bfix_e = Constraint(egc, rule=lambda mm, g: mm.vEleGenInvest[g] == mm._bxe[g])
        sub.bfix_h = Constraint(hgc, rule=lambda mm, g: mm.vHydGenInvest[g] == mm._bxh[g])
        sub.eTotalSCost.deactivate()
        sub.benders_obj = Objective(
            expr=discount[p] * (sub.vTotalCComponent[p, sc] - sub.vTotalRComponent[p, sc]),
            sense=minimize)
        fix = {("e", g): sub.bfix_e[g] for g in egc}
        fix.update({("h", g): sub.bfix_h[g] for g in hgc})

        def set_xhat(x_hat):
            for g in egc:
                sub._bxe[g] = x_hat[("e", g)]
            for g in hgc:
                sub._bxh[g] = x_hat[("h", g)]

        xcopy = {("e", g): sub.vEleGenInvest[g] for g in egc}
        xcopy.update({("h", g): sub.vHydGenInvest[g] for g in hgc})
        return {"model": sub, "xcopy": xcopy, "fix": fix, "set_xhat": set_xhat,
                "obj": sub.benders_obj}

    return benders_solve(make_master, make_subproblem, blocks, config=cfg, solver=solver)


def solve_benders(model, optmodel, solver, config: BendersConfig | None = None):
    """Deprecated alias kept for the original scaffold signature. Use
    :func:`el1xr_benders` (dir, case, date, ...) for the el1xr model."""
    raise NotImplementedError("use el1xr_benders(dir, case, date, solver, config)")
