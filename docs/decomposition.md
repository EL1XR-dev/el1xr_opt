# Decomposition and parallelization — design notes

This note lays the groundwork for solving large el1xr_opt instances faster by
splitting the problem into blocks that can be built and solved in parallel, and
by applying a decomposition method (Benders, and optionally Dantzig-Wolfe /
column generation). It is a plan and a scaffold (`oM_Decomposition.py`), not a
working decomposition solver yet.

It also answers a related modelling question: is it worth moving from a nodal
balance to a per-asset (arc/flow) balance?

## 1. Where the time goes (recap)

Measured on a full-year case (see `computational_efficiency.md`): for a linear
case, **building** the model takes longer than solving it; for a
unit-commitment case the **solve** dominates and can hit the time limit. So both
"prepare for parallelization during building" and "decompose the solve" are
worth doing, and they target different bottlenecks.

## 2. The block structure of the model

The operating part of the model is almost separable by period and scenario.
Most constraints are indexed over `(period, scenario, load level, ...)` and only
couple within one `(period, scenario)`. Two things couple across blocks:

- **Investment / sizing** decisions (`vEleGenInvest`, `vHydGenInvest`). These are
  the *first-stage* (complicating) variables: one set of build decisions feeds
  every operating block.
- **Storage** carried across time (the inventory balance links load level `n` to
  earlier load levels). Within a `(period, scenario)` this is internal; if we
  also split the time axis into blocks, the storage level at each block boundary
  becomes a *linking* variable between consecutive time blocks.

This is exactly the structure the decomposition methods below exploit.

## 3. Asset balance vs nodal balance — is it worth changing?

Today the model enforces a **nodal** balance (everything at a node sums to zero).
The alternative (used in the `el1xr_opt_block2` experiment and in Tulipa) gives
every **asset** its own balance and represents each connection as an **arc**
carrying a flow, with a generic "carrier" label (electricity, hydrogen, heat).

What changes, honestly:

- **It does not change the optimum.** Both formulations describe the same
  feasible region, so the cost is the same. It is not a solver-speed trick on its
  own — the arc form adds flow variables and per-asset balance constraints, so a
  naive version is slightly *larger* to build.
- **It improves modularity and multi-vector reach.** Each asset and each carrier
  is handled uniformly, which removes the large electricity-vs-hydrogen code
  duplication and makes adding the **heat** sector mostly a matter of adding a
  carrier — directly useful given the planned heat work.
- **It makes the block structure explicit.** A per-asset, arc-based model is
  naturally block-angular (one block per asset, coupled through node balances and
  investment). That is the structure Benders and Dantzig-Wolfe want, so the arc
  form and decomposition reinforce each other.

Recommendation: treat the arc/asset-balance form as a **formulation
modernization for maintainability and multi-vector support** (and as a clean base
for decomposition), not as a standalone speed-up. Do it deliberately, on its own,
with the output-extraction and investment layers ported and checked against the
current results — not mixed into an unrelated change.

## 4. Which decomposition fits

- **Benders decomposition (recommended first).** Put the investment / sizing
  decisions in the master problem and the operating cost of each
  `(period, scenario)` in a subproblem. The subproblems are independent given the
  build decisions, so they solve in parallel; their dual information builds cuts
  for the master. This matches a capacity-expansion-with-operations problem
  directly. openTEPES already ships a Benders solver
  (`openTEPES_ProblemSolvingBenders`) that is a good template.
- **Temporally split Benders (for long horizons).** Additionally split the time
  axis into blocks and solve each block as a subproblem, passing the storage
  level at block boundaries between them. This is the approach in the reference
  paper and is the lever when the *solve* (not the build) dominates.
- **Dantzig-Wolfe / column generation.** Natural when the problem is
  block-angular with a few linking constraints and many similar blocks (e.g. many
  scenarios or many identical assets). More machinery than Benders and a better
  fit once the model is already in arc/asset form. Consider after Benders.

## 5. Parallelization, before / during / after building

- **Before building** — partition the work: compute the `(period, scenario)`
  blocks (and optional time blocks) up front, and read only the data each block
  needs. `partition_blocks()` in `oM_Decomposition.py` returns this partition.
- **During building** — build each block's Pyomo sub-model independently (one per
  process), instead of one monolithic model. This also cuts peak memory.
- **After building** — solve the subproblems concurrently, collect their costs
  and duals, update the master, and repeat until the bound gap closes; then
  assemble the results. The DuckDB result store added in this refactor is a good
  place to write per-block results from parallel workers.

## 6. Scaffold provided

`src/el1xr_opt/Modules/oM_Decomposition.py` provides:

- `partition_blocks(...)` — split `(periods, scenarios)` (and optionally the time
  axis) into independent block descriptors (this is real and usable now).
- `first_stage_components()` — names the complicating variables (investment) and
  the time-block linking variables (boundary storage).
- `benders_solve(make_master, make_subproblem, blocks, config)` — a **working**
  generic multi-cut L-shaped Benders solver (optimality cuts from the subproblem
  fixing-constraint duals), validated against the monolithic optimum on a small
  stochastic capacity-expansion problem in `tests/test_benders.py`. The callback
  interface is the template for the el1xr investment/operating split.
- `solve_benders(...)` — the el1xr-specific entry point, still to be wired (build
  the investment master and per-block operating subproblems, then call
  `benders_solve`).

## 7. Suggested order of work

1. Benders over `(period, scenario)` with investment in the master, reusing the
   existing monolithic build per subproblem. Validate the bound matches the
   monolithic optimum on a small case.
2. Parallelize the subproblem solves.
3. Add temporal block splitting with boundary-storage linking for long horizons.
4. Only then consider the arc/asset reformulation and Dantzig-Wolfe, together,
   as a larger modernization.
