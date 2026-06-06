# Computational efficiency: findings and recommendation

This note records a small, measured study of where el1xr_opt spends its time and
what the "blocks" idea can and cannot do for it. It was written alongside the
DuckDB input/output refactor.

## What was measured

Full-year Home1 (8736 load levels), built and solved with HiGHS:

| Stage                  | Time   |
|------------------------|--------|
| Read and process data  | 1.5 s  |
| Define variables       | 6.6 s  |
| Define objective parts | 1.3 s  |
| **Define constraints** | **17.0 s** |
| Solve                  | 11.5 s |
| **Total**              | **~38 s** |

So for an LP case, **building the model takes longer than solving it** (about
26 s build vs 11.5 s solve), and constraint construction is two thirds of the
build. For a unit-commitment case (EEM26) the picture flips: the build is a bit
larger and the **solve** dominates (it runs into the solver time limit).

## Two different things are called "blocks"

1. **Arc / Pyomo `Block` modelling** (the `el1xr_opt_block2` experiment).
   This is a code-organisation pattern: one block per asset, one per flow. It
   makes the formulation more modular and prevented a cost-aggregation bug, but
   it does **not** reduce build time or solve time — its on-demand inflow /
   outflow expressions can actually be slower to build. Not worth porting for
   speed.

2. **Temporal block decomposition** (the IJEPES paper's approach).
   Here the time steps are split into blocks and the problem is solved by a
   Benders-style scheme whose subproblems run in parallel, with special handling
   of the storage level at each block boundary so long-term storage still works.
   This targets **solve time** on large and stochastic problems and is the
   genuinely valuable idea.

## Small change made now

The constraint rules sliced `list(model.n2)` by position on every call, which
rebuilds the whole load-level list each time. It is now built once at the top of
`create_constraints`. The slicing is identical, so results are unchanged. The
win is modest (EEM26 constraint build 29.1 s -> 27.6 s, about 5 %; negligible on
Home1 where those rules are mostly skipped), but it is free and removes a
quadratic-scaling trap on cases with long storage cycles or long minimum
up/down times.

## What actually moves the needle

- **Fewer load levels** is the biggest build-time lever. The model already
  supports time aggregation through `pTimeStep`; representative periods would cut
  both build and solve time roughly in proportion to the number of load levels
  removed.
- **Temporal block decomposition (Benders)** is the biggest solve-time lever for
  the large unit-commitment and stochastic cases. openTEPES already ships a
  Benders solver (`openTEPES_ProblemSolvingBenders`) that is a good template. The
  el1xr_opt index sets decompose naturally by period and scenario; the storage
  cycle constraints couple time, so the block-boundary storage handling from the
  paper is the part that needs care. This is a feature in its own right, not a
  one-session change.
- The DuckDB result store added in this refactor helps a future decomposition:
  subproblem results are written and queried as structured tables instead of
  many CSV files.

## Recommendation

Keep the constraint hoist. Treat temporal block decomposition as the next
efficiency project, starting from the openTEPES Benders module and the paper's
block-boundary storage formulation. Do not adopt the arc/Block modelling style
for performance reasons.
