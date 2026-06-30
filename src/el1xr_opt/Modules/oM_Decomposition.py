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
      time axis is split: the storage inventory at each block boundary, plus the
      trailing FCR reserve bids that a reserve-endurance constraint reads one step
      back across the boundary (the augmented boundary state).
    """
    return {
        "complicating": ["vEleGenInvest", "vHydGenInvest", "vTotalICost"],
        "linking": ["vEleInventory", "vHydInventory",
                    "vEleFreqContReserveDisUpwardBid", "vEleFreqContReserveDisDownwardBid",
                    "vEleFreqContReserveNorBid"],
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
    optimum. Later fallbacks also use a fresh solver instance to avoid any persistent
    internal state left by the failed solve. The retries run only after a solve has
    already failed, so they cannot affect the normal path; if all retries also fail the
    last error propagates.
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
    # Entries with use_fresh=True create a new solver instance (same type as opt)
    # to clear any persistent internal state left by the failed solve -- helpful
    # when the appsi_highs HiGHS object holds corrupted LP state across retries.
    # The last entry is tried without a catching except so its error propagates.
    _FALLBACKS = (
        ({"presolve": "off"}, False),
        ({"presolve": "off", "solver": "simplex"}, False),
        ({"solver": "ipm"}, True),
        ({"presolve": "off", "solver": "ipm"}, True),
    )
    for i, (extra, use_fresh) in enumerate(_FALLBACKS):
        is_last = i == len(_FALLBACKS) - 1
        # Attempt to create a fresh solver instance to clear any corrupted internal
        # state. This is best-effort: if instantiation fails for any reason (e.g. the
        # solver class requires constructor arguments or the solver is unavailable in
        # the current environment) we silently fall back to the original instance and
        # let the option changes do what they can.
        if use_fresh:
            try:
                cur_opt = type(opt)()
            except Exception:  # noqa: BLE001 -- intentional best-effort fallback
                cur_opt = opt
        else:
            cur_opt = opt
        # cur_opt.options is guaranteed to support dict-like access: either it is the
        # original opt (same options type as before) or a fresh instance of the same
        # class (whose options object uses the same interface).
        saved = {k: cur_opt.options[k] for k in extra if k in cur_opt.options}
        added_keys = [k for k in extra if k not in cur_opt.options]
        cur_opt.options.update(extra)
        try:
            res = cur_opt.solve(mdl, load_solutions=False)
            mdl.solutions.load_from(res)
            return res
        except (ValueError, RuntimeError):
            # appsi_highs raises ValueError on bad solver status and RuntimeError
            # on some internal failures; both indicate the same spurious error.
            if is_last:
                raise
        finally:
            for k in added_keys:
                try:
                    del cur_opt.options[k]
                except (KeyError, TypeError):
                    pass
            cur_opt.options.update(saved)


def benders_solve(make_master, make_subproblem, blocks, config=None,
                  solver="appsi_highs", solve_blocks=None, cut_mode="lp",
                  ub_recourse=None):
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

    def _solve_lp_fix(x_hat):
        # Fix-and-resolve LP cuts for INTEGER recourse. The plain lp mode needs duals of the
        # x-fixing constraints, but a binary block has none. So: solve the block MILP, take its
        # integer recourse value q_b, then fix every discrete var to its solution (and relax its
        # domain so the re-solve is a pure LP), re-solve the continuous restriction, and read the
        # fixing-constraint duals lam. The (q_b, lam) cut has the same shape as the lp cut.
        # IMPORTANT: these duals support only the CONVEX ENVELOPE of the value function, so the
        # resulting bound is INEXACT for the integer problem (it is the inexact baseline against
        # which the valid cut_mode='lagrangian' is compared). Restores fixings/domains after.
        from pyomo.environ import Var, Reals, Suffix
        solved = {}
        for b in blocks:
            sub = subs[b]; m = sub["model"]
            sub["set_xhat"](x_hat)
            # The first solve is a MILP, which has no duals; some solver interfaces (appsi_highs)
            # try to load duals whenever a dual Suffix exists and error. So remove the Suffix for
            # the MILP solve and re-add it (empty) for the LP re-solve, which then populates it.
            has_dual = hasattr(m, "dual")
            if has_dual:
                m.del_component("dual")
            _solve_model(opt_sub, m)                                   # MILP solve (no duals)
            qb = sub["recourse"]() if "recourse" in sub else float(value(sub["obj"]))
            if has_dual:
                m.dual = Suffix(direction=Suffix.IMPORT)
            # Relax the domain of EVERY discrete var (not just the free ones) so the re-solve
            # is a pure LP with duals -- a discrete var that the model already fixed still
            # declares an integer domain, which keeps the solver in MIP mode (no duals).
            touched = []
            for v in m.component_data_objects(Var, active=True):
                if not v.is_continuous():
                    was_fixed = v.fixed
                    touched.append((v, v.domain, was_fixed))
                    v.domain = Reals
                    if not was_fixed:
                        v.fix(v.value)                                # pin the free ones at their MILP value
            try:
                _solve_model(opt_sub, m)                               # continuous restriction -> duals
                # default a missing dual to 0: some solvers (gurobi) presolve a fixing
                # constraint away when its var is also bounded, so its dual is not reported;
                # the lp_fix cut is the inexact baseline, so a zero coefficient is acceptable.
                lam = {n: float(m.dual.get(sub["fix"][n], 0.0)) for n in names}
            finally:
                for v, dom, was_fixed in touched:
                    if not was_fixed:
                        v.unfix()
                    v.domain = dom
            solved[b] = (qb, lam)
        return solved

    def _solve_lagrangian(x_hat):
        # Integer-aware cuts (SDDiP-style). For each block, dualise the copy constraints
        # (deactivate the fixings, add sum_n pi_n * xcopy_n to the block objective, solved as
        # a MILP so the recourse stays integer) and ascend pi to maximise the Lagrangian dual
        # g(pi) = phi(pi) - sum_n pi_n * x_hat_n, where phi(pi) is the dualised block value.
        # The cut is theta_b >= g(pi*) + sum_n (-pi*_n)(x_n - x_hat_n) -- the same shape as the
        # LP cut (q_b = g(pi*), lam = -pi*), but a VALID lower bound on the integer recourse.
        # With a binarised linking state (the master binary-expands it) these cuts are tight.
        from pyomo.environ import (Param, Objective, Reals, Set, minimize, maximize,
                                    ConcreteModel, Var, ConstraintList, value as _val)
        steps = int(cfg.extra.get("lag_steps", 20))
        step0 = float(cfg.extra.get("lag_step0", 1.0))
        lag_method = str(cfg.extra.get("lag_method", "level")).lower()
        # Keep the first-stage INVESTMENT hard-fixed in the blocks instead of dualising it.
        # A dualised continuous investment lets each block "build" the unit internally for a
        # cheap multiplier penalty, so the cut never reflects that a no-build master point is
        # infeasible and the master stalls (it never gets pushed to build). With investment
        # hard the block operates at exactly the master's build fraction, so the recourse at a
        # no-build point is genuinely high; the cut's investment slope is read from the LP dual
        # of the fixing (fix integers, relax, re-solve), a valid Benders cut on the continuous
        # first stage. The temporal boundary + bid state stays Lagrangian (integer-exact).
        hard_invest = bool(cfg.extra.get("lag_hard_invest", True))
        solved = {}
        for b in blocks:
            sub = subs[b]; m = sub["model"]; sub["set_xhat"](x_hat)
            xcopy = sub["xcopy"]
            # only dualise the keys this block actually couples on: a temporal block uses its
            # own incoming/outgoing boundaries (+ its thresholds), not every other block's
            # boundary copy. Relaxing an unused (unbounded) copy would leave it uninitialised
            # and the Lagrangian unbounded. Inactive keys keep their fixing and get a zero (or,
            # for hard investment, an LP-dual) cut coefficient.
            inv_keys = [n for n in names if n[0] in ("e", "h")]
            active = [n for n in sub.get("active_keys", names)
                      if n in xcopy and not (hard_invest and n[0] in ("e", "h"))]
            missing = [n for n in active if n not in xcopy]
            if missing:
                raise ValueError(f"lagrangian cut_mode needs a copy var for every active key; "
                                 f"block {b} is missing {missing[:3]}{'...' if len(missing) > 3 else ''}")
            if not hasattr(m, "_lag_pi"):                       # one-time Lagrangian setup
                # jagged index: linking keys have mixed lengths (investment 2-tuples,
                # boundary 3-tuples, threshold 4-tuples), so the Set must be dimen=None.
                m._lag_idx = Set(initialize=list(active), dimen=None, ordered=True)
                m._lag_pi = Param(m._lag_idx, mutable=True, initialize=0.0, within=Reals)
                for n in active:
                    sub["fix"][n].deactivate()
                m._lag_obj = Objective(expr=sub["obj"].expr
                                       + sum(m._lag_pi[n] * xcopy[n] for n in active), sense=minimize)
                sub["obj"].deactivate()
            # The Lagrangian dual g(pi) = phi(pi) - pi.x_hat is CONCAVE; we maximise it. With a
            # binarised (bounded-copy) state phi(pi) is finite for every pi, so g is finite
            # everywhere. _eval(pi) solves the freed block MILP and returns (g, supergradient s);
            # it returns None where the block is non-optimal/unbounded (an unbounded-copy or
            # LP-mode pi), which the ascent then skips. pi is held as a position vector aligned
            # to idx so the inner QP/LP models can use a plain integer index.
            idx = list(active); D = len(idx)
            xh = [x_hat[n] for n in idx]

            def _eval(pivec):
                for j, n in enumerate(idx):
                    m._lag_pi[n] = pivec[j]
                try:
                    _r = opt_sub.solve(m, load_solutions=False)
                    if "optimal" not in str(_r.solver.termination_condition).lower():
                        return None
                    try:
                        m.solutions.load_from(_r)
                    except Exception:
                        _solve_model(opt_sub, m)         # appsi fallback load
                    phi = float(_val(m._lag_obj))
                    xc = [float(_val(xcopy[n])) for n in idx]
                except Exception:
                    return None
                g = phi - sum(pivec[j] * xh[j] for j in range(D))
                s = [xc[j] - xh[j] for j in range(D)]    # supergradient of g at pi
                return g, s

            if lag_method == "subgradient":
                # NORMALISED diminishing-step subgradient ascent (legacy / fallback, kept for
                # A/B comparison): take a 1/sqrt(t) step along the unit supergradient; a pi that
                # makes the block non-optimal is rejected (revert to best pi, shrink the step).
                pivec = [0.0] * D
                best_g, best_pivec, scale = -float("inf"), list(pivec), step0
                for t in range(1, steps + 1):
                    ev = _eval(pivec)
                    if ev is None:
                        pivec = list(best_pivec); scale *= 0.5; continue
                    g, s = ev
                    if g > best_g:
                        best_g, best_pivec = g, list(pivec)
                    norm = sum(v * v for v in s) ** 0.5
                    if norm > 1e-9:
                        stp = scale / (t ** 0.5) / norm
                        pivec = [pivec[j] + stp * s[j] for j in range(D)]
                best_pi = {idx[j]: best_pivec[j] for j in range(D)}
            else:
                # LEVEL-BUNDLE ascent. Keep the whole bundle of supergradient cuts; each is an
                # upper affine model of the concave dual. Take U = max_pi min_i[g_i +
                # s_i.(pi - pi_i)] over a box (an upper bound on the dual optimum), set a level
                # ell = L + lam (U - L), and project the stability centre onto {model >= ell}.
                # This uses every past evaluation and is scale-free, so it closes the dual far
                # faster and more reliably than a single subgradient step (the week-scale case
                # where the plain subgradient under-maximises).
                lam = float(cfg.extra.get("lag_level", 0.5))
                box = float(cfg.extra.get("lag_box", 1.0e5))
                tol = float(cfg.extra.get("lag_tol", 1e-6))
                ev = _eval([0.0] * D)
                if ev is None:
                    best_g, best_pi = -float("inf"), {n: 0.0 for n in active}
                else:
                    g0, s0 = ev
                    bundle = [([0.0] * D, g0, s0)]
                    best_g, best_pivec, center = g0, [0.0] * D, [0.0] * D
                    for _it in range(steps):
                        um = ConcreteModel(); um.j = Set(initialize=list(range(D)), ordered=True)
                        um.pi = Var(um.j, bounds=(-box, box)); um.tau = Var(); um.c = ConstraintList()
                        for (pv, gv, sv) in bundle:
                            um.c.add(um.tau <= gv + sum(sv[j] * (um.pi[j] - pv[j]) for j in range(D)))
                        um.o = Objective(expr=um.tau, sense=maximize)
                        try:
                            _solve_model(opt_sub, um); U = float(_val(um.tau))
                        except Exception:
                            break
                        if U - best_g <= tol * (1.0 + abs(best_g)):
                            break
                        level = best_g + lam * (U - best_g)
                        lp = ConcreteModel(); lp.j = Set(initialize=list(range(D)), ordered=True)
                        lp.pi = Var(lp.j); lp.c = ConstraintList()
                        for (pv, gv, sv) in bundle:
                            lp.c.add(gv + sum(sv[j] * (lp.pi[j] - pv[j]) for j in range(D)) >= level)
                        lp.o = Objective(expr=sum((lp.pi[j] - center[j]) ** 2 for j in range(D)),
                                         sense=minimize)
                        try:
                            _solve_model(opt_sub, lp)
                            pinew = [float(_val(lp.pi[j])) for j in range(D)]
                        except Exception:
                            break
                        ev = _eval(pinew)
                        if ev is None:
                            break
                        g, s = ev; bundle.append((list(pinew), g, s))
                        if g > best_g:
                            best_g, best_pivec = g, list(pinew)
                        center = list(pinew)
                    best_pi = {idx[j]: best_pivec[j] for j in range(D)}
            # true recourse at x_hat for the UB: re-fix the copies and solve the block MILP
            # with its own (un-penalised) objective. The Lagrangian value (best_g) is only a
            # lower bound, so it must NOT be used as the UB. When investment is hard, also read
            # its cut slope here from the LP dual of the fixing (fix integers, relax, re-solve).
            from pyomo.environ import Var as _Var, Reals as _Re, Suffix as _Suf
            lam_inv = {n: 0.0 for n in inv_keys}
            for n in active:
                m._lag_pi[n] = 0.0
                sub["fix"][n].activate()
            m._lag_obj.deactivate(); sub["obj"].activate()
            try:
                _had_dual = hasattr(m, "dual")
                if _had_dual:
                    m.del_component("dual")
                _solve_model(opt_sub, m)            # MILP at x_hat (investment hard-fixed)
                true_q = sub["recourse"]() if "recourse" in sub else float(_val(sub["obj"]))
                if hard_invest and inv_keys:
                    # fix the discrete vars at their MILP values and relax their domain, so the
                    # re-solve is a pure LP whose fixing-constraint duals give the investment
                    # cut slope (a valid Benders cut on the continuous build fraction).
                    m.dual = _Suf(direction=_Suf.IMPORT)
                    _touched = []
                    for v in m.component_data_objects(_Var, active=True):
                        if not v.is_continuous():
                            _wf = v.fixed; _touched.append((v, v.domain, _wf)); v.domain = _Re
                            if not _wf:
                                v.fix(v.value)
                    try:
                        _solve_model(opt_sub, m)
                        lam_inv = {n: float(m.dual.get(sub["fix"][n], 0.0)) for n in inv_keys}
                    finally:
                        for v, dom, _wf in _touched:
                            if not _wf:
                                v.unfix()
                            v.domain = dom
                        m.del_component("dual")
                        if _had_dual:
                            m.dual = _Suf(direction=_Suf.IMPORT)
            except Exception:
                true_q = float("inf")               # infeasible at x_hat -> steers the master away
            sub["obj"].deactivate(); m._lag_obj.activate()
            for n in active:
                sub["fix"][n].deactivate()
            lam = {n: (-best_pi[n] if n in best_pi else 0.0) for n in names}
            for n in inv_keys:
                lam[n] = lam_inv.get(n, 0.0)
            solved[b] = (best_g, lam, true_q)
        return solved

    if cut_mode == "lagrangian":
        if solve_blocks is not None:
            raise NotImplementedError("lagrangian cut_mode does not support external solve_blocks yet")
        solve = _solve_lagrangian
    elif cut_mode == "lp_fix":
        if solve_blocks is not None:
            raise NotImplementedError("lp_fix cut_mode does not support external solve_blocks yet")
        solve = _solve_lp_fix
    else:
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

        solved = solve(x_hat)                  # {block: (cut_q, lam[, ub_q])}
        # The UB is the TRUE recourse at the master point. In LP mode cut_q is already the
        # true recourse; in Lagrangian mode cut_q is a LOWER bound (the cut), so the block
        # also returns ub_q = the true integer recourse (master point fixed) -- using the
        # cut value as the UB would falsely "converge" to the loose Lagrangian bound.
        # When an ``ub_recourse`` hook is given (the integer/binarised temporal mode), the
        # per-block ub_q fixes every storage boundary to the master's binarised-grid value,
        # which the blocks cannot meet exactly (an elastic-penalty UB); the hook instead
        # recovers a feasible UB by a forward pass (boundaries free, fed block to block).
        if ub_recourse is not None:
            recourse = ub_recourse(x_hat, subs, opt_sub)
        else:
            recourse = sum((v[2] if len(v) > 2 else v[0]) for v in solved.values())

        ub = first_stage_cost + recourse
        best_ub = min(best_ub, ub)
        gap = abs(best_ub - lb) / (abs(best_ub) + 1e-12)
        if cfg.extra.get("verbose"):
            print(f"  benders it {it:3d}: lb={lb:.4f} ub={ub:.4f} best_ub={best_ub:.4f} gap={gap:.2e}")
        if gap <= cfg.relative_gap:
            break

        # add an optimality cut per block: theta_b >= cut_q + sum_n lam_n (x_n - x_hat_n)
        for b in blocks:
            q_b, lam = solved[b][0], solved[b][1]
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
                           solver="appsi_highs", config=None, cut_mode="lp",
                           binarize_state=None):
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
    # SDDiP-style boundary-state binarisation: required for the Lagrangian cut_mode (the
    # boundary inventory is the linking STATE; binarising it onto a finite grid both bounds
    # the dualised copies, so the Lagrangian is bounded, and makes the cuts tight, so the
    # method converges to the integer optimum). Default on for cut_mode='lagrangian'.
    _binstate = (cut_mode == "lagrangian") if binarize_state is None else bool(binarize_state)
    _nbits = int((config or BendersConfig()).extra.get("state_bits", 8))
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

    # --- Augmented boundary state: trailing FCR reserve bids ---------------------
    # The reserve-endurance constraints couple a reserve bid at step n-1 to the
    # storage state at step n, so when a time-block seam falls between n-1 and n the
    # constraint pairs a decision in block k (the trailing bid) with a state in block
    # k+1 (the inventory/headroom). A scalar boundary SoC cannot carry the trailing
    # bid, so the receiving block drops the constraint and the decomposition reports a
    # cheaper-than-true optimum (over-bidding reserve at every seam). The fix is to
    # carry the trailing bid across the seam as part of the boundary state, exactly as
    # the inventory levels are carried. Today the endurance window is one step back
    # (W=2), so only the single trailing bid is needed. Inert (no new state) for a
    # case with no FCR-endurance units, so non-FCR cases are byte-unchanged.
    carry_bids = bool(cfg.extra.get("carry_trailing_bids", True))
    e2h_units = list(getattr(full, "e2h", []) or [])
    h2e_units = list(getattr(full, "h2e", []) or [])
    nodes = list(getattr(full, "nd", []) or [])
    n2hg = set(full.n2hg) if hasattr(full, "n2hg") else set()
    n2eg = set(full.n2eg) if hasattr(full, "n2eg") else set()

    def _flag0(key, u):
        try:
            return int(full.Par[key][u]) == 0
        except (KeyError, TypeError):
            return False

    def _ele_fcrd(u):
        return _flag0('pEleGenNoFCRD', u)

    def _ele_fcrn(u):
        return _flag0('pEleGenNoFCRN', u)

    def _hyd_fcrd(u):
        return _flag0('pHydGenNoFCRD', u)

    def _hyd_fcrn(u):
        return _flag0('pHydGenNoFCRN', u)

    def _ele_fcr(u):
        return _ele_fcrd(u) or _ele_fcrn(u)

    def _hyd_fcr(u):
        return _hyd_fcrd(u) or _hyd_fcrn(u)

    # node membership (replicates the monolith's node filters incl. the FCR guard)
    e2h_node = {nd: [u for u in e2h_units if (nd, u) in n2hg and _hyd_fcr(u)] for nd in nodes}
    h2e_node = {nd: [u for u in h2e_units if (nd, u) in n2eg and _ele_fcr(u)] for nd in nodes}
    hgs_node = {nd: [u for u in hgs if (nd, u) in n2hg] for nd in nodes}
    # battery units whose endurance constraint can straddle a seam (FCR-flagged and
    # actually storing energy over the horizon)
    endur_egs = [g for g in egs
                 if _ele_fcr(g) and any(float(full.Par['pEleMaxStorage'][g][p, sc, n]) for n in levels)]
    # the trailing-bid components carried across each seam. btype maps to a bid var:
    #   'up'  -> vEleFreqContReserveDisUpwardBid    (FCR-D up: battery, fuel cell)
    #   'dn'  -> vEleFreqContReserveDisDownwardBid  (FCR-D down: battery, electrolyser)
    #   'nor' -> vEleFreqContReserveNorBid          (FCR-N: all of them)
    # Only carry a component when its FCR product is enabled for the unit; a disabled
    # bid is pinned to zero by a hard constraint, so tying it to a nonzero master copy
    # would make the sending block infeasible.
    bid_comp = []                                    # list of (unit, btype)
    if carry_bids:
        for g in endur_egs:                          # battery: up/dn are FCR-D, nor is FCR-N
            if _ele_fcrd(g):
                bid_comp += [(g, 'up'), (g, 'dn')]
            if _ele_fcrn(g):
                bid_comp += [(g, 'nor')]
        for nd in nodes:
            for u in e2h_node[nd]:                   # electrolyser down: FCR-D / FCR-N (hyd flags)
                if _hyd_fcrd(u):
                    bid_comp += [(u, 'dn')]
                if _hyd_fcrn(u):
                    bid_comp += [(u, 'nor')]
            for u in h2e_node[nd]:                   # fuel cell up: FCR-D / FCR-N (ele flags)
                if _ele_fcrd(u):
                    bid_comp += [(u, 'up')]
                if _ele_fcrn(u):
                    bid_comp += [(u, 'nor')]
        _seen = set()
        bid_comp = [c for c in bid_comp if not (c in _seen or _seen.add(c))]
    bid_names = [("Bid", k, u, bt) for k in range(K - 1) for (u, bt) in bid_comp]
    _BIDVAR = {'up': 'vEleFreqContReserveDisUpwardBid',
               'dn': 'vEleFreqContReserveDisDownwardBid',
               'nor': 'vEleFreqContReserveNorBid'}

    def _bid_cap(u):
        # loose nameplate cap for the carried bid (master-var bound, binarisation grid
        # top). The true bid is bounded inside the sending block, so a generous cap
        # never changes the LP optimum; for the Lagrangian grid a tighter cap helps.
        for key in ('pEleMaxPower', 'pEleMaxCharge'):
            try:
                return max(max(float(full.Par[key][u][p, sc, n]) for n in levels) * factor1, 1.0)
            except (KeyError, TypeError):
                continue
        for key in ('pHydGenMaximumPower', 'pHydGenMaximumCharge'):
            try:
                return max(float(full.Par[key][u]) * factor1, 1.0)
            except (KeyError, TypeError):
                continue
        return float(cfg.extra.get("bid_cap", 1e6))
    bidcap = {u: _bid_cap(u) for (u, _bt) in bid_comp}

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
        # trailing-bid linking variables (one per seam, FCR unit, bid component): no
        # master cost, bounded by a loose nameplate cap so the binarised grid is finite.
        m.Bid = Var([(k, u, bt) for k in range(max(K - 1, 1)) for (u, bt) in bid_comp],
                    within=NonNegativeReals,
                    bounds=lambda mm, k, u, bt: (0.0, bidcap[u]), initialize=0.0)
        for (_tag, k, u, bt) in bid_names:
            x[("Bid", k, u, bt)] = m.Bid[k, u, bt]
        if _binstate:
            # binary-expand each boundary state onto a [0, cap] grid (cap = nameplate*factor1),
            # so the dualised subproblem copies are bounded (Lagrangian bounded) and the cuts
            # are tight at the grid points (SDDiP exactness). The cut interface is unchanged --
            # x still maps to m.Se/m.Sh/m.St, which are now pinned to the grid.
            _caps = {"Se": {g: maxE[g] * factor1 for g in egs},
                     "Sh": {g: maxH[g] * factor1 for g in hgs},
                     "St": {s: maxHt[s] * factor1 for s in hts}}
            _bit = {"Se": Var(range(max(K - 1, 1)), egs, range(_nbits), within=Binary),
                    "Sh": Var(range(max(K - 1, 1)), hgs, range(_nbits), within=Binary),
                    "St": Var(range(max(K - 1, 1)), hts, range(_nbits), within=Binary)}
            m.SeBit, m.ShBit, m.StBit = _bit["Se"], _bit["Sh"], _bit["St"]
            denom = float(2 ** _nbits - 1)
            for kind, items in (("Se", egs), ("Sh", hgs), ("St", hts)):
                cl = ConstraintList()
                setattr(m, f"{kind}BinDef", cl)
                for kk in range(max(K - 1, 1)):
                    for g in items:
                        cap = _caps[kind][g]
                        cl.add(_bvar[kind][kk, g]
                               == sum((cap / denom) * (2 ** j) * _bit[kind][kk, g, j]
                                      for j in range(_nbits)))
            # binarise the trailing-bid components onto their own [0, cap] grid, so the
            # dualised bid copies are bounded and the Lagrangian cut is tight there too.
            if bid_comp:
                m.BidBit = Var([(k, u, bt, j) for k in range(max(K - 1, 1))
                                for (u, bt) in bid_comp for j in range(_nbits)], within=Binary)
                m.BidBinDef = ConstraintList()
                for kk in range(max(K - 1, 1)):
                    for (u, bt) in bid_comp:
                        cap = bidcap[u]
                        m.BidBinDef.add(m.Bid[kk, u, bt]
                                        == sum((cap / denom) * (2 ** j) * m.BidBit[kk, u, bt, j]
                                               for j in range(_nbits)))
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
        # The boundary copies are bounded to [0, cap] when the state is binarised, so the
        # dualised Lagrangian (cut_mode='lagrangian') is bounded; otherwise free (LP mode).
        _seb = (lambda mm, k, g: (0.0, maxE[g] * factor1)) if _binstate else None
        _shb = (lambda mm, k, g: (0.0, maxH[g] * factor1)) if _binstate else None
        _stb = (lambda mm, k, s: (0.0, maxHt[s] * factor1)) if _binstate else None
        sub.Secopy = Var(range(max(K - 1, 1)), egs, within=Reals, bounds=_seb)
        sub.Shcopy = Var(range(max(K - 1, 1)), hgs, within=Reals, bounds=_shb)
        sub.Stcopy = Var(range(max(K - 1, 1)), hts, within=Reals, bounds=_stb)
        sub.sefix = Constraint(range(max(K - 1, 1)), egs,
                               rule=lambda mm, kk, g: mm.Secopy[kk, g] == mm._se[kk, g])
        sub.shfix = Constraint(range(max(K - 1, 1)), hgs,
                               rule=lambda mm, kk, g: mm.Shcopy[kk, g] == mm._sh[kk, g])
        sub.stfix = Constraint(range(max(K - 1, 1)), hts,
                               rule=lambda mm, kk, s: mm.Stcopy[kk, s] == mm._st[kk, s])

        # trailing-bid copies: one per seam, FCR unit, bid component. The copy is tied
        # to the master Bid value (bidfix, the cut's dual source); only the incoming
        # (k-1, used by the receiving endurance rows) and outgoing (k, tied to this
        # window's last-level bid) ones enter this block's constraints.
        _bidx = [(kk, u, bt) for kk in range(max(K - 1, 1)) for (u, bt) in bid_comp]
        if bid_comp:
            sub._bid = Param(_bidx, mutable=True, initialize=0.0)
            _bidb = (lambda mm, kk, u, bt: (0.0, bidcap[u])) if _binstate else None
            sub.Bidcopy = Var(_bidx, within=Reals, bounds=_bidb)
            sub.bidfix = Constraint(
                _bidx, rule=lambda mm, kk, u, bt: mm.Bidcopy[kk, u, bt] == mm._bid[kk, u, bt])

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

        # --- straddling reserve-endurance: sending and receiving sides of each seam.
        bid_comp_set = set(bid_comp)
        if bid_comp and k < K - 1:
            # sending side: tie this window's last-level (b) bids to the outgoing copy.
            def _out_bid(mm, u, bt):
                bv = getattr(mm, _BIDVAR[bt])
                if (p, sc, b, u) not in bv:
                    return Constraint.Skip
                return bv[p, sc, b, u] == mm.Bidcopy[k, u, bt]
            sub.out_bid = Constraint(list(bid_comp), rule=_out_bid)
            # drop the spurious terminal endurance rows the window adds at b: b is not
            # the true horizon end, so the bid at b is backed by the inventory one step
            # ahead (the receiving block's first-level rolling row below), not by b's own
            # inventory. Only the b-level rows exist in the window (guard n==n.last()).
            # Their names are recorded so the forward-pass primal heuristic can re-activate
            # them: backing the trailing bid with the sending block's own ending inventory
            # forces it to retain enough energy, which keeps the greedy forward solution
            # feasible (without it the relieved sending block ends empty and the receiving
            # block cannot charge fast enough to back the bid -> large elastic slack).
            sub._fwd_end_rows = []
            for cn in ("eEleStorageEnduranceUpEnd", "eEleStorageEnduranceDownEnd",
                       "eEleFreqDownEnduranceConvEnd", "eEleFreqUpEnduranceFuelCellEnd"):
                c = getattr(sub, cn, None)
                if c is not None:
                    c.deactivate()
                    sub._fwd_end_rows.append(cn)
        if bid_comp and k > 0:
            # receiving side: re-add the rolling endurance rows the window drops at its
            # first level a (a has ordinal 1, so prev(a) lies in the previous block).
            # Read the trailing bid from the incoming copy Bidcopy[k-1]; back it with
            # this block's first-level inventory/headroom. Same inequality as the
            # monolith, one term supplied by the boundary copy. Elastic (not in
            # keep_hard) so the block stays feasible for any incoming master bid.
            Par = sub.Par

            def _bc(u, bt):
                # carried trailing bid, or 0 when that component is not carried (the
                # bid var is pinned to zero in the monolith too, so the term vanishes).
                return sub.Bidcopy[k - 1, u, bt] if (u, bt) in bid_comp_set else 0.0
            sub.seam_endur = ConstraintList()
            for g in egs:                                  # battery up / down
                if (p, sc, a, g) not in sub.vEleInventory or not Par['pEleMaxStorage'][g][p, sc, a]:
                    continue
                if (g, 'up') in bid_comp_set or (g, 'nor') in bid_comp_set:
                    sub.seam_endur.add(
                        sub.vEleInventory[p, sc, a, g]
                        >= (1.0 / Par['pEleGenEfficiency_discharge'][g])
                        * ((Par['pEleGenEnduranceFCRD'][g] / 60) * _bc(g, 'up')
                           + (Par['pEleGenEnduranceFCRN'][g] / 60) * _bc(g, 'nor')))
                if (g, 'dn') in bid_comp_set or (g, 'nor') in bid_comp_set:
                    sub.seam_endur.add(
                        Par['pEleMaxStorage'][g][p, sc, a] * factor1 - sub.vEleInventory[p, sc, a, g]
                        >= Par['pEleGenEfficiency_charge'][g]
                        * ((Par['pEleGenEnduranceFCRD'][g] / 60) * _bc(g, 'dn')
                           + (Par['pEleGenEnduranceFCRN'][g] / 60) * _bc(g, 'nor')))
            for nd in nodes:                               # electrolyser FCR-down per node
                e2h_n = e2h_node[nd]
                if not e2h_n or not any((u, bt) in bid_comp_set for u in e2h_n for bt in ('dn', 'nor')):
                    continue
                lhs = sum(((Par['pHydGenEnduranceFCRD'][u] / 60) * _bc(u, 'dn')
                           + (Par['pHydGenEnduranceFCRN'][u] / 60) * _bc(u, 'nor'))
                          / Par['pHydGenProductionFunction'][u] for u in e2h_n)
                rhs = sum(Par['pHydMaxStorage'][hs][p, sc, a] * factor1 - sub.vHydInventory[p, sc, a, hs]
                          for hs in hgs_node[nd] if (p, sc, a, hs) in sub.vHydInventory)
                sub.seam_endur.add(lhs <= rhs)
            for nd in nodes:                               # fuel-cell FCR-up per node
                h2e_n = h2e_node[nd]
                if not h2e_n or not any((u, bt) in bid_comp_set for u in h2e_n for bt in ('up', 'nor')):
                    continue
                lhs = sum(((Par['pEleGenEnduranceFCRD'][u] / 60) * _bc(u, 'up')
                           + (Par['pEleGenEnduranceFCRN'][u] / 60) * _bc(u, 'nor'))
                          / Par['pEleGenProductionFunction'][u] for u in h2e_n)
                rhs = sum(sub.vHydInventory[p, sc, a, hs]
                          for hs in hgs_node[nd] if (p, sc, a, hs) in sub.vHydInventory)
                sub.seam_endur.add(lhs <= rhs)

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
                     "tpkfix", "upkdef", "bidfix", "out_bid")
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

        def recourse_value(slack_tol=0.0):
            # the value passed to the Benders bound and cut: the true recourse plus
            # the penalty on any GENUINE slack. Negative slack within the solver's
            # feasibility tolerance is clamped to zero, so a large penalty cannot turn
            # that drift into a spurious reduction (which would poison the bound).
            # ``slack_tol`` (used only by the forward-pass UB) ignores per-constraint slack
            # below the tolerance, so a binarisation/feasibility-tolerance-scale residual
            # (e.g. a grid-mismatch of ~1e-5) is not amplified by the 1e7 penalty into a
            # meaningless upper bound; genuine infeasibility (slack >> tol) is still counted.
            pos = sum(s for s in (float(value(v)) for v in slack_vars) if s > slack_tol)
            return float(value(real_recourse)) + penalty * pos

        fix = {("e", g): sub.bfix_e[g] for g in egc}
        fix.update({("h", g): sub.bfix_h[g] for g in hgc})
        _bfix = {"Se": sub.sefix, "Sh": sub.shfix, "St": sub.stfix}
        for (kind, kk, g) in bnd_names:
            fix[(kind, kk, g)] = _bfix[kind][kk, g]
        for key in thr_keys:
            fix[("t",) + key] = sub.tpkfix[key]
        for (_tag, kk, u, bt) in bid_names:
            fix[("Bid", kk, u, bt)] = sub.bidfix[kk, u, bt]

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
            for (_tag, kk, u, bt) in bid_names:
                sub._bid[kk, u, bt] = x_hat[("Bid", kk, u, bt)]

        xcopy = {("e", g): sub.vEleGenInvest[g] for g in egc}
        xcopy.update({("h", g): sub.vHydGenInvest[g] for g in hgc})
        # full copy-var map for every linking key (needed by the Lagrangian cut_mode):
        # the boundary-inventory copies and the peak-threshold copies, matching `fix`.
        _copyvar = {"Se": sub.Secopy, "Sh": sub.Shcopy, "St": sub.Stcopy}
        for (kind, kk, g) in bnd_names:
            xcopy[(kind, kk, g)] = _copyvar[kind][kk, g]
        if thresholds:
            for key in thr_keys:
                xcopy[("t",) + key] = sub.tpkcopy[key]
        if bid_comp:
            for (_tag, kk, u, bt) in bid_names:
                xcopy[("Bid", kk, u, bt)] = sub.Bidcopy[kk, u, bt]
        # keys this block actually couples on (for the Lagrangian cut_mode): all investment,
        # its own incoming (k-1) / outgoing (k) boundaries, and the thresholds its window hits.
        active_keys = ([("e", g) for g in egc] + [("h", g) for g in hgc]
                       + [(kind, kk, g) for (kind, kk, g) in bnd_names if kk in (k - 1, k)])
        if thresholds:
            active_keys += [("t", ti, sub_maps[ti][nn], it) for (ti, it, nn) in thr_u]
        if bid_comp:
            active_keys += [("Bid", kk, u, bt) for (_tag, kk, u, bt) in bid_names if kk in (k - 1, k)]
        return {"model": sub, "xcopy": xcopy, "fix": fix, "set_xhat": set_xhat,
                "obj": sub.benders_obj, "recourse": recourse_value, "active_keys": active_keys}

    def _forward_ub(x_hat, subs, opt_sub):
        # SDDiP forward pass for a clean upper bound. Fix the investment (and the peak
        # thresholds) to the master point and solve the blocks in time order: each block's
        # INCOMING boundary is fixed to the previous block's realised OUTGOING state and its
        # own outgoing boundary is left FREE, so the block chooses its end inventory. The
        # boundary states are then feasible by construction (no grid-mismatch elastic
        # penalty), so the summed real recourse is a true upper bound -- unlike fixing every
        # boundary to the binarised-grid master value, which the blocks cannot meet exactly.
        # For the reserve-endurance coupling there is one extra step: each sending block's
        # terminal endurance rows are re-activated for this primal sweep (see below), so it
        # retains the energy needed to back its trailing bid in the next block.
        from pyomo.environ import value as _val
        prevE, prevH, prevHt = dict(initE), dict(initH), dict(initHt)
        prevBid = {(u, bt): 0.0 for (u, bt) in bid_comp}   # carried trailing bids
        total = 0.0
        for k in range(K):
            s = subs[k]; m = s["model"]
            s["set_xhat"](x_hat)
            # switch the block out of its Lagrangian state into a primal forward solve.
            if hasattr(m, "_lag_obj"):
                m._lag_obj.deactivate()
            s["obj"].activate()
            for g in egc:
                m.bfix_e[g].activate()
            for g in hgc:
                m.bfix_h[g].activate()
            for key in thr_keys:
                m.tpkfix[key].activate()
            if k > 0:                              # incoming boundary = previous outgoing
                for g in egs:
                    m._se[k - 1, g] = prevE[g]; m.sefix[k - 1, g].activate()
                for g in hgs:
                    m._sh[k - 1, g] = prevH[g]; m.shfix[k - 1, g].activate()
                for sn in hts:
                    m._st[k - 1, sn] = prevHt[sn]; m.stfix[k - 1, sn].activate()
                for (u, bt) in bid_comp:           # incoming trailing bid = previous outgoing
                    m._bid[k - 1, u, bt] = prevBid[(u, bt)]; m.bidfix[k - 1, u, bt].activate()
            # re-activate this (sending) block's terminal endurance rows for the primal
            # heuristic only: they back the trailing bid with the block's own ending
            # inventory, so the greedy sweep retains enough energy and the next block can
            # back the bid -- otherwise the exact split (which moves that backing to the
            # next block) leaves this block free to end empty and the UB blows up on slack.
            for cn in getattr(m, "_fwd_end_rows", []):
                getattr(m, cn).activate()
            # this block's outgoing boundary (index k) stays unfixed: the block picks it.
            _solve_model(opt_sub, m)
            # forward-pass UB: ignore per-constraint slack below a small tolerance, so a
            # binarisation grid-mismatch residual is not amplified by the 1e7 penalty.
            total += s["recourse"](slack_tol=float(cfg.extra.get("fwd_slack_tol", 1e-4)))
            if k < K - 1:                          # read the realised outgoing state
                for g in egs:
                    prevE[g] = float(_val(m.Secopy[k, g]))
                for g in hgs:
                    prevH[g] = float(_val(m.Shcopy[k, g]))
                for sn in hts:
                    prevHt[sn] = float(_val(m.Stcopy[k, sn]))
                for (u, bt) in bid_comp:
                    prevBid[(u, bt)] = float(_val(m.Bidcopy[k, u, bt]))
            # restore the Lagrangian state (active-key fixings off, _lag_obj on) for the
            # next cut-generation pass.
            for cn in getattr(m, "_fwd_end_rows", []):
                getattr(m, cn).deactivate()   # back to the exact-split state
            s["obj"].deactivate()
            if hasattr(m, "_lag_obj"):
                m._lag_obj.activate()
            for g in egc:
                m.bfix_e[g].deactivate()
            for g in hgc:
                m.bfix_h[g].deactivate()
            for key in thr_keys:
                m.tpkfix[key].deactivate()
            if k > 0:
                for g in egs:
                    m.sefix[k - 1, g].deactivate()
                for g in hgs:
                    m.shfix[k - 1, g].deactivate()
                for sn in hts:
                    m.stfix[k - 1, sn].deactivate()
                for (u, bt) in bid_comp:
                    m.bidfix[k - 1, u, bt].deactivate()
        return total

    return benders_solve(make_master, make_subproblem, blocks, config=cfg, solver=solver,
                         cut_mode=cut_mode,
                         ub_recourse=(_forward_ub if cut_mode == "lagrangian" else None))


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
