"""Benders decomposition and parallel block solving.

See ``docs/decomposition.md`` for the design and ``docs/rst/user-guide/decomposition.rst``
for the user-facing overview. The model is block-angular -- investment is the first
stage, the operating problem separates by ``(period, scenario)`` and (for long horizons)
by time window, with storage coupling the time windows -- so it can be solved by Benders
instead of monolithically, reaching the same optimum.

Implemented and validated against the monolith:
  * ``benders_solve`` -- the generic multi-cut L-shaped method (optimality cuts only,
    with an elastic penalty making every block feasible for any first-stage decision).
  * ``el1xr_benders`` -- the el1xr investment/operating split, with optional
    process-parallel subproblem solves (``BendersConfig.n_workers``).
  * ``el1xr_temporal_benders`` -- splits one operating horizon into time windows coupled
    by the storage inventory at each boundary, with the fixed network charge counted once
    in the master and the peak-demand charge handled as a threshold-LP linking variable.
  * ``partition_blocks`` / ``first_stage_components`` -- the block partition and the
    complicating / linking variable names.

The only stub is ``solve_benders(model, ...)``, a deprecated alias kept for the original
scaffold signature; use ``el1xr_benders(dir, case, date, ...)`` instead.
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

    Robustness: HiGHS occasionally returns a spurious solver-ERROR status (a
    presolve/solve internal error, distinct from a real infeasible/unbounded result)
    on an otherwise solvable master MILP. It is platform/version dependent -- seen on
    the CI runner for the heat-storage temporal-Benders master, never locally. When the
    strict load fails on such a status, retry the solve with fallback option sets that
    take different algorithmic paths and clear the spurious error without changing the
    optimum. The retries run only after a solve has already failed, so they cannot
    affect the normal path; if all retries also fail the last error propagates.
    """
    from pyomo.environ import value  # noqa: F401  (kept local for symmetry)
    try:
        return opt.solve(mdl)
    except (ValueError, RuntimeError):
        res = opt.solve(mdl, load_solutions=False)
    try:
        mdl.solutions.load_from(res)
        return res
    except ValueError:
        pass
    # Spurious HiGHS error: retry with progressively different option sets.
    # Each set takes a different algorithmic path; the first that succeeds wins.
    # The last entry is tried without a catching except so its error propagates.
    _FALLBACKS = (
        {"presolve": "off"},
        {"presolve": "off", "solver": "simplex"},
    )
    for i, extra in enumerate(_FALLBACKS):
        saved = {k: opt.options[k] for k in extra if k in opt.options}
        new_keys = [k for k in extra if k not in opt.options]
        opt.options.update(extra)
        is_last = i == len(_FALLBACKS) - 1
        try:
            res = opt.solve(mdl, load_solutions=False)
            mdl.solutions.load_from(res)
            return res
        except (ValueError, RuntimeError):
            if is_last:
                raise
        finally:
            for k in new_keys:
                try:
                    del opt.options[k]
                except (KeyError, TypeError):
                    pass
            opt.options.update(saved)


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
    # Subproblems carry a large elastic penalty on slack variables. At a loose primal
    # feasibility tolerance the solver drifts those slacks just below their zero lower
    # bound, which perturbs the recourse solution and stalls convergence. A tight
    # primal tolerance on the subproblem solves keeps the slacks clean. (The master
    # has no slacks; tightening its tolerances can make some solvers error, so it
    # keeps the defaults.)
    opt_sub = SolverFactory(solver)
    sub_tol = float(cfg.extra.get("sub_primal_tol", 1e-8))
    _name = str(solver).lower()
    if "gurobi" in _name:
        opt_sub.options.update({"FeasibilityTol": sub_tol})
    elif "highs" in _name:
        opt_sub.options.update({"primal_feasibility_tolerance": sub_tol})

    M = make_master()
    names = list(M["x"].keys())
    subs = None if solve_blocks is not None else {b: make_subproblem(b) for b in blocks}

    def _solve_sequential(x_hat):
        solved = {}
        for b in blocks:
            sub = subs[b]
            sub["set_xhat"](x_hat)
            _solve_model(opt_sub, sub["model"])
            lam = {n: float(sub["model"].dual[sub["fix"][n]]) for n in names}
            qb = sub["recourse"]() if "recourse" in sub else float(value(sub["obj"]))
            solved[b] = (qb, lam)
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
        if cfg.extra.get("verbose"):
            print(f"  benders it {it:3d}: lb={lb:.4f} ub={ub:.4f} best_ub={best_ub:.4f} gap={gap:.2e}")
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
    counted once in the master and removed from each block's recourse. The peak
    demand charge (the per-month sum of the N largest grid imports) is the other
    horizon-coupling cost; it is reformulated as a threshold-LP whose scalar
    threshold per (month, retailer) is a master linking variable -- the master holds
    N*t and the peak coefficient, each window adds its own sum_n (import_n - t)_+.
    With the grid import chosen by the optimiser (not pinned), the battery shaves the
    import peak across the window boundaries, so the storage-boundary coupling and
    the peak threshold are active at once; this reproduces the binary monolith exactly
    (tests/test_benders_temporal_el1xr.py::...endogenous_import...).

    Transversality. The split couples the windows only through storage inventory and
    the registered aggregate costs, so it is transversal to the network
    representation (single-node / DC / linear three-phase -- the network mode changes
    a window's own constraints, not the coupling) and to the hydrogen sector (no
    horizon-coupling aggregate cost). The heat sector is handled too: its operating
    cost decomposes per window and is added to the recourse, and its thermal store is
    coupled by a boundary inventory (the St master variable, the analogue of Se / Sh
    for electricity / hydrogen storage). Still refused rather than mis-solved: any new
    sector aggregate charge that is not a plain sum over load levels and is not in the
    horizon-coupling registry (a constant or threshold charge must be registered, like
    the fixed network charge and the peak). This MVP also assumes hourly storage
    (cycle = 1), a single (period, scenario), and Hourly power tariffs (it raises on a
    Daily peak charge).
    """
    from pyomo.environ import (ConcreteModel, Var, Constraint, ConstraintList, Param,
                               Objective, Suffix, Reals, Binary, UnitInterval,
                               NonNegativeReals, minimize, value, TransformationFactory)
    from .oM_Sequence import build_structure

    cfg = config or BendersConfig()
    # Penalty on the elastic feasibility slacks, kept well above the model's own
    # recourse marginal (ENS cost) so a slack is never preferred to real recourse.
    # The recourse value reported to the Benders bound clamps the slack penalty to
    # genuine (positive) slack (see make_subproblem.recourse_value), so this large
    # penalty does not poison the bound through the solver's feasibility-tolerance
    # drift -- the penalty only steers the solve.
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
    # heat thermal storage couples the windows like electricity/hydrogen storage, so its
    # boundary inventory is a master linking variable too. load_heat_data reads the heat
    # set and bounds onto the structure model (it is a no-op -- hts stays empty -- for a
    # case with no heat sector, so this changes nothing for electricity/hydrogen cases).
    # Heat inventory is hourly (inv[n] = prev + eff*charge - discharge, no cycle step),
    # so it needs no cycle guard.
    from .oM_HeatSector import load_heat_data
    load_heat_data(full, dir_name, case_name)
    hts = list(getattr(full, "hts", []) or [])
    maxHt = {s: float(full.Par['pHeatStoMax'][s]) for s in hts}
    initHt = {s: float(full.Par['pHeatStoInitial'][s]) for s in hts}
    heat_eff = {s: float(full.Par['pHeatStoEff'][s]) for s in hts}
    # Horizon-coupling aggregate costs -- the per-(period, scenario) charges that do
    # NOT split by time window -- are described by the cost registry
    # (oM_Features.seed_horizon_coupling), not hard-coded here, so the split carries no
    # sector-specific names. Two shapes:
    #   * "constant" (the fixed network charge): counted once in the master, removed
    #     from each window's recourse;
    #   * "threshold" (the peak demand charge -- the per-subgroup sum of the N largest
    #     of a metered quantity): reformulated as a threshold-LP whose scalar threshold
    #     per (subgroup, item) is a master linking variable, using the identity
    #       sum of N largest of {x_n} = min over t of [ N*t + sum_n (x_n - t)_+ ].
    #     The master holds N*t and the coefficient; each window adds its own
    #     sum_n (x_n - t)_+. This is a pure LP and, the peak being a positive cost being
    #     minimised, reproduces the binary top-N selection exactly (validated against
    #     the binary monolith in tests/test_benders_temporal_el1xr.py).
    # Everything else (psn/psd costs and the "ps" terms that are plain sums over load
    # levels) splits by window on its own. A new sector with such a charge registers a
    # descriptor in seed_horizon_coupling instead of editing this function.
    from .oM_Features import (seed_horizon_coupling, TEMPORAL_HANDLED_PS_COST,
                              TEMPORAL_HANDLED_PS_REV)
    seed_horizon_coupling(full)
    horizon = list(getattr(full, "_horizon_coupling", []))
    for d in horizon:
        if d["kind"] == "unsupported":
            raise NotImplementedError(
                f"temporal Benders cannot decompose {d['reason']} yet.")
    constants = [d for d in horizon if d["kind"] == "constant"]
    thresholds = [d for d in horizon if d["kind"] == "threshold"]
    const_value = sum(d["amount"] for d in constants)
    const_vars = [d["cost_var"] for d in constants]
    # threshold master-linking keys: (descriptor index, subgroup, item)
    thr_keys = [(ti, sg, it) for ti, d in enumerate(thresholds)
                for sg in d["subgroups"] for it in d["items"]]
    fix_import = dict(cfg.extra.get("fix_import", {}))

    # contiguous time windows
    K = max(1, n_time_blocks)
    size = (len(levels) + K - 1) // K
    windows = [w for w in (levels[i:i + size] for i in range(0, len(levels), size)) if w]
    K = len(windows)
    blocks = list(range(K))
    bnd_names = ([("Se", k, g) for k in range(K - 1) for g in egs]
                 + [("Sh", k, g) for k in range(K - 1) for g in hgs]
                 + [("St", k, s) for k in range(K - 1) for s in hts])

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
        # boundary inventory levels (electricity / hydrogen / heat storage): no master
        # cost, so initialise (cold start)
        m.Se = Var(range(max(K - 1, 1)), egs, within=NonNegativeReals,
                   bounds=lambda mm, k, g: (0, maxE[g]), initialize=lambda mm, k, g: initE[g])
        m.Sh = Var(range(max(K - 1, 1)), hgs, within=NonNegativeReals,
                   bounds=lambda mm, k, g: (0, maxH[g]), initialize=lambda mm, k, g: initH[g])
        m.St = Var(range(max(K - 1, 1)), hts, within=NonNegativeReals,
                   bounds=lambda mm, k, s: (0, maxHt[s]), initialize=lambda mm, k, s: initHt[s])
        _bvar = {"Se": m.Se, "Sh": m.Sh, "St": m.St}
        for (kind, k, g) in bnd_names:
            x[(kind, k, g)] = _bvar[kind][k, g]
        # threshold linking variable per (descriptor, subgroup, item): the master holds
        # the N*t part of each threshold-LP and its cost; each window adds its own
        # sum_n (quantity_n - t)_+.
        m.tpk = Var(thr_keys, within=NonNegativeReals, bounds=(0, 1e9), initialize=0.0)
        for key in thr_keys:
            x[("t",) + key] = m.tpk[key]
        peak_master = discount * sum(
            thresholds[ti]["coeff_of"][it] * thresholds[ti]["count"] * m.tpk[(ti, sg, it)]
            for (ti, sg, it) in thr_keys)
        m.theta = Var(blocks, within=Reals, bounds=(-1e9, 1e12), initialize=0.0)
        m.cuts = ConstraintList()
        inv = period_weight * sum(invcost[nm] * x[nm] for nm in inv_names)   # factor1 dropped (audit C38): investment lump sum is invariant
        m.obj = Objective(expr=inv + discount * const_value + peak_master
                          + sum(m.theta[b] for b in blocks),
                          sense=minimize)
        return {"model": m, "x": x, "theta": {b: m.theta[b] for b in blocks}, "cuts": m.cuts}

    def make_subproblem(block):
        k = block
        win = windows[k]
        a, b = win[0], win[-1]
        sub = _build_window(dir_name, case_name, date, sc, win)

        # Transversality guard (fail fast on the first window build). The split is
        # transversal to the network representation (the network mode only changes a
        # window's own operating constraints; the windows are coupled by storage and
        # the registered aggregate costs, not by the network), to the hydrogen sector
        # and to the heat sector (electricity/hydrogen/heat storage are all coupled by
        # boundary inventory below, and the heat operating cost decomposes per window).
        # What is still refused rather than solved with a silently wrong objective: a
        # new per-(period, scenario) aggregate charge that is not described in the
        # horizon-coupling registry (so it is neither a plain per-level sum nor a
        # registered constant/threshold).
        _unknown = ([nm for nm, kd in getattr(sub, "_cost_terms", [])
                     if kd == "ps" and nm not in TEMPORAL_HANDLED_PS_COST]
                    + [nm for nm, kd in getattr(sub, "_revenue_terms", [])
                       if kd == "ps" and nm not in TEMPORAL_HANDLED_PS_REV])
        if _unknown:
            raise NotImplementedError(
                "temporal Benders handles only the known per-(period, scenario) "
                f"aggregate cost/revenue terms; found unhandled term(s) {_unknown}. A "
                "per-(period, scenario) term that is not a plain sum over load levels "
                "(a peak/threshold charge or a constant fee) does not split by time "
                "window on its own and must be added to the split explicitly -- see the "
                "peak threshold-LP and the fixed network charge counted once in the "
                "master in this function.")

        sub.dual = Suffix(direction=Suffix.IMPORT)
        sub._bxe = Param(egc, mutable=True, initialize=0.0)
        sub._bxh = Param(hgc, mutable=True, initialize=0.0)
        sub.bfix_e = Constraint(egc, rule=lambda mm, g: mm.vEleGenInvest[g] == mm._bxe[g])
        sub.bfix_h = Constraint(hgc, rule=lambda mm, g: mm.vHydGenInvest[g] == mm._bxh[g])
        # boundary copies for every boundary (fixed to the master value); only the
        # incoming (k-1) and outgoing (k) ones enter this block's constraints.
        sub._se = Param(range(max(K - 1, 1)), egs, mutable=True, initialize=0.0)
        sub._sh = Param(range(max(K - 1, 1)), hgs, mutable=True, initialize=0.0)
        sub._st = Param(range(max(K - 1, 1)), hts, mutable=True, initialize=0.0)
        sub.Secopy = Var(range(max(K - 1, 1)), egs, within=Reals)
        sub.Shcopy = Var(range(max(K - 1, 1)), hgs, within=Reals)
        sub.Stcopy = Var(range(max(K - 1, 1)), hts, within=Reals)
        sub.sefix = Constraint(range(max(K - 1, 1)), egs,
                               rule=lambda mm, kk, g: mm.Secopy[kk, g] == mm._se[kk, g])
        sub.shfix = Constraint(range(max(K - 1, 1)), hgs,
                               rule=lambda mm, kk, g: mm.Shcopy[kk, g] == mm._sh[kk, g])
        sub.stfix = Constraint(range(max(K - 1, 1)), hts,
                               rule=lambda mm, kk, s: mm.Stcopy[kk, s] == mm._st[kk, s])

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

        def _rep_ht(mm, s):
            if k == 0 or (p, sc, a, s) not in mm.eHeatInventory:
                return Constraint.Skip
            return (mm.vHeatInventory[p, sc, a, s]
                    == mm.Stcopy[k - 1, s]
                    + mm.Par['pDuration'][p, sc, a] * (heat_eff[s] * mm.vHeatCharge[p, sc, a, s]
                                                       - mm.vHeatDischarge[p, sc, a, s]))
        sub.rep_ht = Constraint(hts, rule=_rep_ht)
        if k > 0:
            for g in egs:
                if (p, sc, a, g) in sub.eEleInventory:
                    sub.eEleInventory[p, sc, a, g].deactivate()
            for g in hgs:
                if (p, sc, a, g) in sub.eHydInventory:
                    sub.eHydInventory[p, sc, a, g].deactivate()
            for s in hts:
                if (p, sc, a, s) in sub.eHeatInventory:
                    sub.eHeatInventory[p, sc, a, s].deactivate()

        # outgoing boundary (k < K-1): tie the window's last inventory to the copy
        sub.out_e = Constraint(egs, rule=lambda mm, g: (
            mm.vEleInventory[p, sc, b, g] == mm.Secopy[k, g]
            if (k < K - 1 and (p, sc, b, g) in mm.vEleInventory) else Constraint.Skip))
        sub.out_h = Constraint(hgs, rule=lambda mm, g: (
            mm.vHydInventory[p, sc, b, g] == mm.Shcopy[k, g]
            if (k < K - 1 and (p, sc, b, g) in mm.vHydInventory) else Constraint.Skip))
        sub.out_ht = Constraint(hts, rule=lambda mm, s: (
            mm.vHeatInventory[p, sc, b, s] == mm.Stcopy[k, s]
            if (k < K - 1 and (p, sc, b, s) in mm.vHeatInventory) else Constraint.Skip))

        sub.eTotalSCost.deactivate()

        # threshold-LP: drop this window's own peak charge(s) and inject the window's
        # part of each threshold-LP. The native peak machinery (the binary top-N
        # selection) is deactivated and the native peak-cost Var is pinned to 0 so it
        # leaves the block recourse; in its place u[n] >= quantity[n] - t[subgroup(n)]
        # adds sum_n (quantity_n - t)_+, with t fixed from the master (its
        # fixing-constraint dual is the cut subgradient). Driven by the threshold
        # descriptors, so any per-subgroup top-N charge is handled the same way.
        thr_u = []                                       # (descriptor, item, load level)
        if thresholds:
            sub._tpk = Param(thr_keys, mutable=True, initialize=0.0)
            sub.tpkcopy = Var(thr_keys, within=Reals)
            sub.tpkfix = Constraint(
                thr_keys, rule=lambda mm, ti, sg, it: mm.tpkcopy[ti, sg, it] == mm._tpk[ti, sg, it])
            sub_maps = {}                                # descriptor -> {load level: subgroup}
            for ti, d in enumerate(thresholds):
                sub.__getattribute__(d["cost_var"])[p, sc].fix(0.0)
                for cn in d["native_constraints"]:
                    c = getattr(sub, cn, None)
                    if c is not None:
                        c.deactivate()
                sub_maps[ti] = {nn: sg for (nn, sg) in getattr(sub, d["level_subgroup"])}
                qv = sub.__getattribute__(d["quantity_var"])
                for it in d["items"]:
                    nd = d["node_of"][it]
                    for nn in win:
                        if nn in sub_maps[ti] and (p, sc, nn, nd) in qv:
                            thr_u.append((ti, it, nn))
            sub.upk = Var(thr_u, within=NonNegativeReals)

            def _upkdef(mm, ti, it, nn):
                d = thresholds[ti]
                qv = mm.__getattribute__(d["quantity_var"])
                return (mm.upk[ti, it, nn]
                        >= qv[p, sc, nn, d["node_of"][it]]
                        - mm.tpkcopy[ti, sub_maps[ti][nn], it])
            sub.upkdef = Constraint(thr_u, rule=_upkdef)
            # optional: pin the window's metered quantity to a given profile (test
            # support), keyed by load level across every threshold's node.
            if fix_import:
                for ti, d in enumerate(thresholds):
                    qv = sub.__getattribute__(d["quantity_var"])
                    for it in d["items"]:
                        nd = d["node_of"][it]
                        for nn in win:
                            if nn in fix_import and (p, sc, nn, nd) in qv:
                                qv[p, sc, nn, nd].fix(float(fix_import[nn]))

        # elastic relaxation on the operating constraints (everything except the
        # fixing and boundary-coupling constraints) so the block is feasible for any
        # fixed master point. The boundary couplings stay HARD: the inventory must be
        # exactly the master value at the boundary (so it is conserved across the
        # split); feasibility for an unreachable boundary comes from the elastic
        # operating constraints (and the model's own ENS / spillage), and the
        # fixing-constraint duals carry the (feasibility) cut. The peak threshold
        # fixing and the u-definition are exact too, so they stay hard.
        keep_hard = ("bfix_e", "bfix_h", "sefix", "shfix", "stfix",
                     "rep_e", "rep_h", "rep_ht", "out_e", "out_h", "out_ht",
                     "tpkfix", "upkdef")
        targets = [c for c in sub.component_objects(Constraint, active=True)
                   if c.name not in keep_hard]
        TransformationFactory('core.add_slack_variables').apply_to(sub, targets=targets)
        slack_blk = sub._core_add_slack_variables
        slack_blk._slack_objective.deactivate()
        slack_vars = list(slack_blk.component_data_objects(Var))
        slack_sum = sum(slack_vars)
        peak_win = (discount * sum(thresholds[ti]["coeff_of"][it] * sub.upk[ti, it, nn]
                                   for (ti, it, nn) in thr_u)
                    if thr_u else 0.0)
        # heat operating cost (heat-not-served + heat generator running cost) is a
        # duration-weighted, already-period-discounted sum over the window's load
        # levels, so it decomposes by window like the electricity/hydrogen "psn" costs;
        # add the window's share to the recourse. It is zero (and absent) for a case
        # with no heat sector. This is what makes the split transversal to the heat
        # sector (without a thermal store, which is guarded above).
        heat_win = getattr(sub, "HeatOperatingCost", 0.0)
        # the real operating recourse, kept separate from the elastic penalty so the
        # bound/cut can read it clean (see recourse_value below)
        const_sub = sum(sub.__getattribute__(cv)[p, sc] for cv in const_vars)
        real_recourse = (discount * (sub.vTotalCComponent[p, sc]
                                     - const_sub
                                     - sub.vTotalRComponent[p, sc])
                         + peak_win + heat_win)
        sub.benders_obj = Objective(expr=real_recourse + penalty * slack_sum, sense=minimize)

        def recourse_value():
            # the value passed to the Benders bound and cut: the true recourse plus
            # the penalty on any GENUINE slack. Negative slack within the solver's
            # feasibility tolerance is clamped to zero, so a large penalty cannot turn
            # that drift into a spurious reduction (which would poison the bound).
            pos = sum(s for s in (float(value(v)) for v in slack_vars) if s > 0.0)
            return float(value(real_recourse)) + penalty * pos

        fix = {("e", g): sub.bfix_e[g] for g in egc}
        fix.update({("h", g): sub.bfix_h[g] for g in hgc})
        _bfix = {"Se": sub.sefix, "Sh": sub.shfix, "St": sub.stfix}
        for (kind, kk, g) in bnd_names:
            fix[(kind, kk, g)] = _bfix[kind][kk, g]
        for key in thr_keys:
            fix[("t",) + key] = sub.tpkfix[key]

        def set_xhat(x_hat):
            for g in egc:
                sub._bxe[g] = x_hat[("e", g)]
            for g in hgc:
                sub._bxh[g] = x_hat[("h", g)]
            _bpar = {"Se": sub._se, "Sh": sub._sh, "St": sub._st}
            for (kind, kk, g) in bnd_names:
                _bpar[kind][kk, g] = x_hat[(kind, kk, g)]
            for key in thr_keys:
                sub._tpk[key] = x_hat[("t",) + key]

        xcopy = {("e", g): sub.vEleGenInvest[g] for g in egc}
        xcopy.update({("h", g): sub.vHydGenInvest[g] for g in hgc})
        return {"model": sub, "xcopy": xcopy, "fix": fix, "set_xhat": set_xhat,
                "obj": sub.benders_obj, "recourse": recourse_value}

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
        inv = period_weight * sum(invcost[nm] * x[nm] for nm in names)   # factor1 dropped (audit C38): investment lump sum is invariant
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
