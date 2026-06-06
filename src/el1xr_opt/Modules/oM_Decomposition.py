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


def solve_benders(model, optmodel, solver, config: BendersConfig | None = None):
    """Solve by Benders decomposition (not implemented).

    Planned: investment in the master; one operating subproblem per block from
    :func:`partition_blocks`, solved in parallel; subproblem duals build optimality
    and feasibility cuts for the master; iterate to ``config.relative_gap``. Mirror
    openTEPES ``openTEPES_ProblemSolvingBenders``. Validate the bound against the
    monolithic optimum on a small case before trusting it.
    """
    raise NotImplementedError(
        "Benders decomposition is not implemented yet; see docs/decomposition.md"
    )
