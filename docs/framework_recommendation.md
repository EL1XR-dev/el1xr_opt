# Framework assessment: build speed vs the el1xr_opt roadmap

This synthesises the build-speed benchmarks (`computational_efficiency.md`) and the
problem-class study (`modeling_framework_problem_classes.md`) into a
recommendation, taking into account where the model is likely to go: **unbalanced
three-phase AC OPF, energy communities, virtual energy sharing, and similar**.

## 1. What the benchmarks established

- **Build time is the bottleneck** for the large linear model (building ≈ 2× the
  solve for a full-year LP), and Pyomo's per-element constraint loops are the slow
  part.
- For the **linear core (LP / MILP / QP)**, **linopy is much faster to build**.
  Construct-only it is 11–49× over Pyomo; **end-to-end (construct + export to the
  solver) it is ~5–20×** — still decisive (the construct-only figure excluded the
  solver-export step, where Pyomo is slowest). The linopy model was verified
  complete and correct. pyoframe ~3×, JuMP ~3–5×, Pyomo the baseline.
- For **SOCP**, linopy is out (no cones); **JuMP (~12×) and CVXPY (~11×)** build
  fastest, pyoframe ~3.7×.
- For **SDP**, only **JuMP and CVXPY** can express it at all (JuMP ~3× faster to
  build); the others have no PSD variable.

So on raw build speed, linopy is the clear winner — **but only for the linear
classes it can express.**

## 2. What the roadmap adds (and which classes it needs)

| Planned extension | Optimisation class it brings | Who can do it |
|-------------------|------------------------------|---------------|
| Energy community, virtual sharing, P2P allocation | LP / MILP (sometimes bilevel → MILP via KKT, or complementarity) | all (linopy fastest); complementarity needs Pyomo or JuMP |
| Three-phase **unbalanced AC OPF**, **exact** | **NLP (non-convex)** | **only Pyomo (Ipopt) or JuMP (Ipopt)** |
| Three-phase unbalanced AC OPF, **convex relaxation** | **SOCP / SDP** (3-phase branch-flow SOC, chordal SDP) | JuMP, CVXPY, Pyomo (SOCP), pyoframe (SOCP) |
| Robust / chance-constrained variants | often SOCP | JuMP, CVXPY, Pyomo, pyoframe |

The decisive item is **three-phase AC OPF**. Whether exact or relaxed, it needs a
class that **linopy and pyoframe cannot do** (NLP/SDP), and the *exact* form is
**NLP, which only Pyomo and JuMP support** (CVXPY is convex-only; linopy/pyoframe
are linear/quadratic). The community / sharing pieces are linear and fit any tool.

This is the key conclusion: **the build-speed winner (linopy) cannot be the
backbone of this roadmap.** It can only ever be the fast builder for the *linear
sub-model*, never the tool that does the AC OPF.

## 3. Coverage across the whole roadmap

| | LP/MILP (community, sharing, UC, expansion) | QP/MIQP | SOCP (3φ relax) | SDP (3φ relax) | NLP (exact 3φ AC OPF) |
|---|:--:|:--:|:--:|:--:|:--:|
| linopy   | ✅ fastest | ✅ | ❌ | ❌ | ❌ |
| pyoframe | ✅ ~3×     | ✅ | ✅ | ❌ | ❌ |
| Pyomo    | ✅ baseline| ✅ | ✅ | ❌ | ✅ (Ipopt) |
| JuMP     | ✅ ~3–5×   | ✅ | ✅ | ✅ | ✅ (Ipopt) |
| CVXPY    | convex only| ✅ | ✅ | ✅ | ❌ |

Only **Pyomo** and **JuMP** span the *whole* roadmap including exact AC OPF. And
for **unbalanced three-phase OPF specifically, the domain-standard tooling is
JuMP-based**: `PowerModelsDistribution.jl` implements exactly this (multi-conductor
unbalanced OPF with NLP/SOCP/SDP formulations), with `PowerModels.jl` for the
transmission side.

## 4. The realistic end-states

