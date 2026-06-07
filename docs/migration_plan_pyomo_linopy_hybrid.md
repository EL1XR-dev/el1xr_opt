# Migration plan: Pyomo backbone + linopy accelerator (hybrid)

## Goal and principle

Keep **Pyomo as the backbone** — it already implements the whole el1xr_opt model
and is the only Python tool that covers the full roadmap (LP/MILP/QP, exact AC OPF
via NLP, SOCP). Add **linopy as an optional, opt-in accelerator for the large
*linear* operational/expansion model**, where the build-time win is real
(~5–20× end-to-end, measured) and full-year models are heavy. Use **Pyomo (Ipopt /
Gurobi) or CVXPY** for the conic/NLP AC-OPF sub-problems the roadmap will add.

The guiding rule: **one source of truth (Pyomo), linopy only where a measured
build-time bottleneck justifies a second, parity-checked builder for an isolated
linear sub-model.** This avoids turning the project into two full models to
maintain.

## What is already in place (built earlier this session)

The hybrid does not start from scratch — the shared layers exist:

- **Backend-agnostic input** — `oM_InputSource` (CSV / DuckDB sources, schema).
  Any model builder can read the same case; the source returns plain DataFrames.
- **Common output** — `oM_OutputData_duckdb` writes results to `results.duckdb`.
- **Decomposition scaffold** — `oM_Decomposition` (block partition, first-stage
  variables) for a later Benders path on the linear model.
- **MILP-dual pattern** — `oM_ProblemSolving` already fixes integers and re-solves
  to recover marginal prices; the linopy path will mirror this exactly.
- **Benchmarks** — `benchmarks/` (build-speed across tools and classes) and the
  golden-cost validation cases (Home1, Grid1, EEM26, H2VPP) as the parity harness.

## Target architecture

```
            oM_InputSource  (CSV / DuckDB)        ← shared, done
                    │
        ┌───────────┴───────────┐
        ▼                        ▼
  Pyomo data dict          linopy data (xarray)    ← new adapter (Phase 1)
        │                        │
  oM_ModelFormulation      oM_ModelFormulation_linopy   ← new builder (Phase 2),
  (+Investment,GreenH2)     (linear core only)             linear families only
        │                        │
        └───────────┬───────────┘
                    ▼   backend = pyomo | linopy   (Phase 4 switch)
            oM_ProblemSolving  (solve + fix-and-resolve duals)
                    │
            oM_OutputData_duckdb  (results.duckdb)  ← shared, done
                    │
        AC-OPF sub-problems (separate):  Pyomo+Ipopt (exact NLP)
                                         CVXPY / Pyomo (SOCP/SDP relax)   ← Phase 5
```

The backend switch lives in `oM_Sequence.routine`; the AC-OPF module is a separate
analysis step that consumes a network snapshot from the linear model's results.

## Decision gate (do this before building the linopy path)

The integrity re-check showed linopy is ~5–20× faster *end-to-end*, but Pyomo's
absolute full-year build may still be acceptable for current case sizes. So:

- **Gate 1 — measured need.** Profile the real full-year build of the actual
  el1xr_opt cases in Pyomo (not the synthetic benchmark). Only invest in the linopy
  builder if that build time is a genuine, repeated pain point (e.g. minutes per
  iteration during development, or blocking a study).
- **Gate 2 — maintenance budget.** Confirm the team can maintain a second builder
  for the linear core (or that the linopy path is isolated enough to be low-churn).

If both gates pass, proceed. If not, prefer the cheaper Pyomo-only levers first:
representative periods (fewer load levels — already supported via `pTimeStep`), the
`LinearExpression` path, and temporal decomposition (the `oM_Decomposition`
scaffold + openTEPES Benders template).

## Phases

Each phase has a definition-of-done (DoD) and a parity gate so it can be done
incrementally without a big-bang rewrite.

### Phase 0 — Profile and freeze the parity harness
- Measure full-year Pyomo build/solve time on the real cases; record the golden
  objectives (already have them at 168h — extend to full year).
- **DoD:** a one-page "is the build actually the bottleneck?" answer with numbers,
  and a frozen golden-cost set the linopy path must reproduce.

### Phase 1 — linopy data adapter
- Add `oM_InputData_linopy` (or extend the source): turn the source DataFrames into
  the xarray/pandas coords + DataArrays linopy needs (dims = periods, scenarios,
  load levels, units; values = the `pVar*`/`pEle*`/`pHyd*` params). No model logic.
- **DoD:** every parameter the linear core uses is available as a linopy-ready
  array; a round-trip test shows the arrays match the Pyomo `model.Par` values.

