# Architecture audit and refactor recommendation

Audit of the el1xr_opt build/solve architecture and a staged plan to make every
feature — unit commitment, investment, green hydrogen, energy community, AC OPF,
decomposition, and a future unbalanced *linear* OPF — **activatable/deactivatable
per case**, with clean seams for **parallelisation** and **decomposition**.

Scope note: this recommends a *targeted* refactor, not a rewrite. The current
design is a normal research-model layout (openTEPES is similar) and mostly works;
the goal is to cut the per-feature "blast radius" and add a couple of clean seams,
without building a speculative plugin framework.

## 1. Current state (audited)

How a feature is turned on/off today, with the evidence:

- **Option flags** are read generically from the Option CSV into `model.Par`
  (`pOpt{col}`) in `oM_InputData.py:106`. ~11 flags exist (`IndBinGenOperat`,
  `IndBinSingleNode`, `IndBinGenRamps`, ...). Defaults are *ad hoc*: only
  `IndBinCommunity` has a `setdefault(..., 0)` (`oM_InputData.py:110`); green-H2
  uses a try/except `_option()` helper; the rest assume the column exists (a
  missing one KeyErrors on old cases).
- **Gating is inconsistent**: variable-domain switch (`pOptIndBinGenOperat`:
  UnitInterval vs Binary, `oM_InputData.py:1037`), in-rule conditional terms
  (`pOptIndBinGenRamps` across `oM_ModelFormulation.py:1169+`), set/bound gating
  (`pOptIndBinSingleNode`), data-presence (investment runs iff candidate units
  exist, `oM_Investment.py:49`), and a global Parameter flag (green-H2 matching).
- **Orchestration** is a hand-ordered call list in `oM_Sequence.py:40-70`; some
  calls unconditional, some early-return on a flag (community, green-H2).
- **The objective is monolithic**: `eTotalCComponent` / `eTotalRComponent`
  (`oM_ModelFormulation.py:38-47`) hard-code the cost/revenue terms, so a new
  cost means editing these rules.
- **Shared constraints are edited in place**: the community layer injects a term
  into `eEleRetNodeBalance` behind a `community_on` guard
  (`oM_ModelFormulation.py:284,289`).
- **Good seams already exist**: AC OPF (`oM_ACOPF.py`) is fully decoupled (its own
  model, not in `routine`); investment and green-H2 are purely additive; the
  decomposition scaffold (`oM_Decomposition.py`) correctly identifies
  `(period, scenario)` blocks with investment as the first stage and storage as
  the time-linking variable; build is cleanly separated from solve
  (`oM_ProblemSolving.solving_model` gets a finished model); and there is no
  global mutable state beyond the read-only `model.Par`.

**Feature blast radius today** (files touched to add one feature): community = 4
(InputData flag, Sequence ×2 calls, ModelFormulation balance edit, + the new
module); investment / green-H2 = additive module + Sequence call + input params.

## 2. Assessment — what's fine, what hurts

**Fine (leave it):**
- The decoupled-analysis pattern (AC OPF) — keep using it for 3-phase OPF.
- Build/solve separation and the additive-module pattern (investment, green-H2).
- The generic Option-CSV → `pOpt*` reading.

**Hurts (worth fixing):**
1. **No central feature catalogue / default for flags** → old cases KeyError, and
   each feature invents its own on/off + default convention.
2. **Monolithic objective aggregation** → every cost-bearing feature edits the
   same two rules; this is the main coupling and merge-conflict magnet.
3. **In-place edits to shared balances** → the community term in the retail
   balance; a third such feature would make the rule unwieldy.
4. **No build-per-block seam** → blocks the parallel build and Benders, even
   though the structure is separable.

These are the four things to address; everything else is acceptable.

## 3. Recommendation — a staged, low-risk refactor

Each stage is independent, additive, behind the existing validation harness (the
four golden cases must keep their exact costs), and small enough to be its own PR.

### Stage A — feature catalogue + uniform flags (small, high value)
A single `oM_Features.py` declaring, per feature: the flag name, default, the
module entry points (variables / constraints fns), and the order. Then:
- `oM_InputData` applies **all** defaults from the catalogue (no more scattered
  `setdefault`; old cases never KeyError).
- `oM_Sequence` iterates the catalogue instead of a hand-ordered call list.
- One consistent rule: an optional feature checks its flag at the top of its
  `create_*` fns and returns early (the community pattern, applied uniformly).