- **A — Adopt JuMP as the single framework.** The only one tool that covers the
  entire roadmap (LP → SDP → NLP), with the best build speed at the conic classes
  and a mature unbalanced-OPF ecosystem (PowerModelsDistribution.jl). Build speed
  on the linear core is ~3–5× (good, not linopy's 11–49×, but adequate). Cost: a
  full rewrite in Julia and committing the project/team to Julia. Best long-term
  fit **if the three-phase AC OPF roadmap is firm and Julia is acceptable.**
- **B — Stay on Pyomo as the backbone, tune it.** Pyomo already covers the whole
  roadmap except SDP (and SOCP relaxations usually suffice for distribution
  networks; SDP is more a transmission-research need). No rewrite. The cost is
  build speed, which is addressable without leaving Pyomo: representative periods
  (fewer load levels), the `LinearExpression` path (~1.4×), and temporal
  decomposition. Best **if staying in Python with one mature tool is a hard
  preference** and exact AC OPF (NLP) is needed.
- **C — Hybrid: linopy for the linear sub-model + Pyomo/JuMP/CVXPY for AC OPF.**
  Use linopy where its build win is real and large (the year-long LP/MILP/QP
  expansion + UC + community + sharing model) and a second tool for the AC OPF
  sub-problems (Pyomo+Ipopt or JuMP for exact; CVXPY/JuMP for SOCP/SDP). Captures
  the build-speed win where it matters and full coverage where it is needed. Cost:
  two modelling layers and the glue/data-passing between them.

## 5. Recommendation

Weigh it on two questions the benchmarks cannot answer:

1. **Is three-phase (unbalanced) AC OPF firmly on the roadmap?** If yes, **linopy
   cannot be the backbone** — drop the idea of migrating the whole model to it.
2. **Is adopting Julia acceptable for the project?** If yes, **JuMP (option A) is
   the strongest long-term fit** — one framework for everything on the roadmap,
   the standard unbalanced-OPF libraries, and competitive build speed. If Julia is
   not acceptable, **keep Pyomo as the backbone (option B)** and treat its build
   time tactically; bring in **linopy only as a hybrid accelerator (option C)** for
   a specific large linear sub-model **if and when build time is a measured
   bottleneck there** — not as a wholesale migration.

In short: the benchmarks make linopy look like the obvious migration target, but
that is only true for a model that stays linear. Given an AC-OPF-heavy roadmap, the
real choice is **JuMP (if going Julia) or Pyomo-as-backbone (if staying Python)**,
with linopy demoted from "backbone" to "optional fast builder for the linear
sub-model."

## 6. Measured: NLP (exact AC OPF), Pyomo vs JuMP — the backbone head-to-head

Built (`build_speed_acopf_nlp.py` / `.jl`) — polar-form AC OPF on a feeder, the two
tools that can express general non-convex NLP. Both solve the small case to the
same optimum (0.82162…, Pyomo with idaes-Ipopt vs JuMP with Ipopt.jl, agree to
~1e-9), so both models are correct. Build time on the remote desktop:

| N buses | constraints | Pyomo  | JuMP          |
|---------|-------------|--------|---------------|
| 1 000   | 2 002       | 0.143 s| 0.067 s (2.1x)|
| 10 000  | 20 002      | 1.626 s| 0.801 s (2.0x)|

Findings:

- **JuMP builds the NLP ~2× faster than Pyomo** (construct-only). Both express the
  trigonometric power-flow equations cleanly; JuMP's compiled nonlinear macro
  edges Pyomo's Python-rule `cos`/`sin` construction.
- This is the smallest gap of any class — for *exact* AC OPF the two are in the
  same ballpark on build time. (End-to-end the gap likely widens: Pyomo writes a
  `.nl` file for Ipopt, a known bottleneck, while JuMP loads Ipopt in memory — the
  same construct-vs-export effect documented in `computational_efficiency.md`.)
- **Both are correct and viable** for exact AC OPF; the choice between them rests on
  the rest of the picture (coverage, ecosystem, language), not NLP build speed.

This closes the backbone question: **for exact AC OPF, Pyomo and JuMP both work**;
JuMP is modestly faster to build and, combined with its SDP coverage and the
`PowerModelsDistribution.jl` unbalanced-OPF ecosystem, is the stronger backbone *if
adopting Julia* — while **Pyomo remains the only Python option that can do exact
NLP AC OPF**, so it stays the natural backbone if the project stays in Python.