### Phase 2 — linopy builder for the linear core, family by family
- New `oM_ModelFormulation_linopy` building the **linear** families only: nodal
  balances (electricity + hydrogen), storage inventory (windowed — prototyped),
  capacity/investment coupling, retail buy/sell, operating-reserve (FCR) bids,
  network DC flow, green-H2 matching, peak/tariff. Unit-commitment binaries stay
  (linopy does MILP). Anything nonlinear is **out of scope** (there is none in the
  current linear core).
- Port one family at a time; after each, assert the assembled constraint set
  reproduces the Pyomo objective on the validation cases (LP relaxation first, then
  with binaries).
- **DoD:** the linopy model solves all four validation cases to the same objective
  as Pyomo (LP exact; MILP within the solver gap), from both CSV and DuckDB input.
- **Effort/risk:** this is the bulk of the work (~the linear families in a 160-
  constraint-statement formulation) and the main divergence risk. Mitigate by
  porting hottest-first, parity-gating each family, and keeping Pyomo authoritative.

### Phase 3 — linopy solve, duals, and results
- Solve via linopy (HiGHS / Gurobi). LP duals come back directly; for MILP marginal
  prices, mirror the existing fix-and-resolve (`oM_ProblemSolving`): fix the
  binaries, re-solve the LP, pull `constraint.dual`.
- Adapt `oM_OutputData_duckdb` to write linopy variables/duals into the same
  `results.duckdb` schema (so downstream analysis is backend-agnostic).
- **DoD:** linopy runs produce the same `results.duckdb` tables (values + duals/
  marginal prices) as Pyomo, within tolerance, on the validation cases.

### Phase 4 — backend switch + CI parity gate
- Add `--backend pyomo|linopy` to `routine` / the CLI (default stays `pyomo`).
- CI runs the validation cases on **both** backends and asserts matching objectives
  (the cross-backend parity test). Document when to pick which: linopy for large
  linear/MILP runs; Pyomo when a feature linopy lacks is needed.
- **DoD:** green two-backend CI; a documented switch; linopy is the recommended
  path for large linear studies.

### Phase 5 — AC-OPF sub-problem module (the coverage piece)
- New module (e.g. `oM_ACOPF`) that solves an AC OPF on a network snapshot taken
  from the linear model's results: **exact** (Pyomo + Ipopt, polar form —
  prototyped in `benchmarks/build_speed_acopf_nlp.py`) and/or **relaxation**
  (CVXPY or Pyomo SOCP — `benchmarks/build_speed_socp.py`). Decoupled from the big
  linear solve (run as analysis), so linopy's inability to do cones/NLP does not
  matter here.
- This is where the roadmap's three-phase work plugs in. **Note:** unbalanced
  three-phase AC OPF is a large modelling effort in any tool; this phase delivers
  the interface and a single-phase baseline, not the full multi-conductor model.
- **DoD:** a balanced single-phase AC OPF (exact and SOCP-relaxed) runs on a case
  network and writes results; a documented path to extend to three-phase.

### Phase 6 — energy community / virtual sharing
- These are **linear allocation layers** (sharing keys, virtual net metering, P2P)
  added on the backbone — new constraint families on the existing linear model
  (Pyomo and, if Phase 2 done, linopy). If a variant is bilevel/equilibrium, use
  Pyomo's complementarity (`pyomo.mpec`) or a KKT→MILP reformulation.
- **DoD:** an energy-community case solves and its sharing/allocation results are in
  `results.duckdb`; documented as new constraint families, not a new framework.

## Sequencing and honest trade-offs

- **Phases 5 and 6 do not depend on the linopy work.** If the AC-OPF / community
  roadmap is the priority, do Phase 5/6 on the Pyomo backbone first; the linopy
  accelerator (Phases 1–4) can come later, only if build time bites.
- **The hybrid's real cost is maintaining two builders of the linear core.** Keep
  it contained: Pyomo stays the source of truth; linopy is parity-gated in CI;
  consider limiting the linopy path to the single hottest sub-model (e.g. the
  full-year LP dispatch) rather than the entire formulation, so the duplication is
  bounded.
- **If the maintenance cost looks too high**, the fallback is Pyomo-only with
  representative periods + decomposition — no second builder, slower build accepted.
  Revisit linopy only when a specific study is build-bound.

## Bottom line

Pyomo carries the whole roadmap with no rewrite. linopy is a targeted accelerator
for the linear hot path, added behind a backend switch and a CI parity gate, only
once a measured build-time need and a maintenance budget justify it. The AC-OPF and
energy-community extensions sit on the Pyomo backbone (with CVXPY for SOCP/SDP) and
proceed independently of the linopy decision.