This does **not** require touching the model maths — it's wiring. It makes adding
or toggling a feature a one-line catalogue entry plus the feature module.
DoD: golden costs unchanged; a feature can be toggled by its flag alone; an old
case with no new columns still runs.

### Stage B — cost/revenue registry (small, removes the worst coupling)
Replace the hard-coded sums in `eTotalCComponent` / `eTotalRComponent` with a
registry: features register their cost/revenue variable (e.g. `vTotalICost`,
`vTotalEleMrkPPACost`, a future community settlement term) into a list on the
model; the aggregation rule sums whatever is registered. Existing terms are moved
into the registry so behaviour is identical.
DoD: golden costs bit-identical; a new feature adds a cost by registering it, with
no edit to the aggregation rules.

### Stage C — network-representation mode (enables unbalanced linear OPF) — STARTED (2026-06-07)
First increment done: a `NETWORK_MODES` catalogue in `oM_Features` (single_node /
dc / distflow_socp / acopf_nlp / lindist3flow, each with its problem class and
in-core vs decoupled flag), and the **unbalanced linear OPF** itself —
`oM_LinDist3Flow.py`, an LP three-phase LinDistFlow analysis module (validated:
balanced+diagonal reduces to single-phase LinDistFlow exactly; unbalanced loading
gives the per-phase spread). Remaining for Stage C: consolidate the scattered
`IndBinSingleNode`/DC branches in the core into the mode dispatch, and validate the
LinDist3Flow mutual (off-diagonal) terms against OpenDSS/PMD.jl (the 5c follow-on).
Original design below.


Make the network model a selectable **mode** rather than scattered `IndBinSingleNode`
branches: `single-node | dc | distflow-socp | lindist3flow`. Each mode is a builder
that contributes the network constraints; the balance references the active mode's
flow variables. The existing single-node/DC logic becomes two of the modes; the
**unbalanced linear OPF (LinDist3Flow)** becomes a third builder added later — a
new constraint family gated by the mode, not a rewrite. (Exact/unbalanced AC OPF
stays in the decoupled `oM_ACOPF` path per the 5c scope; LinDist3Flow is the
*in-model linear* option for runs that need approximate unbalance without leaving
the LP/MILP solve.)
DoD: existing cases pick `dc`/`single-node` and are unchanged; a case can select a
network mode by one option; LinDist3Flow can be added as a builder without
touching the others.

### Stage D — block-build + solve-mode seam (enables parallelism & decomposition)
Refactor the build so it can build either the whole model (today) or one
`(period, scenario)` block, by having `data_processing` / `create_*` accept an
optional block filter from `partition_blocks`. Add a **solve mode**:
`monolithic | benders | parallel-blocks`. `monolithic` is today's path unchanged;
`benders` implements the master (investment + cuts) / subproblem loop the scaffold
already sketches, reusing the existing fix-and-resolve dual recovery
(`oM_ProblemSolving.py:172-192`); subproblems solve in parallel (no global state
blocks this). Temporal (within-block) splitting, which needs the storage
boundary-inventory linking (`oM_ModelFormulation.py:648-670`), is a later sub-step.
DoD: `monolithic` reproduces today exactly; `benders` matches the monolithic
optimum on a small case before being trusted; the block builder produces the same
constraints as the monolithic build for one block.

## 4. Mapping to the four asks

- **Easy activate/deactivate per case** → Stages A (+ B for cost-bearing features).
  Every feature gated uniformly by one flag with a safe default; toggling is a
  one-line case-data change; the catalogue is the single source of truth.
- **Unbalanced linear OPF** → Stage C: a `lindist3flow` network mode, activated
  like any other mode, sitting beside DC and single-node.
- **Parallelisation** → Stage D: the block-build seam + parallel subproblem solve;
  the audit confirms no global-state blocker, only the monolithic-build assumption.
- **Decomposition** → Stage D solve mode `benders`, building on the existing
  scaffold and dual-recovery; temporal Benders as a follow-on.

## 5. Sequencing, effort, and what NOT to do

Order by value/risk: **A → B → C → D**. A and B are small, pure-wiring, high
value, and unblock cleaner feature work immediately (do them first, and do C/D when
the corresponding feature — LinDist3Flow, or Benders — is actually being built, so
the seam is validated by a real user rather than speculative).

Effort: A ≈ 0.5–1 day; B ≈ 0.5–1 day; C ≈ scoped with the LinDist3Flow feature
(the mode dispatch is small, the LinDist3Flow builder is the real work); D ≈ scoped
with Benders (the seam is moderate, the Benders loop is the real work).

