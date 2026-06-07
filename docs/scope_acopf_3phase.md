# Scope: Phase 5c — three-phase unbalanced AC OPF (IEEE 13-bus)

Builds on the single-phase AC OPF of Phases 5a/5b (`oM_ACOPF`). This is the large
roadmap item, so this document scopes it and makes the engine decision before any
implementation. Anchored on the **IEEE 13-bus** unbalanced distribution feeder,
the standard small benchmark for unbalanced power flow.

## 1. Why single-phase is not enough

Phases 5a/5b model one balanced phase: one voltage and one flow per branch. Real
distribution networks — and the roadmap (unbalanced three-phase, energy
communities on LV feeders) — are **unbalanced**, which a single-phase model cannot
represent:

- **Per-phase voltages and currents** differ; the neutral carries return current.
- **Mutual coupling** between phases: a line is a 3×3 (or larger, with neutral)
  series-impedance matrix `Z_abc`, not a scalar. Off-diagonal terms couple phases.
- **Unbalanced loads**: single-, two- and three-phase loads, wye and delta
  connections, constant-PQ / constant-Z / constant-I behaviour.
- **Devices**: step-voltage regulators, in-line transformers, shunt capacitors,
  and laterals that carry only one or two phases.

The IEEE 13-bus feeder has all of these (a regulator, an in-line transformer, a
shunt capacitor, overhead and underground lines with full 3×3 configurations, spot
and distributed unbalanced loads, and single/two/three-phase segments). Its
published per-phase voltages (≈0.97–1.04 pu on the strong phases, dropping further
on lightly-supported ones) are the validation target.

## 2. The engine decision (the crux)

Three ways to get unbalanced AC OPF, with very different cost:

### Option A — use PowerModelsDistribution.jl as the engine (recommended)
PMD.jl (LANL-ANSI, Julia/JuMP) is the open-source domain standard for
multi-conductor unbalanced distribution OPF. It already provides:

- exact AC in polar (ACP) and rectangular (ACR) form;
- a second-order-cone relaxation of the branch-flow (BFM) and bus-injection (BIM)
  models, an SDP relaxation, and linear approximations including **LinDist3Flow**;
- a **built-in OpenDSS parser**, and its AC results are **validated against OpenDSS
  on the IEEE 13/34/123-bus feeders and the LV test case**.

So the IEEE 13-bus (distributed as OpenDSS) runs out of the box, already validated.
Cost: a Julia dependency for this one decoupled analysis module — consistent with
the framework decision (Pyomo backbone for the big linear model; a specialist tool
for the conic/NLP AC OPF, which Pyomo/linopy do not do well or at all). We already
run Julia/JuMP on the remote desktop for the benchmarks, so the toolchain exists.

Sources: PMD.jl docs (lanl-ansi.github.io/PowerModelsDistribution.jl) and the
SoftwareX/arXiv paper (arXiv:2004.10081).

### Option B — native Pyomo LinDist3Flow (linear, lower fidelity)
LinDist3Flow is a linearised three-phase branch-flow model: per-phase squared
voltages and flows with the 3×3 coupling kept to first order. It is linear, so it
needs no NLP/conic solver and could live natively in Pyomo (and even linopy),
giving fast unbalanced **screening** integrated in the model. It does not capture
the full nonlinearity (voltage magnitudes are approximate, no exact losses), and
implementing regulators/transformers/delta loads correctly is still real work.

### Option C — full Pyomo-native nonlinear three-phase (not recommended)
Re-implementing the exact unbalanced ACP/ACR plus all the device models in Pyomo
is a multi-month effort that reproduces what PMD.jl already does and validates.
Not worth it unless there is a hard requirement to stay in pure Python for the
exact model.

### Recommendation
**A for the exact/relaxed unbalanced AC OPF** (call PMD.jl as a decoupled engine,
validated on IEEE 13-bus), **optionally B later** as a native linear screening
inside the model if a Julia dependency in the workflow is undesirable for routine
runs. Avoid C.

## 3. Data and the format gap

el1xr's electricity-network CSV is single-phase (one Reactance/Resistance per
branch). Unbalanced AC OPF needs much more: per-line 3×3 impedance configurations,
phase connectivity per segment, load phasing and connection, regulator/transformer
/capacitor models. Rather than extend the el1xr CSV schema to a full
multi-conductor format (large, and a parallel to what OpenDSS already standardises),
**use OpenDSS feeder files as the three-phase network input** for Phase 5c:

- The IEEE feeders are published as OpenDSS; PMD.jl parses them directly.
- el1xr's role at the interface is to provide the **snapshot**: substation boundary
  conditions and any DER/community setpoints (from a solved operational model
  period) that map onto the feeder's buses. PMD.jl runs the unbalanced OPF/PF on
  the feeder and returns per-phase voltages, currents and losses.

This keeps el1xr as the planning/operational backbone and treats the unbalanced
feeder analysis as a specialist downstream check — the same decoupled pattern as
5a/5b, just with a three-phase engine.

## 4. Integration architecture

```
solved el1xr model (period snapshot: bus injections / DER setpoints)
        │   (per-feeder mapping)
        ▼
  oM_ACOPF3ph  ──►  PowerModelsDistribution.jl  ◄── OpenDSS feeder model (IEEE 13-bus)
        │                 (ACP/ACR exact, SOC/LinDist3Flow)
        ▼
  per-phase voltages / currents / losses  ──►  results.duckdb
```

How `oM_ACOPF3ph` calls PMD.jl (to decide during 5c-1):
- **File exchange + subprocess** (simplest, robust): write the snapshot to JSON,
  run a small Julia script (`julia acopf3ph.jl feeder.dss snapshot.json out.json`),
  read the result. No in-process Julia↔Python bridge to maintain.
- **PyJulia / juliacall** (tighter, more setup): call PMD.jl in-process. More
  fragile across environments; defer unless the subprocess overhead matters.

Subprocess + JSON is the recommended first integration (matches how we already run
Julia benchmarks on the remote desktop).

## 5. Validation target (IEEE 13-bus)

- Run PMD.jl ACP on the IEEE 13-bus OpenDSS model; compare per-phase node voltages
  to the OpenDSS reference solution (PMD.jl already matches it — we re-confirm the
  pipeline reproduces it from el1xr's side).
- Then run the OPF variant and the SOC/LinDist3Flow relaxations; report the
  relaxation gap and per-phase voltage spread, written to `results.duckdb`.
- Success = per-phase voltages match OpenDSS within tolerance and the unbalanced
  voltage spread between phases is captured (the thing single-phase 5a/5b cannot
  show).

## 6. Phasing

- **5c-1 — engine + pipeline (decision-proving).** Stand up the PMD.jl call path
  (subprocess + JSON), run ACP power flow on the IEEE 13-bus OpenDSS model, and
  reproduce the OpenDSS per-phase voltages. Deliverable: `oM_ACOPF3ph` skeleton +
  a Julia driver + an IEEE 13-bus validation test (skipped if Julia/PMD.jl absent,
  like the existing solver-gated AC OPF tests). This proves Option A end to end.
- **5c-2 — OPF + el1xr snapshot injection.** Feed substation/DER setpoints from a
  solved el1xr period into the feeder, run the unbalanced OPF (and a relaxation),
  write per-phase results to DuckDB.
- **5c-3 — (optional) native LinDist3Flow.** A linear unbalanced screening model in
  Pyomo for runs that should avoid the Julia dependency; validated against PMD.jl's
  LinDist3Flow on the IEEE 13-bus.

## 7. Effort, risk, dependencies

- **Effort:** 5c-1 is modest (wiring + a known-good engine). 5c-2 is the real
  integration work (snapshot mapping, OPF setup). 5c-3 is a separate linear-model
  build.
- **Risk:** mostly integration/toolchain (Julia env, OpenDSS parsing edge cases),
  not modelling — PMD.jl carries the validated physics. A native build (B/C) would
  move risk back onto our own modelling.
- **Dependencies:** Julia + PMD.jl for Option A (already used for benchmarks on
  remote desktop); an Ipopt/SCS-class solver for exact/relaxed solves (PMD.jl uses the
  same JuMP solver stack we set up for the build benchmarks).

## 8. Recommendation summary

Adopt **PMD.jl as the unbalanced AC-OPF engine** (Option A), wired as a decoupled
downstream module reading OpenDSS feeders and returning per-phase results to
DuckDB, validated on the IEEE 13-bus against OpenDSS. Keep a **native
LinDist3Flow** (Option B) as an optional later screening model. Do not
re-implement the exact unbalanced model in Pyomo (Option C). Start with **5c-1**
to prove the pipeline on the IEEE 13-bus before the deeper 5c-2 integration.
