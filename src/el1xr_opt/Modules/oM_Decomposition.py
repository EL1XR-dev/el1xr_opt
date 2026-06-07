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


def _solve_model(opt, mdl):
    """Solve and load a Pyomo model, with the appsi/strict-load fallback.

    appsi solvers raise on load if not optimal; ask not to auto-load and load
    explicitly so duals come through and a clear error is raised on failure.
    """
    from pyomo.environ import value  # noqa: F401  (kept local for symmetry)
    try:
        res = opt.solve(mdl)
    except (ValueError, RuntimeError):
        res = opt.solve(mdl, load_solutions=False)
        mdl.solutions.load_from(res)
    return res


def benders_solve(make_master, make_subproblem, blocks, config=None,
                  solver="appsi_highs", solve_blocks=None):
    """Generic multi-cut (L-shaped) Benders decomposition.

    Assumes relative complete recourse (every subproblem is feasible for any
    first-stage decision), so it adds optimality cuts only. The el1xr subproblems
    guarantee this with an elastic penalty relaxation (see :func:`el1xr_benders`),
    which turns any operating infeasibility into a high-cost recourse value whose
    fixing-constraint dual is a feasibility (steering) cut, so this loop needs no
    separate feasibility-cut handling. Returns a result dict with the objective,
    the first-stage solution, the iteration count and the final gap.

    Subproblems are independent given the master decision, so they can be solved in
    parallel. Pyomo solvers are not thread-safe (shared writer / tempfile / solver
    state), so parallelism is by process, not thread: pass ``solve_blocks``, a
    callable ``solve_blocks(x_hat) -> {block: (q_b, lam)}`` that solves the blocks
    however it likes (e.g. a pool of worker processes that each own and reuse their
    subproblems). When ``solve_blocks`` is given the subproblems are not built here
    (the pool owns them); when it is ``None`` the blocks are built and solved
    sequentially in-process. The result is identical either way.

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

    M = make_master()
    names = list(M["x"].keys())
    subs = None if solve_blocks is not None else {b: make_subproblem(b) for b in blocks}

    def _solve_sequential(x_hat):
        solved = {}
        for b in blocks:
            sub = subs[b]
            sub["set_xhat"](x_hat)
            _solve_model(opt, sub["model"])
            lam = {n: float(sub["model"].dual[sub["fix"][n]]) for n in names}
            solved[b] = (float(value(sub["obj"])), lam)
        return solved

    solve = solve_blocks if solve_blocks is not None else _solve_sequential

    best_ub = float("inf")
    gap = float("inf")
    it = 0
    for it in range(1, cfg.max_iterations + 1):
        _solve_model(opt, M["model"])
        lb = value(M["model"].obj)
        x_hat = {n: float(value(M["x"][n])) for n in names}
        theta_hat = {b: float(value(M["theta"][b])) for b in blocks}
        first_stage_cost = lb - sum(theta_hat.values())

        solved = solve(x_hat)                  # {block: (q_b, lam)}
        recourse = sum(q_b for q_b, _ in solved.values())

        ub = first_stage_cost + recourse
        best_ub = min(best_ub, ub)
        gap = abs(best_ub - lb) / (abs(best_ub) + 1e-12)
        if gap <= cfg.relative_gap:
            break

        # add an optimality cut per block: theta_b >= q_b + sum_n lam_n (x_n - x_hat_n)
        for b in blocks:
            q_b, lam = solved[b]
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
    """Build the el1xr model restricted to one scenario.

    Produces a clean single-scenario copy of the case -- the kept scenario is the
    only one in the scenario dimension dict, and every other scenario's rows are
    dropped from the data files -- then builds the model from it. This reads and
    builds only the kept scenario instead of reading the whole multi-scenario
    dataset and filtering it down, which is the bulk of a block build. The kept
    scenario's own data (including its probability, read unnormalised) is left
    untouched, so the subproblem is identical to the one the full build would
    produce for that scenario.
    """
    import os
    import shutil
    import tempfile
    import pandas as pd
    from .oM_Sequence import build_model

    work = tempfile.mkdtemp(prefix="benders_blk_")
    src = os.path.join(dir_name, case_name)
    dst = os.path.join(work, case_name)
    shutil.copytree(src, dst)

    # scenario dimension dict: keep only the kept scenario, so model.sc = {kept}
    # and every scenario-indexed set product is built for that one scenario.
    dpath = os.path.join(dst, f"oM_Dict_Scenario_{case_name}.csv")
    dd = pd.read_csv(dpath)
    scenarios = set(dd.iloc[:, 0].astype(str))
    dd[dd.iloc[:, 0] == keep_scenario].to_csv(dpath, index=False)

    # data files: drop the other scenarios' rows. The scenario is the 2nd index
    # column in the Scenario file and in every (period, scenario, load level) time
    # series. Detect that column by its content -- it holds scenario labels -- not
    # by position, because other files (e.g. the networks, indexed by node, node,
    # circuit) also have several leading index columns but no scenario index.
    for fname in os.listdir(dst):
        if not (fname.startswith("oM_Data_") and fname.endswith(f"_{case_name}.csv")):
            continue
        fpath = os.path.join(dst, fname)
        df = pd.read_csv(fpath, header=0)
        if df.shape[1] < 2:
            continue
        scen_col = df.columns[1]
        values = set(df[scen_col].astype(str).unique())
        if not values or not values.issubset(scenarios):
            continue                                   # 2nd column is not scenarios
        df[df[scen_col] == keep_scenario].to_csv(fpath, index=False)

    model = build_model(work, case_name, date)
    shutil.rmtree(work, ignore_errors=True)
    return model


def _build_window(dir_name, case_name, date, keep_scenario, level_names):
    """Build the el1xr model restricted to one scenario and to a window of load
    levels (Duration kept only for ``level_names``), for temporal block splitting.
    The window's first level then has ordinal 1, so its inventory balance uses the
    initial-inventory branch (the hook for injecting the incoming boundary)."""
    import os
    import shutil
    import tempfile
    import pandas as pd
    from .oM_Sequence import build_model

    work = tempfile.mkdtemp(prefix="benders_win_")
    src = os.path.join(dir_name, case_name)
    dst = os.path.join(work, case_name)
    shutil.copytree(src, dst)
    dpath = os.path.join(dst, f"oM_Dict_Scenario_{case_name}.csv")
    dd = pd.read_csv(dpath)
    scenarios = set(dd.iloc[:, 0].astype(str))
    dd[dd.iloc[:, 0] == keep_scenario].to_csv(dpath, index=False)
    for fname in os.listdir(dst):
        if not (fname.startswith("oM_Data_") and fname.endswith(f"_{case_name}.csv")):
            continue
        fpath = os.path.join(dst, fname)
        df = pd.read_csv(fpath, header=0)
        if df.shape[1] < 2:
            continue
        scen_col = df.columns[1]
        values = set(df[scen_col].astype(str).unique())
        if values and values.issubset(scenarios):
            df[df[scen_col] == keep_scenario].to_csv(fpath, index=False)
    dpath = os.path.join(dst, f"oM_Data_Duration_{case_name}.csv")
    dur = pd.read_csv(dpath)
    dur.loc[~dur[dur.columns[2]].isin(level_names), "Duration"] = float("nan")
    dur.to_csv(dpath, index=False)
    model = build_model(work, case_name, date)
    shutil.rmtree(work, ignore_errors=True)
    return model


def el1xr_temporal_benders(dir_name, case_name, date, n_time_blocks=2,
                           solver="appsi_highs", config=None):
    """Solve one (period, scenario) el1xr operating horizon by temporal Benders.

    The horizon is split into ``n_time_blocks`` contiguous time blocks coupled by
    the storage inventory at each boundary. The master holds the investment build
    fractions and the boundary inventory levels (linking variables, each shared by
    two adjacent blocks); each block is the operating model over its window with the
    investment and its incoming/outgoing boundary inventory fixed (the duals of the
    fixing constraints give the cuts), made always-feasible by the elastic penalty.

    The per-scenario fixed network charge does not split by time window, so it is
    counted once in the master and removed from each block's recourse. This MVP
    assumes hourly storage (cycle = 1), a single (period, scenario), and that the
    horizon-coupling peak charge is inactive (zero grid import) -- it asserts the
    last. Validate against the monolith (see tests/test_benders_temporal_el1xr.py).
    """
    from pyomo.environ import (ConcreteModel, Var, Constraint, ConstraintList, Param,
                               Objective, Suffix, Reals, Binary, UnitInterval,
                               NonNegativeReals, minimize, TransformationFactory)
    from .oM_Sequence import build_structure

    cfg = config or BendersConfig()
    penalty = float(cfg.extra.get("feasibility_penalty", 1e7))

    full = build_structure(dir_name, case_name, date)
    ps = list(full.ps)
    if len(ps) != 1:
        raise NotImplementedError("temporal Benders MVP handles a single (period, scenario)")
    p, sc = ps[0]
    egc, hgc = list(full.egc), list(full.hgc)
    egs, hgs = list(full.egs), list(full.hgs)
    levels = list(full.n)
    factor1 = float(full.factor1)
    period_weight = sum(float(full.Par['pDiscountFactor'][pp]) for pp in full.p)
    discount = float(full.Par['pDiscountFactor'][p])
    invcost = {("e", g): float(full.Par['pEleGenInvestCost'][g]) for g in egc}
    invcost.update({("h", g): float(full.Par['pHydGenInvestCost'][g]) for g in hgc})
    inv_names = list(invcost)
    for g in egs:
        if int(full.Par['pEleCycleTimeStep'][g]) != 1:
            raise NotImplementedError("temporal MVP assumes hourly storage (cycle=1)")
    for g in hgs:
        if int(full.Par['pHydCycleTimeStep'][g]) != 1:
            raise NotImplementedError("temporal MVP assumes hourly storage (cycle=1)")
    n0 = levels[0]
    initE = {g: float(full.Par['pEleInitialInventory'][g][p, sc, n0]) for g in egs}
    initH = {g: float(full.Par['pHydInitialInventory'][g][p, sc, n0]) for g in hgs}
    # storage capacity caps the reachable boundary inventory (so the hard boundary
    # tie is feasible); take the nominal max over the horizon.
    maxE = {g: max(float(full.Par['pEleMaxStorage'][g][p, sc, n]) for n in levels) for g in egs}
    maxH = {g: max(float(full.Par['pHydMaxStorage'][g][p, sc, n]) for n in levels) for g in hgs}
    nmonths = len(list(full.moy))
    netfix = sum(float(full.Par['pEleRetFastavgift'][er]) * factor1 * nmonths
                 * (1 + float(full.Par['pEleRetMoms'][er])) for er in full.er)

    # contiguous time windows
    K = max(1, n_time_blocks)
    size = (len(levels) + K - 1) // K
    windows = [w for w in (levels[i:i + size] for i in range(0, len(levels), size)) if w]
    K = len(windows)
    blocks = list(range(K))
    bnd_names = ([("Se", k, g) for k in range(K - 1) for g in egs]
                 + [("Sh", k, g) for k in range(K - 1) for g in hgs])

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
        # boundary inventory levels: no master cost, so initialise (cold start)
        m.Se = Var(range(max(K - 1, 1)), egs, within=NonNegativeReals,
                   bounds=lambda mm, k, g: (0, maxE[g]), initialize=lambda mm, k, g: initE[g])
        m.Sh = Var(range(max(K - 1, 1)), hgs, within=NonNegativeReals,
                   bounds=lambda mm, k, g: (0, maxH[g]), initialize=lambda mm, k, g: initH[g])
        for (kind, k, g) in bnd_names:
            x[(kind, k, g)] = m.Se[k, g] if kind == "Se" else m.Sh[k, g]
        m.theta = Var(blocks, within=Reals, bounds=(-1e9, 1e12), initialize=0.0)
        m.cuts = ConstraintList()
        inv = period_weight * factor1 * sum(invcost[nm] * x[nm] for nm in inv_names)
        m.obj = Objective(expr=inv + discount * netfix + sum(m.theta[b] for b in blocks),
                          sense=minimize)
        return {"model": m, "x": x, "theta": {b: m.theta[b] for b in blocks}, "cuts": m.cuts}

    def make_subproblem(block):
        k = block
        win = windows[k]
        a, b = win[0], win[-1]
        sub = _build_window(dir_name, case_name, date, sc, win)
        sub.dual = Suffix(direction=Suffix.IMPORT)
        sub._bxe = Param(egc, mutable=True, initialize=0.0)
        sub._bxh = Param(hgc, mutable=True, initialize=0.0)
        sub.bfix_e = Constraint(egc, rule=lambda mm, g: mm.vEleGenInvest[g] == mm._bxe[g])
        sub.bfix_h = Constraint(hgc, rule=lambda mm, g: mm.vHydGenInvest[g] == mm._bxh[g])
        # boundary copies for every boundary (fixed to the master value); only the
        # incoming (k-1) and outgoing (k) ones enter this block's constraints.
        sub._se = Param(range(max(K - 1, 1)), egs, mutable=True, initialize=0.0)
        sub._sh = Param(range(max(K - 1, 1)), hgs, mutable=True, initialize=0.0)
        sub.Secopy = Var(range(max(K - 1, 1)), egs, within=Reals)
        sub.Shcopy = Var(range(max(K - 1, 1)), hgs, within=Reals)
        sub.sefix = Constraint(range(max(K - 1, 1)), egs,
                               rule=lambda mm, kk, g: mm.Secopy[kk, g] == mm._se[kk, g])
        sub.shfix = Constraint(range(max(K - 1, 1)), hgs,
                               rule=lambda mm, kk, g: mm.Shcopy[kk, g] == mm._sh[kk, g])

        # incoming boundary (k > 0): replace the window's first-level inventory
        # balance (which uses the constant initial inventory) with one reading the
        # incoming boundary copy. Hourly cycle, so the window over the level is [a].
        def _rep_e(mm, g):
            if k == 0 or (p, sc, a, g) not in mm.eEleInventory:
                return Constraint.Skip
            return (mm.Secopy[k - 1, g] + mm.Par['pDuration'][p, sc, a] * (
                mm.vEleEnergyInflows[p, sc, a, g] - mm.vEleEnergyOutflows[p, sc, a, g]
                - mm.vEleTotalOutput[p, sc, a, g] * (1.0 / mm.Par['pEleGenEfficiency_discharge'][g])
                + mm.Par['pEleGenEfficiency_charge'][g] * mm.vEleTotalCharge[p, sc, a, g])
                == mm.vEleInventory[p, sc, a, g] + mm.vEleSpillage[p, sc, a, g])
        sub.rep_e = Constraint(egs, rule=_rep_e)

        def _rep_h(mm, g):
            if k == 0 or (p, sc, a, g) not in mm.eHydInventory:
                return Constraint.Skip
            return (mm.Shcopy[k - 1, g] + mm.Par['pDuration'][p, sc, a] * (
                mm.vHydEnergyInflows[p, sc, a, g] - mm.vHydEnergyOutflows[p, sc, a, g]
                - mm.vHydTotalOutput[p, sc, a, g]
                + mm.Par['pHydGenEfficiency'][g] * mm.vHydTotalCharge[p, sc, a, g])
                == mm.vHydInventory[p, sc, a, g] + mm.vHydSpillage[p, sc, a, g])
        sub.rep_h = Constraint(hgs, rule=_rep_h)
        if k > 0:
            for g in egs:
                if (p, sc, a, g) in sub.eEleInventory:
                    sub.eEleInventory[p, sc, a, g].deactivate()
            for g in hgs:
                if (p, sc, a, g) in sub.eHydInventory:
                    sub.eHydInventory[p, sc, a, g].deactivate()

        # outgoing boundary (k < K-1): tie the window's last inventory to the copy
        sub.out_e = Constraint(egs, rule=lambda mm, g: (
            mm.vEleInventory[p, sc, b, g] == mm.Secopy[k, g]
            if (k < K - 1 and (p, sc, b, g) in mm.vEleInventory) else Constraint.Skip))
        sub.out_h = Constraint(hgs, rule=lambda mm, g: (
            mm.vHydInventory[p, sc, b, g] == mm.Shcopy[k, g]
            if (k < K - 1 and (p, sc, b, g) in mm.vHydInventory) else Constraint.Skip))

        sub.eTotalSCost.deactivate()
        # elastic relaxation on the operating constraints (everything except the
        # fixing and boundary-coupling constraints) so the block is feasible for any
        # fixed master point. The boundary couplings stay HARD: the inventory must be
        # exactly the master value at the boundary (so it is conserved across the
        # split); feasibility for an unreachable boundary comes from the elastic
        # operating constraints (and the model's own ENS / spillage), and the
        # fixing-constraint duals carry the (feasibility) cut.
        keep_hard = ("bfix_e", "bfix_h", "sefix", "shfix",
                     "rep_e", "rep_h", "out_e", "out_h")
        targets = [c for c in sub.component_objects(Constraint, active=True)
                   if c.name not in keep_hard]
        TransformationFactory('core.add_slack_variables').apply_to(sub, targets=targets)
        slack_blk = sub._core_add_slack_variables
        slack_blk._slack_objective.deactivate()
        slack_sum = sum(v for v in slack_blk.component_data_objects(Var))
        sub.benders_obj = Objective(
            expr=discount * (sub.vTotalCComponent[p, sc] - sub.vTotalEleNetUseFixCost[p, sc]
                             - sub.vTotalRComponent[p, sc]) + penalty * slack_sum,
            sense=minimize)

        fix = {("e", g): sub.bfix_e[g] for g in egc}
        fix.update({("h", g): sub.bfix_h[g] for g in hgc})
        for (kind, kk, g) in bnd_names:
            fix[(kind, kk, g)] = sub.sefix[kk, g] if kind == "Se" else sub.shfix[kk, g]

        def set_xhat(x_hat):
            for g in egc:
                sub._bxe[g] = x_hat[("e", g)]
            for g in hgc:
                sub._bxh[g] = x_hat[("h", g)]
            for (kind, kk, g) in bnd_names:
                if kind == "Se":
                    sub._se[kk, g] = x_hat[(kind, kk, g)]
                else:
                    sub._sh[kk, g] = x_hat[(kind, kk, g)]

        xcopy = {("e", g): sub.vEleGenInvest[g] for g in egc}
        xcopy.update({("h", g): sub.vHydGenInvest[g] for g in hgc})
        return {"model": sub, "xcopy": xcopy, "fix": fix, "set_xhat": set_xhat,
                "obj": sub.benders_obj}

    return benders_solve(make_master, make_subproblem, blocks, config=cfg, solver=solver)


def _build_el1xr_subproblem(dir_name, case_name, date, block, egc, hgc, discount, penalty):
    """Build one (period, scenario) operating subproblem with the investment fixed.

    Top-level (not a closure) so worker processes can build it. Restricts the build
    to the block's scenario, adds the investment-fixing constraints (their duals are
    the cut subgradient), and the elastic penalty relaxation that makes the block
    feasible for any investment (see :func:`el1xr_benders`). Returns the same dict
    shape as the :func:`benders_solve` subproblem callback expects.
    """
    from pyomo.environ import (Constraint, Param, Objective, Suffix, Var, minimize,
                               TransformationFactory)
    p, sc = block
    sub = _build_block(dir_name, case_name, date, sc)
    sub.dual = Suffix(direction=Suffix.IMPORT)
    sub._bxe = Param(egc, mutable=True, initialize=0.0)
    sub._bxh = Param(hgc, mutable=True, initialize=0.0)
    sub.bfix_e = Constraint(egc, rule=lambda mm, g: mm.vEleGenInvest[g] == mm._bxe[g])
    sub.bfix_h = Constraint(hgc, rule=lambda mm, g: mm.vHydGenInvest[g] == mm._bxh[g])
    sub.eTotalSCost.deactivate()
    targets = [c for c in sub.component_objects(Constraint, active=True)
               if c.name not in ("bfix_e", "bfix_h")]
    TransformationFactory('core.add_slack_variables').apply_to(sub, targets=targets)
    slack_blk = sub._core_add_slack_variables
    slack_blk._slack_objective.deactivate()
    slack_sum = sum(v for v in slack_blk.component_data_objects(Var))
    sub.benders_obj = Objective(
        expr=discount[p] * (sub.vTotalCComponent[p, sc] - sub.vTotalRComponent[p, sc])
        + penalty * slack_sum,
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


def _benders_worker(conn, dir_name, case_name, date, my_blocks, egc, hgc,
                    discount, penalty, solver):
    """Persistent worker process: build the assigned blocks once, then on each
    message set the investment to x_hat, solve, and send back {block: (q_b, lam)}.
    A ``None`` message ends the loop. Reuses the built subproblems across Benders
    iterations, so the (expensive) build happens once per block."""
    from pyomo.environ import SolverFactory, value
    names = [("e", g) for g in egc] + [("h", g) for g in hgc]
    opt = SolverFactory(solver)
    subs = {b: _build_el1xr_subproblem(dir_name, case_name, date, b, egc, hgc,
                                       discount, penalty) for b in my_blocks}
    conn.send("ready")
    while True:
        x_hat = conn.recv()
        if x_hat is None:
            break
        out = {}
        for b in my_blocks:
            sub = subs[b]
            sub["set_xhat"](x_hat)
            _solve_model(opt, sub["model"])
            lam = {n: float(sub["model"].dual[sub["fix"][n]]) for n in names}
            out[b] = (float(value(sub["obj"])), lam)
        conn.send(out)
    conn.close()


def el1xr_benders(dir_name, case_name, date, solver="appsi_highs", config=None):
    """Solve the el1xr investment + operating model by Benders decomposition.

    Master: the investment build fractions plus a recourse variable per
    (period, scenario) block. Subproblem per block: the operating model restricted
    to that scenario, with the investment variables fixed (their fixing-constraint
    duals give the cut). Calls the validated :func:`benders_solve`. Returns its
    result dict. Validate against the monolithic optimum before trusting (see
    ``tests/test_benders_el1xr.py``)."""
    from pyomo.environ import (ConcreteModel, Var, ConstraintList, Objective, Reals,
                               Binary, UnitInterval, minimize)
    from .oM_Sequence import build_structure

    cfg = config or BendersConfig()
    # penalty on the elastic slacks added to the operating constraints (see
    # make_subproblem). Large vs any real operating cost so slack is used only when
    # the fixed investment is genuinely infeasible; configurable via config.extra.
    penalty = float(cfg.extra.get("feasibility_penalty", 1e7))

    # read only the structure (sets + parameters): the candidate sets, the block
    # list and the investment costs/flags. This skips a full operating-model build
    # that would be thrown away, which removes the serial floor on the parallel
    # speed-up (the subproblems are still built in full, per block).
    full = build_structure(dir_name, case_name, date)
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
        # The elastic-penalty relaxation that makes every block feasible for any
        # investment (so optimality cuts suffice) lives in the shared builder; see
        # _build_el1xr_subproblem and the module/docs notes on feasibility cuts.
        return _build_el1xr_subproblem(dir_name, case_name, date, block, egc, hgc,
                                       discount, penalty)

    # Sequential (default) vs parallel subproblem solves. The subproblems are
    # independent given the investment, so with n_workers > 1 they are solved in
    # worker processes (Pyomo solvers are not thread-safe). Each worker builds and
    # owns a round-robin slice of the blocks once and reuses them across iterations;
    # the master loop sends x_hat and collects (cost, duals). The result is
    # identical to the sequential solve.
    if cfg.n_workers > 1 and len(blocks) > 1:
        import multiprocessing as mp
        ctx = mp.get_context("spawn")
        nw = min(cfg.n_workers, len(blocks))
        assign = {w: blocks[w::nw] for w in range(nw)}
        procs = []
        for w in range(nw):
            parent, child = ctx.Pipe()
            pr = ctx.Process(target=_benders_worker,
                             args=(child, dir_name, case_name, date, assign[w], egc,
                                   hgc, discount, penalty, solver), daemon=True)
            pr.start()
            procs.append((pr, parent))
        for _, parent in procs:
            parent.recv()                       # "ready" once that worker has built

        def solve_blocks(x_hat):
            for _, parent in procs:
                parent.send(x_hat)
            merged = {}
            for _, parent in procs:
                merged.update(parent.recv())
            return merged

        try:
            return benders_solve(make_master, make_subproblem, blocks, config=cfg,
                                 solver=solver, solve_blocks=solve_blocks)
        finally:
            for _, parent in procs:
                try:
                    parent.send(None)
                except (BrokenPipeError, OSError):
                    pass
            for pr, _ in procs:
                pr.join(timeout=10)

    return benders_solve(make_master, make_subproblem, blocks, config=cfg, solver=solver)


def solve_benders(model, optmodel, solver, config: BendersConfig | None = None):
    """Deprecated alias kept for the original scaffold signature. Use
    :func:`el1xr_benders` (dir, case, date, ...) for the el1xr model."""
    raise NotImplementedError("use el1xr_benders(dir, case, date, solver, config)")
