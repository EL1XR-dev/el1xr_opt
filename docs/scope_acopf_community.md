# Scope: AC OPF (Phase 5) and energy community / virtual sharing (Phase 6)

On the Pyomo backbone, independent of the linopy accelerator. Grounded in
el1xr_opt's existing data and constraints so each piece extends what is there
rather than bolting on a generic template.

## What already exists (the foundation)

- **Network data** (`oM_Data_ElectricityNetwork`): per branch `Type, Voltage,
  Length, LossFactor, Reactance, Resistance, TTC, TTCBck, SecurityFactor` plus
  investment columns. So **R and X are already in the data** — AC OPF and its SOCP
  relaxation need no new network parameters, only to *use* R (today only X is used).
- **Power flow today is DC**: `vEleNetTheta` + reactance (`oM_ModelFormulation`
  ~line 1597), `vEleNetFlow` bounded by `TTC`. Nodal balance `eEleBalance` already
  sums line flows, imports/exports, generation, storage and demand per node.
- **Spatial hierarchy**: `Node → Zone → Area → Region` dicts + `NodeToZone`,
  `ZoneToArea`, `AreaToRegion` — the natural boundaries for a community.
- **Retail/market layer** (`oM_Data_ElectricityRetail`): per retailer `Node, Buy,
  Sell, MaximumEnergyBuy/Sell, TariffType, BuyingRatio, SellingRatio, Incentive,
  PowerTariff, EnergyTax, ...` and the `vEleBuy`/`vEleSell` variables with the
  retail node-balance — the hooks a community/sharing layer plugs into.
- **Results**: `results.duckdb` writer; validation cases as the regression harness.

So both phases are **new constraint families and one new analysis module**, not new
infrastructure.

---

## Phase 5 — AC OPF

### Why and what
The model uses a transport / DC-flow representation. Distribution-level studies
(and the three-phase roadmap) need the real power flow: voltage magnitudes, losses,
reactive power. AC OPF is **non-convex (NLP)** exactly; the convex **SOCP branch-
flow (DistFlow) relaxation** is the practical workhorse for radial networks. Both
are Pyomo-expressible (NLP via Ipopt; SOCP via Gurobi or `pyomo.kernel.conic`).

### Design decision: coupled vs decoupled
AC OPF over the full year × scenarios × all storage/UC binaries would be an
enormous MINLP — not solvable. The realistic design (and what the migration plan
assumed) is **decoupled**:

1. Solve the existing linear/MILP operational+expansion model (DC or transport).
2. For selected snapshots (peak hour, critical periods, or each representative
   load level), run an **AC OPF / SOCP** on the network with injections fixed (or
   bounded) from step 1, to check voltages, losses and reactive feasibility.

This keeps each problem tractable, matches how AC feasibility is checked in
practice, and means linopy's inability to do cones/NLP never blocks the main solve.

### Module: `oM_ACOPF`
A standalone analysis module (mirrors the `benchmarks/build_speed_acopf_nlp.py` and
`build_speed_socp.py` prototypes, promoted to use real case data):

- **Input**: a network snapshot — buses, branches (R, X, TTC, Voltage from the
  existing network data), and nodal net injections from a chosen result period.
- **Formulations** (an option flag, like the existing `pOptIndBin*`):
  - `acopf_socp` — branch-flow SOC relaxation (rotated cone P²+Q² ≤ l·v), the
    default for radial feeders; convex, Gurobi.
  - `acopf_nlp` — exact polar-form AC OPF, Ipopt; for accuracy / non-radial.
- **Output**: per-bus voltage magnitude/angle, per-branch flows and losses,
  reactive dispatch, and the SOCP relaxation gap (how far P²+Q² is from l·v —
  the standard exactness check) → written to `results.duckdb`.

