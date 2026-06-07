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

## Where to run, and which solver

- **Tests / CI**: one week of operation (168 load levels) on the open-source
  HiGHS solver. One week is enough to exercise the model, and HiGHS needs no
  licence, so it runs on the shared CI machines. The full test suite is about two
  minutes this way.
- **Local development**: use Gurobi (`--solver gurobi`). It gives the same answer
  as HiGHS on these cases (checked: the linear cases match to the last digit) and
  is much faster on the large unit-commitment instances. A licence lives at
  `~/gurobi.lic`.
- **Full-year "proper" runs**: these are large and belong on a bigger machine
  (the Comillas desktop, 64 GB), not on a laptop or in CI. Keep CI on the short
  horizon and move the full-year studies to that machine.

## Should we stay on Pyomo, or move to another modelling tool?

This matters because, as measured above, **building the model is the bottleneck
for the linear cases, and Pyomo's Python loops that emit constraints are the slow
part**. Faster solving (Gurobi, Benders) does not help the build; a faster
*model builder* does. The options, with the trade-offs that matter here:

- **linopy** (Python, builds vectorised over `xarray` arrays). About 4-6x faster
  to build than Pyomo and uses roughly half the memory, same language, supports
  HiGHS and Gurobi and integer variables, and it is the engine PyPSA uses at
  continental scale, so it is proven on power-system models. LP duals come back
  directly; duals for unit-commitment cases (the marginal prices) need a
  fix-and-resolve step that must be designed in. **Lowest-risk option and the
  front-runner.**
- **pyoframe** (Python, builds over Polars data frames; this is most likely the
  "polar-high" idea). Backed by a very fast low-level core, good at the sparse,
  irregular index sets that unit commitment produces, MILP supported, HiGHS and
  Gurobi. But it is young with a small community, and its support for duals is not
  documented - verify that before relying on it. Higher reward, higher risk.
- **JuMP** (Julia). Reputed the fastest builder (around 15-20x over Pyomo on
  synthetic benchmarks) and the most mature, with strong unit-commitment
  libraries. The cost is a full rewrite in Julia and leaving the Python ecosystem.
  Note: when measured on our own storage family (on the latest Julia, 1.12.6) it
  was only about 3-5x (see the step-3 results), so its build-speed edge did not
  reproduce here. Worth it only if we commit to Julia for its broader ecosystem,
  not for build speed alone.
- **Staying on Pyomo and tuning it** (`LinearExpression` / the kernel layer)
  realistically buys 1.5-3x on the build, not the 5-30x the others can. It is a
  half-day experiment, so it is worth quantifying first as the cheap baseline.

Suggested path: steps (1) and (2) below are now done and measured (see the table
that follows); the remaining work is steps (3)-(4).

1. *(done)* Quantify the cheap Pyomo `LinearExpression` fix - result: about
   1.4-1.5x at scale, a small steady win, not enough on its own.
2. *(done)* Port one constraint family (the storage inventory balance) to linopy
   and measure on a full-year case - result: 23-60x faster to build.
3. *(done)* Port a **harder** family (the storage-cycle-window sum) to linopy and
   **pyoframe** and measure again - result: linopy 11-37x, pyoframe only 3-3.6x;
   marginal-price duals come back from both (for an LP). See the second table.
4. Decide. linopy is the front-runner: biggest measured build win, keeps Python
   and HiGHS/Gurobi, duals work for LP. Still to design before a full migration:
   MILP duals (a fix-and-resolve step) for the unit-commitment marginal prices.
   JuMP stays a fallback only if we adopt Julia for other reasons.

Full details and sources are in the reference note
`amls_build_speed_pyomo_alternatives` in the research memory.

### Measured prototype (steps 1 and 2, storage inventory balance)

`benchmarks/build_speed_storage.py` builds the storage inventory balance - one of
the biggest constraint families - three ways and times only the model build. All
three solve to the same objective on a small forced-charging case (2.105263), so
they are the same model. Build time on the **Comillas desktop** (Intel i7-8700,
6c/12t, the machine used for full-year runs; best of two builds):

