# Problem classes: what each modelling tool can express

Before choosing a build-time-faster modelling tool (see
`computational_efficiency.md`), the first question is *coverage*: can the tool even
express the problem classes el1xr_opt needs? Build speed is irrelevant if a tool
cannot state the model.

This matters for power systems specifically because the AC power flow brings in
non-linear classes:

- **QP / MIQP** — quadratic generator cost curves, some battery-degradation terms.
- **SOCP / MISOCP** — second-order-cone (branch-flow / DistFlow) relaxations of AC
  OPF, convex relaxations of power flow, some chance constraints. MISOCP when
  discrete decisions (switching, capacitor banks, topology) are added.
- **SDP** — the semidefinite (Lavaei–Low) relaxation of AC OPF, and some robust /
  polynomial-optimisation reformulations.

## Capability matrix

Verified empirically for linopy and pyoframe on 2026-06-07 (the installed
versions, solved tiny instances with a known optimum); the others are from their
documentation and standard use.

| Class                         | linopy 0.7 | pyoframe 1.4 | Pyomo (current) | JuMP | CVXPY |
|-------------------------------|:----------:|:------------:|:---------------:|:----:|:-----:|
| LP                            | yes        | yes          | yes             | yes  | yes   |
| MILP (integer / binary)       | yes        | yes          | yes             | yes  | yes¹  |
| QP (quadratic **objective**)  | yes        | yes          | yes             | yes  | yes   |
| MIQP                          | yes        | yes          | yes             | yes  | yes¹  |
| QCQP / **SOCP** (quad constr) | **no**     | yes          | yes²            | yes  | yes   |
| **MISOCP**                    | **no**     | yes          | yes²            | yes  | yes¹  |
| **SDP** (PSD matrix vars)     | **no**     | **no**       | no (native)³    | yes  | yes   |

¹ CVXPY handles mixed-integer *convex* problems (it is convex-only / DCP — no
  non-convex MINLP), via mixed-integer conic solvers.
² Pyomo expresses SOCP/MISOCP either as quadratic constraints solved by Gurobi, or
  through its `pyomo.kernel.conic` cone constraints (Mosek / Gurobi).
³ Pyomo has no native PSD-matrix variable; SDP is not practical in it.

Key evidence (what was actually run):

- **linopy**: MILP, QP, MIQP all solve; a quadratic *constraint* raises
  `NotImplementedError: Quadratic expressions cannot be used in constraints`. No
  cone or PSD API. So linopy is **LP / MILP / QP / MIQP only**.
- **pyoframe**: quadratic constraint `x²+y²≤1` maximising `x+y` solved to
  `x=y=0.707` (the true cone solution), and an MISOCP (integer + quad constraint)
  solved — both via Gurobi. No PSD API, so **no SDP**.

Two solver notes: SOCP/MISOCP need a conic-capable solver (Gurobi, Mosek, COPT);
**HiGHS does LP/MILP/QP only**, so the conic classes fall back to Gurobi on the
box. SDP needs Mosek / SCS / COSMO / Clarabel.

## What this means for the migration

The fast builder (linopy, 11–49× on build) is also the **narrowest**: it cannot do
cones or SDP. So the choice depends on el1xr_opt's roadmap:

- **If the model stays LP / MILP / QP / MIQP** (typical expansion + unit commitment
  + market layers — which is what el1xr_opt is today): **linopy is the best fit** —
  the big build-time win with no coverage loss.
- **If SOCP / MISOCP are needed** (AC OPF cone relaxations): linopy is out.
  Options that keep most of the build win: **pyoframe** (covers up to MISOCP, ~3×
  build, but it collapsed at 1M rows), **staying on Pyomo** (already covers this),
  or **JuMP** (covers it, ~3–5× build, full Julia rewrite).
- **If SDP is needed** (AC OPF SDP relaxation): only **JuMP** or **CVXPY** (or
  Mosek directly). None of linopy / pyoframe / current-Pyomo do SDP natively.

A **hybrid** is realistic and worth keeping in mind: use linopy for the large
LP/MILP/QP operational and expansion model (where build time dominates and the
classes are linear), and a dedicated conic tool (CVXPY or JuMP, or Mosek) for the
smaller SOCP/SDP sub-problems such as an AC OPF relaxation on one network snapshot
— those instances are small, so their build time does not matter and linopy's
speed is not missed.

