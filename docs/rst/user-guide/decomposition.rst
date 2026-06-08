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
  window boundary is the linking variable.

Solve entry points
------------------

- ``el1xr_benders(dir, case, date, ...)`` -- master holds the investment build
  fractions; one operating subproblem per ``(period, scenario)`` block with the
  investment fixed (the fixing-constraint duals give the optimality cuts). Validated to
  reach the exact monolithic optimum.
- ``el1xr_temporal_benders(dir, case, date, n_time_blocks=...)`` -- splits one operating
  horizon into time windows coupled by the storage inventory at each boundary, which the
  master holds. The per-scenario fixed network charge is counted once in the master; the
  **peak-demand charge** (the sum of the N largest grid imports per month) is rewritten
  as a threshold LP whose per-month threshold is a master linking variable. Validated
  against the binary monolith for several block counts.
- ``benders_solve(...)`` -- the generic multi-cut L-shaped method the two el1xr entry
  points call; reusable for any two-stage stochastic program.

Feasibility is guaranteed for any first-stage decision with an elastic penalty on the
operating constraints, so optimality cuts suffice (no separate feasibility-cut pass).

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