| size (time x units) | constraints | pyomo-rule | pyomo-LinearExpression | linopy |
|---------------------|-------------|------------|------------------------|--------|
| 168 x 10            | 1 680       | 0.031 s    | 0.014 s (2.3x)         | 0.096 s (0.3x) |
| 1 000 x 10          | 10 000      | 0.292 s    | 0.213 s (1.4x)         | 0.095 s (3.1x) |
| 8 760 x 10          | 87 600      | 2.611 s    | 1.792 s (1.5x)         | 0.114 s (23x)  |
| 8 760 x 50          | 438 000     | 12.589 s   | 9.089 s (1.4x)         | 0.211 s (60x)  |

(The development Mac is faster per core, so its absolute times are about 3-4x
smaller, but the ratios are the same.)

Two clear findings:

- **`LinearExpression` is a small, steady win, not the lever.** It builds about
  1.4-1.5x faster at full-year scale - real, but far short of what is needed. The
  cost that dominates is the per-element Python loop over the index set, and
  `LinearExpression` only speeds up the expression *body*, not the loop.
- **linopy scales.** Its build time is almost flat as the constraint count grows
  (0.11 s at 87k, 0.21 s at 438k) because it builds the whole family as one
  vectorised array operation rather than element by element. At full-year scale it
  is 23-60x faster to build.

Caveats: this is one constraint family with a simple one-step recurrence. The
harder family below is the more realistic test.

### Measured prototype (step 3, harder cycle-window family)

`benchmarks/build_speed_storage_window.py` builds the more realistic storage
balance: inventory at each cycle boundary equals the previous boundary plus the
**sum over a window of steps in that cycle** (a windowed sum plus a block lag,
which is what is genuinely hard to vectorise). Five builders (four Python plus
JuMP/Julia), all solving to the same objective (2.105263) on the small
forced-charging case. Build time on the **Comillas desktop** (best of two; B
cycles x C=24 steps x G units; JuMP on the latest Julia, 1.12.6, timed after a
warm-up build to exclude Julia's first-call compilation):

| size (B x C x G) | rows | pyomo-rule | LinearExpression | linopy | pyoframe | JuMP (1.12.6) |
|------------------|------|------------|------------------|--------|----------|------|
| 365 x 24 x 10    | 3 650 | 0.969 s   | 0.821 s (1.2x)   | 0.085 s (11x) | 0.269 s (3.6x) | 0.193 s (5.0x) |
| 365 x 24 x 50    | 18 250 | 4.483 s  | 3.813 s (1.2x)   | 0.123 s (37x) | 1.471 s (3.0x) | 1.525 s (2.9x) |

Findings on the harder family:

- **linopy still wins big but less than the easy case** - 11-37x here vs 23-60x on
  the one-step family. The windowed sum and the block lag add overhead, as
  expected, but a vectorised builder is still the clear lever.
- **pyoframe is viable but well behind linopy here** - 3-3.6x. Its Polars-based
  block lag (shift the index, then realign) is less ergonomic than linopy's
  `xarray` `.shift`, and the build is slower on this time-coupled structure.
- **JuMP does not win on build time for this family** - about 2.9-5.0x, in
  pyoframe's range and well behind linopy, and its build time grows roughly with
  the constraint count while linopy's stays nearly flat. The synthetic-benchmark
  "JuMP ~15-20x" does not carry over to this windowed, dense-regular structure.
  This was checked on the latest Julia (1.12.6); an earlier run on the box's old
  Julia 1.8.5 gave essentially the same numbers, so it is not a stale-version
  artifact. Fair caveats remain: JuMP builds element by element with the
  `@constraint` macro, which a dense-regular family flatters linopy's array
  approach but suits sparse, irregular constraints better than masking does; and
  JuMP's real strengths are the in-memory solver interface (no LP-file writing),
  fast warm re-solves, and its unit-commitment libraries - none of which a
  build-time micro-benchmark captures. So this measures one thing (build time of
  one regular family), and on that one thing JuMP does not justify a Julia rewrite.
- **`LinearExpression` is a steady ~1.2x** - confirms it is not the lever.
- **Marginal prices work in linopy and pyoframe** - the shadow price on the
  inventory balance comes back identically from linopy (`constraint.dual`) and
  pyoframe (`constraint.dual`), -1.052632 in the probe. That settles the dual
  question for LP cases; the unit-commitment (MILP) marginal prices would still
  need a fix-and-resolve step in either tool.

### Honest correction: construct-only vs end-to-end (construct + export)

The build numbers above (and the scaling table below) time **modelling-layer
construction only**. They exclude the step where the model is handed to the solver
— Pyomo writes an LP/NL file or loads an in-memory matrix; linopy assembles a
scipy sparse matrix. Both tools defer that step, so a construct-only number
flatters the tool with the cheaper construct. A re-check (`build_speed_endtoend.py`)
measured the full path to solver-ready and found two things the construct-only
metric hid:

- linopy's own matrix assembly is non-trivial and grows with size (it became the
  larger part of linopy's time at scale), and
- Pyomo's **export is its slowest part** (LP/NL writing or the appsi in-memory
  load), which construct-only excluded entirely.

