Decomposition (Benders)
=======================

el1xr_opt can solve the investment + operating problem as a single monolithic model
(the default) or by **Benders decomposition**. The decomposition reaches the same
optimum as the monolith; its value is letting a large problem be built and solved in
independent blocks. The code is in ``oM_Decomposition.py``; the design is in
``docs/decomposition.md``.

Block structure
---------------

The problem is block-angular:

- the **investment** (capacity-sizing) decisions are the first stage, shared by every
  block (the Benders master variables);
- the **operating** problem separates by ``(period, scenario)`` -- and, for long
  horizons, by contiguous **time windows** -- given the investment;
- **storage** couples time, so when the horizon is split, the storage inventory at each
  window boundary is the linking variable. There is one boundary inventory per stored
  carrier: ``Se`` (electricity), ``Sh`` (hydrogen) and ``St`` (the heat thermal store).
  The heat store is now coupled across windows like a battery: the incoming boundary
  replaces the window's first-level store balance, and the outgoing boundary ties the
  window's last level to the master copy.

Solve entry points
------------------

- ``el1xr_benders(dir, case, date, ...)`` -- master holds the investment build
  fractions; one operating subproblem per ``(period, scenario)`` block with the
  investment fixed (the fixing-constraint duals give the optimality cuts). Validated to
  reach the exact monolithic optimum.
- ``el1xr_temporal_benders(dir, case, date, n_time_blocks=...)`` -- splits one operating
  horizon into time windows coupled by the storage inventory at each boundary, which the
  master holds (``Se`` / ``Sh`` / ``St`` for electricity / hydrogen / heat storage).
  The heat operating cost (heat-not-served plus heat-generator running cost) is a
  per-load-level sum, so it decomposes per window and is added to each window's recourse.
  Validated against the binary monolith for several block counts.

Some per-``(period, scenario)`` charges depend on the whole horizon and do not split by
window (a naive split would double-count them). These are handled by a **registry-driven**
mechanism rather than hard-coded names. ``seed_horizon_coupling`` (in ``oM_Features``)
reads the structure model and declares each such charge:

- a **constant** charge over the horizon (``register_horizon_constant``) -- for example
  the fixed network fee -- is counted once in the master and removed from every window's
  recourse;
- a **peak / threshold** charge (``register_horizon_threshold``) -- the sum of the N
  largest grid imports per month -- is rewritten as a threshold LP whose per-month
  threshold is a master linking variable;
- an **unsupported** charge (``register_horizon_unsupported``) raises a clear error
  instead of returning a wrong objective. A Daily power-tariff peak is marked unsupported.

A safety net backs this up: the split compares the registered ``"ps"`` cost and revenue
terms against ``TEMPORAL_HANDLED_PS_COST`` / ``TEMPORAL_HANDLED_PS_REV`` and refuses an
unrecognised one, so a charge that is added to the objective but not described is caught
rather than silently dropped.

- ``benders_solve(...)`` -- the generic multi-cut L-shaped method the two el1xr entry
  points call; reusable for any two-stage stochastic program.

Feasibility is guaranteed for any first-stage decision with an elastic penalty on the
operating constraints, so optimality cuts suffice (no separate feasibility-cut pass).

Scope of the temporal MVP
~~~~~~~~~~~~~~~~~~~~~~~~~~~

``el1xr_temporal_benders`` is a minimum-viable version with three limits, each enforced
by a raise rather than a silent wrong answer:

- it handles a single ``(period, scenario)``;
- it assumes hourly storage (cycle time step = 1), so each window boundary is one
  inventory value per storage unit;
- it supports Hourly power tariffs only; a Daily power-tariff peak charge raises.

Parallelism
-----------

The subproblems are independent given the master decision, so they can be solved at
once. Pyomo solvers are not thread-safe, so the parallelism is by process:
``BendersConfig.n_workers > 1`` starts a pool of worker processes that each build and
reuse their share of the blocks across iterations. The result is identical to the
sequential solve.

When it pays off
----------------

Decomposition wins when the per-block work dominates the coordination overhead -- a
combinatorial first stage (unit-commitment binaries) or a problem too large to hold in
one model. On small LPs the monolith is faster (one efficient solve beats many
round-trips). See the benchmarks under ``benchmarks/`` and ``docs/decomposition.md``.
