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

Suggested path: (1) spend half a day on the Pyomo `LinearExpression` / kernel
tuning to see how much the cheap fix gives; then (2) port **one** real constraint
family (e.g. the storage inventory balance) to **linopy** and to **pyoframe** and
measure the build time on a full-year case - the published speed-ups come from
clean synthetic problems and will be smaller on this sparse model, so measure our
own before committing. If the measured linopy build win is large and duals work
for our marginal prices, linopy is the recommended move; keep JuMP in mind only
if we decide to adopt Julia for other reasons. Full details and sources are in the
reference note `amls_build_speed_pyomo_alternatives` in the research memory.