End-to-end on Comillas (construct + export to solver-ready):

| rows   | linopy total | Pyomo (LP file) | Pyomo (appsi in-memory) |
|--------|--------------|-----------------|-------------------------|
| 3 650  | 0.79 s       | 3.9 s (5.0x)    | 4.9 s (6.2x)            |
| 18 250 | 1.26 s       | 13.0 s (10.4x)  | 20.6 s (16.4x)          |
| 50 000 | 3.61 s       | 36.4 s (10.1x)  | 71.1 s (19.7x)          |

So the honest headline is **linopy is ~5–20x faster end-to-end** (vs the
construct-only 37–49x), the multiple growing with size and with Pyomo's export
path (appsi — which the test suite uses — is the slower one). The linopy model was
verified complete and correct: variable and constraint counts match exactly and it
solves to the same objective, so the speed is real, not a truncated or lazy model.
The construct-only ratios remain a valid measure of *construction* cost, but the
end-to-end figure is the one to quote. (The construct-only numbers are also larger
on the older Comillas CPU, where Pyomo's pure-Python loops suffer more than
linopy's vectorised numpy.)

### Scaling to very large models (rows and columns)

Pushing the same family far past any real case (Comillas; pyomo / JuMP / pyoframe
build element by element, linopy builds vectorised). Rows = constraints, columns =
variables; this family has about `2C+1` columns per row. **These are construct-only
times** (see the end-to-end correction above; the real-world multiple is ~5–20x,
not the construct-only ratios shown here).

| rows       | columns | pyomo-rule | linopy        | pyoframe   | JuMP        |
|------------|---------|------------|---------------|------------|-------------|
| 50 000     | 2.45 M  | 11.6 s     | 0.24 s (49x)  | 4.2 s (2.8x) | 5.0 s (2.3x) |
| 1 000 000  | 49 M    | (OOM)      | 3.4 s         | 96 s       | 141 s       |
| 10 000 000 | 490 M   | (OOM)      | 29 s          | (impractical) | (impractical) |

Column-heavy shape (only 1 000 rows but each constraint sums C=5 000 steps, so
~10 M columns): pyomo-rule 46 s, **linopy 0.95 s (49x)**, pyoframe 17.5 s (2.6x).

Two things stand out:

- **linopy's lead grows with size** - 11x at 3.6k rows, 49x at 50k, and at 1M+
  rows it is the only tool that stays in seconds while the element-wise builders
  take minutes or run out of memory. It built a 490-million-variable LP in 29 s.
- **element-wise building does not scale, in any language** - at 1M rows JuMP
  (141 s) is even slower than pyoframe (96 s) and ~40x slower than linopy, and
  Pyomo runs out of memory. Wide constraints (the column-heavy case) hurt the
  per-element builders most, because they emit every term in Python or Julia,
  whereas linopy reduces over the cycle dimension in one array operation.

So at the scales where build time actually matters, the case for a vectorised
builder is even stronger, and JuMP's element-wise `@constraint` does not rescue
it. (These extreme sizes are well beyond a realistic el1xr_opt case; they are a
stress test of how each tool scales, not a target model size.)

Overall direction (now measured across all the candidates): the build-time lever
is a vectorised builder, and **linopy is the front-runner** - largest measured win
by a wide margin, same language, HiGHS/Gurobi, working LP duals. pyoframe and JuMP
both land around 3-4x on this family; JuMP's headline advantage from synthetic
benchmarks did not reproduce here, which (together with the cost of a full Julia
rewrite) argues against switching languages for build speed alone. The remaining
design item before a full migration to linopy is MILP dual extraction for
marginal prices.
