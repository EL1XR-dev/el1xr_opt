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
- **JuMP** (Julia). The fastest builder (around 15-20x over Pyomo) and the most
  mature, with strong unit-commitment libraries. The cost is a full rewrite in
  Julia and leaving the Python ecosystem. Worth it only if we commit to Julia.
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
which is what is genuinely hard to vectorise). Four builders, all solving to the
same objective (2.105263) on the small forced-charging case. Build time on the
**Comillas desktop** (best of two; B cycles x C=24 steps x G units):

| size (B x C x G) | rows | pyomo-rule | LinearExpression | linopy | pyoframe |
|------------------|------|------------|------------------|--------|----------|
| 365 x 24 x 10    | 3 650 | 0.969 s   | 0.821 s (1.2x)   | 0.085 s (11x) | 0.269 s (3.6x) |
| 365 x 24 x 50    | 18 250 | 4.483 s  | 3.813 s (1.2x)   | 0.123 s (37x) | 1.471 s (3.0x) |

Findings on the harder family:

- **linopy still wins big but less than the easy case** - 11-37x here vs 23-60x on
  the one-step family. The windowed sum and the block lag add overhead, as
  expected, but a vectorised builder is still the clear lever.
- **pyoframe is viable but well behind linopy here** - 3-3.6x. Its Polars-based
  block lag (shift the index, then realign) is less ergonomic than linopy's
  `xarray` `.shift`, and the build is slower on this time-coupled structure.
- **`LinearExpression` is a steady ~1.2x** - confirms it is not the lever.
- **Marginal prices work in both** - the shadow price on the inventory balance
  comes back identically from linopy (`constraint.dual`) and pyoframe
  (`constraint.dual`), -1.052632 in the probe. That settles the dual question for
  LP cases; the unit-commitment (MILP) marginal prices would still need a
  fix-and-resolve step in either tool.

Overall direction (unchanged and now well supported): the build-time lever is a
vectorised builder, and **linopy is the front-runner** - largest measured win,
same language, HiGHS/Gurobi, and working LP duals. pyoframe (the "polar-high"
candidate) is a real option but, on this model's time-coupled structure, slower to
build and more awkward than linopy. The remaining design item before a full
migration is MILP dual extraction for marginal prices.