**Do NOT:**
- Build a generic plugin/hook framework with dynamic registries of injectors,
  dependency graphs, and runtime feature discovery. For a research model with a
  small team this is over-engineering; Stages A–B get 90% of the benefit at a
  fraction of the cost and risk.
- Re-namespace the flat ConcreteModel or introduce Pyomo Blocks for organisation
  alone — the earlier build-speed study showed the arc/Block style is not a
  performance win, and reorganising for its own sake risks the validated results.
- Pre-refactor for decomposition before implementing Benders — design the
  block-build seam *with* the Benders work so it is exercised, not speculative.

## 5b. Problem class drives solver AND build-library choice

Stage A makes the model's mathematical class (LP/MILP/QP/MIQP/SOCP/MISOCP/NLP) a
first-class, detected property (`oM_Features.detect_problem_class`). It is the lever
for two choices, not one:

- **Solver**: a SOCP/MISOCP case rules out HiGHS (needs Gurobi/Mosek); an NLP case
  needs Ipopt. `check_solver_for_model` warns on a mismatch before the solver does.
- **Model-building library** (for the hybrid/migration path): the same class says
  which builder can even express it — **linopy is LP/MILP/QP only**, pyoframe up to
  MISOCP, JuMP/CVXPY for SDP, Pyomo/JuMP for NLP. So `builders_for(class)` tells a
  future build step whether the fast linopy builder is usable for a given case or
  whether it must fall back to pyoframe/JuMP/Pyomo. This wires the framework study
  directly into the architecture.

Note an important sub-point: **unbalanced OPF is not necessarily nonlinear.** The
exact unbalanced AC OPF is NLP/SOCP (the decoupled PMD.jl path, Phase 5c), but the
**LinDist3Flow** model is a *linear* unbalanced approximation — class LP. So the
Stage-C `lindist3flow` network mode keeps the main model an LP/MILP, buildable even
by linopy and solvable by HiGHS, while the exact unbalanced analysis stays in the
specialist engine. The class detector reports this automatically.

## 5c. Nodal vs per-asset (arc) balance — a solve-time configuration

The current model uses a **nodal** balance. The arc / per-asset balance (one
balance per asset, flows as arcs) was assessed earlier for *build* time and found
not to help there. The reference paper's advantage is in **solve** time, not build
time, and it offers **several configurations** — which is a different lever and
worth revisiting under that lens:

- A per-asset, arc-based formulation makes the model **block-angular** (one block
  per asset, coupled through node balances and investment), which is exactly the
  structure that **decomposition** (Dantzig-Wolfe / column generation) and the
  Stage-D Benders work exploit, and which can tighten/restructure the problem for
  faster solving.
- It is therefore best treated as a **formulation configuration** (a `balance mode`
  option: `nodal | per-asset`) evaluated for **solve time and decomposability**,
  alongside Stage D — not adopted for build time (where the earlier benchmark
  showed no gain). The "several configurations" in the paper map to options in the
  same mode-dispatch pattern as the network modes (Stage C).

Action: scope the per-asset/arc balance as a Stage-D companion experiment — measure
**solve** time and Benders compatibility on a real case, with the configurations
the paper describes, before committing. Keep nodal as the default.

## 5d. CI must exercise the new architecture

As features become flag-activated and class-aware, CI should test the capabilities,
not just the golden costs. Already in place after Stages A/B (marker-driven, so the
existing `ci.yml` picks them up):

- fast tier: feature catalogue + defaults + capability matrices
  (`tests/test_features.py`).
- solve tier: problem-class detection on the validation cases
  (`tests/test_problem_class.py`), AC OPF on IEEE benchmarks (`tests/test_acopf.py`),
  energy community (`tests/test_community.py`).

As Stages C/D land, add: a case per network mode (single-node / dc / distflow /
lindist3flow) asserting the detected class and a representative solve; and a Benders
run asserting it matches the monolithic optimum. The `data/sizing` generate-on-the-fly
pattern is the place to add these small per-capability cases so CI stays fast.

## 6. Bottom line

The architecture is sound and already has the right seams (decoupled analysis,
additive modules, build/solve split, a correct decomposition scaffold). It does
**not** need a rewrite. Four targeted, independent, validation-gated changes —
a feature catalogue (A), a cost registry (B), a network-mode dispatch (C), and a
block-build/solve-mode seam (D) — make features cleanly activatable per case and
open the parallelisation/decomposition and unbalanced-linear-OPF paths, while
keeping the four golden cases bit-for-bit. Start with A and B (cheap, immediate);
fold C and D into the LinDist3Flow and Benders features when those are built.
