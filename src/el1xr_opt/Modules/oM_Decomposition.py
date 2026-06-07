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

    M = make_master()
    subs = {b: make_subproblem(b) for b in blocks}
    names = list(M["x"].keys())

    best_ub = float("inf")
    gap = float("inf")
    it = 0
    for it in range(1, cfg.max_iterations + 1):
        opt.solve(M["model"])
        lb = value(M["model"].obj)
        x_hat = {n: float(value(M["x"][n])) for n in names}
        theta_hat = {b: float(value(M["theta"][b])) for b in blocks}
        first_stage_cost = lb - sum(theta_hat.values())

        recourse = 0.0
        new_cuts = []
        for b in blocks:
            sub = subs[b]
            sub["set_xhat"](x_hat)
            opt.solve(sub["model"])
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


def solve_benders(model, optmodel, solver, config: BendersConfig | None = None):
    """Benders entry point for the el1xr operational+investment model.

    Not wired yet: it will build the master (investment + recourse variables) and,
    per ``partition_blocks`` block, an operating subproblem with a free copy of the
    investment variables fixed to the master values, then call :func:`benders_solve`.
    The generic machinery in :func:`benders_solve` is implemented and validated
    (see ``tests/test_benders.py``); this wrapper is the remaining el1xr-specific
    wiring.
    """
    raise NotImplementedError(
        "el1xr Benders wiring is pending; the generic solver is benders_solve(). "
        "See docs/decomposition.md and tests/test_benders.py."
    )