### Phasing within Phase 5
- **5a — single-phase balanced baseline. DONE (2026-06-07).** Implemented in
  ``oM_ACOPF.py``: reads the el1xr electricity-network format (R, X, TTC per branch),
  builds the SOC (DistFlow) relaxation (Gurobi, with the relaxation-gap check) and
  the exact polar NLP (Ipopt, warm-started from the SOC voltages — a flat start
  fails on a stressed feeder), and writes per-bus voltages + a summary to DuckDB.
  Validated against the **IEEE 33-bus** feeder (Baran & Wu): both formulations
  reproduce the published base-case loss (202.68 vs ~202.7 kW) and minimum voltage
  (0.9131 vs ~0.913 pu) and agree to 0.001 kW; SOC relaxation gap ~7e-5 (exact
  here). Tests in ``tests/test_acopf.py`` (data in ``tests/_ieee33.py``), skip-
  guarded on solver availability (SOC needs Gurobi, NLP needs Ipopt). Note: a
  cross-bug found and fixed during this — the polar injection must use the Ybus
  off-diagonal (negated series admittance), not the series value.
- **5b — multi-snapshot. DONE (2026-06-07).** ``run_acopf_sweep`` runs one AC OPF
  per snapshot (with permissive voltage bounds so the actual power-flow voltages
  are found) and summarises min/max voltage, losses and violations vs the nominal
  limits; ``scaled_snapshots`` builds a load-profile set and ``snapshots_from_case``
  is the interface to pull per-node net demand per load level from a real case. The
  summary writes to DuckDB (``oM_Result_ACOPF_Sweep``). Validated on the IEEE
  33-bus feeder over a 0.5x-1.3x load profile: losses rise (47 -> 360 kW) and
  minimum voltage falls monotonically (0.958 -> 0.884) with load, violations grow,
  and the base snapshot reproduces the 5a benchmark (202.68 kW, 0.9131 pu). Test in
  ``tests/test_acopf.py::test_ieee33_sweep``. Optional feedback (tighten the linear
  model's line limits where AC OPF finds violations) remains for a later step.
- **5c — three-phase unbalanced (the roadmap item).** The big one. Replace the
  single-phase branch model with a multi-conductor (3-phase) one: per-phase
  voltages and currents, mutual coupling, unbalanced loads. This is a large
  modelling effort in any tool; the reference implementation is
  `PowerModelsDistribution.jl` (Julia/JuMP). **Decision point:** implement 3-phase
  in Pyomo (self-contained, more work) or call PowerModelsDistribution.jl as an
  external AC-OPF engine (less modelling, adds a Julia dependency for this module
  only — consistent with "Pyomo backbone, specialist tool for the conic/NLP
  sub-problem"). Scope 5c as its own mini-project after 5a/5b prove the interface.
  **Scoped in detail (2026-06-07) in `docs/scope_acopf_3phase.md`**, anchored on
  the IEEE 13-bus feeder: recommendation is to adopt PowerModelsDistribution.jl as
  a decoupled engine (OpenDSS feeders, validated against OpenDSS on IEEE 13/34/123),
  with an optional native LinDist3Flow screening model later, and to start with a
  pipeline-proving step (5c-1) that reproduces the IEEE 13-bus per-phase voltages.

### DoD for Phase 5
5a: SOCP and NLP AC OPF run on a real case snapshot, agree within the relaxation
gap, and write voltages/losses/gap to `results.duckdb`. 5b: a year-snapshot sweep
report. 5c: a documented decision (Pyomo vs PMD.jl) + a single feeder three-phase
proof of concept.

### Data additions (small)
- `oM_Data_ACOPF` (option flags: formulation, which periods, voltage bounds).
- Per-bus voltage limits (`Vmin/Vmax`) and per-generator reactive limits
  (`Qmin/Qmax`) — add columns to the existing node/generation dicts (default to
  wide bounds so existing cases are unaffected).

---

## Phase 6 — Energy community / virtual sharing

### Why and what
An energy community lets members (buses/retailers in a Zone or Area) **share**
locally generated energy before importing from the grid, under a sharing rule, and
settle internal exchanges at community prices rather than full retail tariffs.
"Virtual" sharing = the allocation is financial/metering, not a separate physical
network (the existing grid carries the power). This is a **linear** layer — it adds
allocation variables and balance/settlement constraints on top of the current
retail model. No new solver class.

### Design: a community as a Zone/Area aggregate
Reuse the existing hierarchy: a **community = a Zone** (or Area), its members = the
retailers/demands/generators mapped to that zone (`z2ed`, `z2eg`, `z2er` already
exist). Then:

- **Shared-energy variables** per community and time: `vEleShared[p,sc,n,zn]` (and
  per-member split `vEleSharedTo[...]`), bounded by local surplus generation.
- **Community balance**: within a zone, members' surplus generation is allocated to
  members' deficits first; only the net residual hits `vEleBuy`/`vEleSell` at the
  retail boundary. This slots into the existing nodal/retail balance, not replacing
  it.
- **Sharing rule** (an option): pro-rata by demand, fixed keys, or
  optimised/welfare-maximising allocation. Static keys = data; optimised = the
  solver chooses the split (still linear).
- **Settlement / pricing**: internal exchanges priced at a community tariff
  (between buy and sell price), using the existing `BuyingRatio`/`SellingRatio`/
  `Incentive` machinery. Members' bills = grid import at retail − shared-energy
  credit + community fee. New cost/revenue terms in the objective components
  (mirrors how `vTotalEleMrk*` terms are built today).

### Virtual net metering / P2P variants
- **Virtual net metering**: a member's export offsets another member's import over a
  settlement window (e.g. monthly) — a windowed allocation constraint (same
  windowed-sum pattern as the storage cycle, already prototyped).
- **P2P**: bilateral allocation variables `vEleP2P[p,sc,n,from_member,to_member]`
  within the community, with per-pair limits; linear. If pricing is
  game-theoretic/bilevel (members optimise own bills vs a coordinator), use Pyomo
  `pyomo.mpec` (complementarity) or a KKT→MILP reformulation — both Pyomo-native.

### Phasing within Phase 6
- **6a — virtual sharing with a fixed rule. DONE (2026-06-07).** Implemented in
  ``oM_Community.py``: per-member ``vEleShareIn``/``vEleShareOut`` variables, a
  per-zone pool-conservation constraint, and the matching terms in the retail
  balance, behind the ``IndBinCommunity`` flag (off by default — the four golden
  cases keep their exact costs). The cost saving emerges from displacing the retail
  buy/sell spread, so no explicit settlement term is needed for the total-cost
  objective (member-level bill splitting is 6b). Validated by
  ``tests/test_community.py``: a two-member community (prosumer with PV + consumer)
  uses sharing and lowers total cost (~65 % on the synthetic case) vs the flag-off
  baseline. Member-level bill reporting and community pricing remain for 6b.
- **6b — optimised sharing + virtual net metering** (windowed settlement).
- **6c — P2P / bilevel** (only if needed; `pyomo.mpec`).

### DoD for Phase 6
6a: an energy-community case (a zone with ≥2 members) solves; total community cost
with sharing ≤ without sharing; member-level bills and shared-energy flows in
`results.duckdb`. 6b/6c: optimised and windowed variants validated against 6a.

### Data additions
- `oM_Dict_Community` (or reuse Zone) + membership mapping (reuse `z2*`).
- `oM_Data_Community` (sharing rule, community tariff, settlement window).
- A small **CommunityHome** validation case (one zone, a few members with PV +
  battery + load), added to the generate-on-the-fly `data/sizing` family so it is
  CI-tested from CSV and DuckDB.

---

## Sequencing recommendation

Both phases are independent of each other and of the linopy work. Suggested order,
given the roadmap:

1. **6a (virtual sharing, fixed rule)** — smallest, highest-value, pure-linear,
   directly demonstrable, reuses everything that exists. Best first win.
2. **5a/5b (AC OPF SOCP/NLP on snapshots)** — the prototypes already exist; promote
   them to real case data and wire into `results.duckdb`.
3. **6b** (optimised + virtual net metering), then **5c** (three-phase — the large
   item, with the Pyomo-vs-PMD.jl decision), then **6c** (P2P/bilevel) as needed.

Each step is a new constraint family or analysis module with a DoD and a
validation case, parity-gated in CI — the same incremental method used for the
DuckDB refactor and the sizing cases. None requires leaving Pyomo.

## Cross-cutting notes
- **Keep existing cases unaffected**: every new feature behind an option flag
  defaulting off (the `pOptIndBin*` convention), so the four golden validation
  cases keep their exact costs.
- **Three-phase is the one genuinely large item** — scope it as its own project
  after the interface (5a/5b) is proven; everything else is incremental.
- **linopy**: the community/sharing layers (6) are linear, so if the linopy
  accelerator is later built, they port to it too; the AC-OPF module (5) stays on
  Pyomo/CVXPY/PMD.jl regardless (linopy cannot express it).