Bottom line: linopy wins on build speed but only covers the linear/quadratic-
objective classes. Decide the migration on **which classes el1xr_opt will actually
use**, not on build speed alone.

## How to benchmark the quadratic / conic / SDP classes

The existing benchmarks cover LP/MILP build speed. To extend them to the harder
classes, the benchmark has two stages, because not every tool can express every
class:

1. **Capability stage (pass/fail).** For each (tool, class), build one small
   canonical instance with a known optimum and try to solve it. Record
   express-and-solve / not-supported. This is the matrix above; re-run it per tool
   version because support changes (e.g. linopy may add quadratic constraints
   later).

2. **Build-time + correctness stage**, only among the tools that pass stage 1 for
   that class. Same protocol as the linear benchmarks: scale the instance up, time
   the model **build** only (warm up JuMP first), and check the objective matches
   across tools. Use one common solver per class so the comparison is fair:
   - LP / MILP / QP / MIQP → Gurobi (or HiGHS for the non-quadratic ones).
   - SOCP / MISOCP → Gurobi (Mosek / COPT also work).
   - SDP → Mosek (or SCS / Clarabel for an open-source option).

**JuMP is included in every class.** It is the only tool that spans LP through
SDP, so it is the natural cross-class reference: each per-class comparison is run
against JuMP, and for the classes the Python tools cannot express (SDP, and SOCP
for linopy) JuMP is the yardstick for what "supported and fast" looks like. For
SDP the field narrows to **JuMP vs CVXPY**; for SOCP/MISOCP it is **JuMP vs
pyoframe vs Pyomo (vs CVXPY)**.

Representative, power-systems-flavoured instances per class (so the benchmark
reflects el1xr_opt, not generic shapes), with the tools each one is benchmarked
across:

