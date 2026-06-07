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
- `el1xr_benders(dir, case, date, ...)` — the el1xr-specific entry point. It reads
  the investment structure with `build_structure` (sets and parameters only), then
  builds the investment master (build fractions plus one recourse variable per
  `(period, scenario)`
  block) and, per block, an operating subproblem restricted to that scenario with
  the investment variables fixed (their fixing-constraint duals give the cuts), and
  calls `benders_solve`. Validated to reach the exact monolithic optimum on a
  two-scenario case (`tests/test_benders_el1xr.py`).

### Feasibility cuts via an elastic penalty

The el1xr operating model is **not** complete-recourse with respect to investment:
too little investment can make a block's operating subproblem infeasible, and an
optimality-cut-only loop cannot steer the master away from such a point. The
subproblem builder handles this by adding a penalised slack to every operating
constraint except the investment-fixing ones, so the block is always feasible.

- When the fixed investment is feasible, the slacks stay at zero, the recourse
  value is the true operating cost, and the dual is the usual optimality cut.
- When it is infeasible, the slacks turn on, the recourse value jumps by the
  penalty, and the fixing-constraint dual becomes a feasibility (steering) cut that
  pushes the master toward feasible investment.

The penalty is large compared with any real operating cost, so at the optimum no
slack is used and the Benders optimum equals the monolithic optimum. This is the
standard exact-penalty alternative to a separate feasibility-cut pass, and it keeps
`benders_solve` a pure optimality-cut loop. The penalty is configurable via
`BendersConfig.extra["feasibility_penalty"]`.

### Parallel subproblem solve

The subproblems are independent given the investment decision, so each Benders
iteration solves them in parallel. Pyomo solvers are **not thread-safe** (shared
model-writer, tempfile-manager and solver state — a `ThreadPoolExecutor` deadlocks
after the first solve), so the parallelism is by **process**, not thread. With
`BendersConfig.n_workers > 1`, `el1xr_benders` starts a pool of worker processes;
each worker builds and owns a round-robin slice of the blocks once and reuses them
across iterations. The master loop sends the trial investment `x_hat` to every
worker over a pipe and collects each block's cost and fixing-constraint duals. The
result is identical to the sequential solve (the iteration count can differ because
LP dual degeneracy yields different but equally valid cuts).

`benders_solve` stays generic: parallelism enters through an optional
`solve_blocks(x_hat) -> {block: (cost, duals)}` callback. When it is given the
subproblems are not built in the main process (the pool owns them); when it is
`None` the blocks are built and solved sequentially in-process (the default).

Measured on the remote desktop (12 logical CPUs, Gurobi) for an 8-block case
(8 scenarios, 48-hour horizon):

| workers | wall time (s) | speed-up |
|--------:|--------------:|---------:|
| 1       | 122.0         | 1.00     |
| 2       | 75.6          | 1.61     |
| 4       | 47.9          | 2.55     |
| 8       | 41.2          | 2.96     |

Every run reached the same objective (2832.142) in the same number of iterations.
The speed-up flattens past four workers because of a serial floor.

`el1xr_benders` reads the problem structure (candidate lists, costs, the block
list) with `build_structure` — `data_processing` only, no variables/constraints —
instead of a full operating-model build. This removes work that was otherwise
thrown away, but it is a small saving: the build cost is dominated by
`data_processing` (reading the multi-scenario CSVs and building the parameter
series), not by the model construction. Measured at eight scenarios, the structure
read is about 2.9 s versus 3.3 s for the full build (~10%).

The bigger lever was per-block scenario subsetting, now done. Each block solves a
single-scenario subproblem, but the block build used to keep **all** scenarios in
the scenario dimension dict, so `data_processing` built every parameter over the
full N-scenario set product — for every one of the N blocks. That is roughly
quadratic in the scenario count. `_build_block` now produces a genuine
single-scenario case (the kept scenario is the only one in the dict, and the other
scenarios' rows are dropped from the data files; the scenario column is found by
content, not position, so node-indexed files like the networks are left alone), so
each block build is constant in the scenario count. The kept scenario's data —
including its probability, which `data_processing` reads unnormalised — is
untouched, so the subproblem and the optimum are unchanged.

End-to-end Benders wall-clock, sequential, old vs new block build (8/16/24
scenarios; same optimum every time):

| scenarios | old (s) | new (s) | speed-up |
|----------:|--------:|--------:|---------:|
| 8         | 57.3    | 23.6    | 2.4      |
| 16        | 214.7   | 57.5    | 3.7      |
| 24        | 511.2   | 100.5   | 5.1      |

The new build scales about linearly with the number of blocks while the old one
grew quadratically, so the gain widens with the scenario count — exactly the regime
a stochastic study runs in. This shortens both the sequential and the parallel
solve (it is per-block work), and it stacks with the process parallelism above.