| Class   | Representative instance                                              | Tools benchmarked |
|---------|---------------------------------------------------------------------|-------------------|
| LP      | DC optimal power flow / economic dispatch over T periods            | pyomo, linopy, pyoframe, **JuMP** |
| MILP    | unit commitment (on/off, start-up) — the storage family already used| pyomo, linopy, pyoframe, **JuMP** |
| QP/MIQP | dispatch (+ commitment) with **quadratic generator cost curves**    | pyomo, linopy, pyoframe, **JuMP** |
| SOCP    | branch-flow (DistFlow) SOC relaxation of radial AC OPF              | pyoframe, pyomo, **JuMP**, cvxpy (linopy can't) |
| MISOCP  | the SOCP above plus discrete decisions (capacitor banks, switching) | pyoframe, pyomo, **JuMP**, cvxpy (linopy can't) |
| SDP     | Lavaei–Low SDP relaxation of AC OPF on a small network (W ⪰ 0)      | **JuMP**, cvxpy (only these two) |

What to report per class: the capability row, then build time vs instance size for
the capable tools (with the same ratios-vs-baseline presentation as the linear
study, JuMP always among them), plus the matching objective as the correctness
check. For SOCP/SDP the instances are usually solved on a single network snapshot,
so build time matters less there than for the year-long LP/MILP — which is itself
part of the conclusion: the build-time race is decided on the large linear model
(where linopy wins), while the conic/SDP needs are about *coverage* (where JuMP is
the only complete option).

## Measured: SOCP (DistFlow AC-OPF relaxation)

Built (`benchmarks/build_speed_socp.py` and `.jl`) and run on the remote desktop
desktop. The model is the rotated-cone DistFlow relaxation above on a radial
feeder of N buses (4N variables, 4N constraints incl. N second-order cones).
linopy is absent — it cannot express the cone. All four tools solve the small
instance to the same loss objective (0.0010446, Gurobi vs Clarabel agree to ~1e-7).

Build time (best of two; cvxpy timed *with* canonicalisation via
`get_problem_data`, since it builds lazily otherwise):

| N buses | constraints | pyomo  | pyoframe   | cvxpy        | JuMP         |
|---------|-------------|--------|------------|--------------|--------------|
| 1 000   | 4 000       | 0.066 s| 0.112 s (0.6x) | 0.014 s (4.6x) | 0.006 s (11x) |
| 10 000  | 40 000      | 0.975 s| 0.263 s (3.7x) | 0.091 s (10.8x) | 0.078 s (12.5x) |

Findings, and how they differ from the linear study:

- **For SOCP, JuMP and CVXPY are the fastest builders** (~11–12x over Pyomo at 10k
  buses), with pyoframe ~3.7x and Pyomo slowest. This is the opposite of the
  linear case, where linopy's vectorised build dominated — and linopy is simply
  not eligible here.
- **JuMP looks much better on SOCP than it did on the linear family** (where it was
  ~3–5x). Its native `RotatedSecondOrderCone` plus compiled construction build the
  cones efficiently; the per-element penalty that hurt it on the dense linear
  family is smaller here (4N constraints, not a windowed sum).
- **CVXPY is the strong Python option for conic** — purpose-built, vectorised
  canonicalisation; nearly as fast to build as JuMP and trivially expresses the
  cone. (Caveat: it is convex-only, so it does not replace Pyomo/linopy for the
  large non-convex MILP unit-commitment model.)
- **pyoframe handles SOCP** (rotated cone via Gurobi) at a steady ~3–4x, but the
  index-shift gymnastics for the feeder coupling make it the least ergonomic here.

Takeaway: the best builder is **class-dependent**. For the large linear (LP/MILP)
operational and expansion model, linopy wins decisively. For conic AC-OPF
relaxations, linopy is out and **JuMP or CVXPY** are both fast and natural. This is
the concrete evidence behind the hybrid recommendation: linopy for the big linear
model, a conic tool (CVXPY, or JuMP if also adopting it elsewhere) for the
SOCP/SDP sub-problems.

## Measured: SDP (semidefinite relaxation, AC-OPF style)

Built (`benchmarks/build_speed_sdp.py` and `.jl`) and run on the remote desktop. Only JuMP
and CVXPY can express it — Pyomo, pyoframe and linopy have no PSD-matrix variable,
so they are not in the table at all. The instance is a PSD matrix W ⪰ 0 with fixed
diagonal minimising trace(C W), C the ring (cycle) adjacency — the max-cut /
AC-OPF-relaxation SDP core, scalable by matrix dimension n (≈ 2·buses). Both solve
the small instance to the same optimum (−19.99999996, via Clarabel in each).

Build time (best of two; cvxpy timed with canonicalisation):

| n (matrix dim) | variables | CVXPY  | JuMP          |
|----------------|-----------|--------|---------------|
| 100            | 5 050     | 0.009 s| 0.003 s (3x)  |
| 200            | 20 100    | 0.037 s| 0.011 s (3.4x)|

Findings:

- **Both express SDP cleanly and build it fast** (hundredths of a second);
  **JuMP is ~3x faster to build than CVXPY** here, and both are correct.
- For SDP the build time is not the bottleneck anyway — the *solve* is O(n^6)-ish,
  so a 100–200-dimension matrix (a 50–100-bus AC OPF) is already heavy to solve
  while trivial to build. The real question for SDP is **coverage**, and only
  these two tools have it.
- This confirms the coverage picture end to end: **JuMP is the one tool that spans
  every class** (LP → SDP) and is fast at the conic ones; **CVXPY** is the strong
  Python option for the convex conic/SDP classes but cannot do the non-convex UC
  MILP; **linopy** is fastest for the big linear model but stops at MIQP.

### Conclusion across all classes

| | LP/MILP build | QP/MIQP | SOCP/MISOCP | SDP |
|---|---|---|---|---|
| linopy   | **fastest (11–49x)** | yes | — | — |
| pyoframe | ~3x            | yes | yes (~3.7x)  | — |
| Pyomo    | baseline       | yes | yes          | — |
| JuMP     | ~3–5x          | yes | **fast (~12x)** | **yes (fast)** |
| CVXPY    | (convex only)  | yes | fast (~11x)  | **yes** |

The decision follows the **classes el1xr_opt will use**: stay/grow linear+UC →
linopy (biggest build win); add AC-OPF cone relaxations → JuMP or CVXPY (or
pyoframe/Pyomo); add SDP → JuMP or CVXPY only. A **hybrid** (linopy for the large
linear model + JuMP/CVXPY for conic sub-problems) gets the build-speed win where it
matters and full coverage where it is needed.