### Combined: subsetting plus parallel workers

The two optimizations stack. Re-running the same eight-block case on the remote
desktop (Gurobi) with the single-scenario block build in place, across worker
counts, against the earlier numbers without subsetting (same objective every run):

| workers | without subsetting (s) | with subsetting (s) | total vs 1 worker, no subsetting |
|--------:|-----------------------:|--------------------:|---------------------------------:|
| 1       | 122.0                  | 65.3                | 1.9                              |
| 2       | 75.6                   | 41.0                | 3.0                              |
| 4       | 47.9                   | 28.2                | 4.3                              |
| 8       | 41.2                   | 25.5                | 4.8                              |

Subsetting gives about 1.9x on the sequential build and the worker pool about 2.6x
on top, for roughly 4.8x end to end (122 s to 25.5 s). The parallel speed-up alone
is a little lower with subsetting than without (2.6x vs 3.0x at eight workers),
because subsetting shrinks the per-block work, so the fixed costs that do not
parallelize — worker start-up, the master solves, the pipe traffic — are a larger
share of a now-smaller total. The absolute wall-clock is what matters, and it is
markedly lower. At higher scenario counts the subsetting factor grows (it is
roughly linear-vs-quadratic), so the combined gain widens further.

### Temporal block splitting with storage-boundary linking

The scenario split gives one subproblem per `(period, scenario)`, each over the
whole horizon. For long horizons the next step is to split the time axis too:
each `(period, scenario)` operating problem becomes a chain of contiguous time
blocks. Unlike scenarios, time blocks are **not** independent — they are coupled
*sequentially* by the storage inventory carried across each boundary.

**The linking variable is the boundary inventory.** In el1xr the inventory balance
(`eEleInventory` / `eHydInventory`) ties `vEleInventory[n]` to `vEleInventory[n -
cycle]`, where `cycle` is the storage's `CycleTimeStep` (1 for hourly storage, 24
for daily, 168 for weekly). When a block boundary falls between `n - cycle` and
`n`, that earlier inventory is in the previous block. So for hourly storage the
boundary is a single inventory value per storage unit; for daily/weekly storage the
block boundaries should be aligned to the cycle so the boundary stays a single
value per unit.

**The decomposition is a Benders with the boundary inventories in the master.**
The boundary inventory levels are complicating / linking variables, exactly like
investment in the scenario split — except each one is shared by just two adjacent
blocks instead of all of them. The master holds the boundary levels (and
investment); block `t` is given its incoming and outgoing boundary levels as fixed
values and solves its slice of the horizon; the duals of those two fixing
constraints are its cut. A block can be infeasible for a bad pair of boundary
levels, so the elastic-penalty relaxation already used for the scenario subproblems
provides the feasibility (steering) cuts here too.

This needs no new solver: `benders_solve` already supports it, because a temporal
subproblem simply depends on two complicating variables (its two boundary states)
instead of all of them — the duals for every other boundary are zero. This is
validated against the monolithic optimum on a small multistage storage problem in
`tests/test_benders_temporal.py` (cyclic storage, boundary levels in the master,
elastic blocks), the temporal analogue of `tests/test_benders.py`.

**Wiring it into el1xr (the remaining step).** Each block is built over its window
of load levels (truncate the `Duration` to the window, as the block build already
does for scenarios). Two boundary couplings then need handling per storage unit:
the **outgoing** inventory `vEleInventory[last level]` is fixed to the master value
(a fixing constraint, like the investment fix); the **incoming** inventory must
enter the window's first inventory balance, which today uses the constant
`pEleInitialInventory`. So the first-level balance is replaced by one that reads a
mutable incoming-inventory parameter set from the master each iteration (the
`set_xhat` step), rather than rebuilding the block. The same applies to
`vHydInventory`. Blocks should be aligned to the storage `CycleTimeStep`. The
`partition_blocks(..., n_time_blocks)` helper and the `linking` entry of
`first_stage_components()` already mark out this structure.

## 7. Suggested order of work

1. Benders over `(period, scenario)` with investment in the master, reusing the
   existing monolithic build per subproblem. Validate the bound matches the
   monolithic optimum on a small case. **Done.**
2. Parallelize the subproblem solves. **Done** (process pool).
3. Per-block scenario subsetting so each block builds one scenario, not all.
   **Done.**
4. Temporal block splitting with boundary-storage linking. Algorithm validated
   (`tests/test_benders_temporal.py`); el1xr wiring (windowed build + mutable
   incoming inventory) is the remaining step.
5. Only then consider the arc/asset reformulation and Dantzig-Wolfe, together,
   as a larger modernization.
