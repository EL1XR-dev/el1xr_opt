Features, problem classes and modes
===================================

``oM_Features.py`` is the one place that records the optional features, detects the
model's mathematical class, and keeps the cost/revenue registry. It is the lever for
choosing the solver and (for a future migration) the model-building library.

Option-flag catalogue
---------------------

Each optional feature has an option flag with a safe default. ``apply_flag_defaults``
seeds the defaults so a case whose ``oM_Data_Option`` file predates a flag still runs
instead of raising a ``KeyError``. The flags cover unit-commitment binaries, ramps,
minimum up/down time, single-node operation, network and storage investment, the energy
community, green-hydrogen matching, and the balance mode.

Problem classes
---------------

From the built model, ``detect_problem_class`` reports the mathematical class -- LP,
MILP, QP, MIQP, SOCP, MISOCP, NLP, MINLP or SDP. The class drives two choices:

- **Solver**: a capability matrix records which solvers handle which class (for
  example HiGHS does LP and MILP but not SOCP). ``check_solver_for_model`` warns when
  the chosen solver cannot handle the model's class.
- **Build library**: the same class selects which model-building libraries are viable
  (for example a MISOCP rules out the linopy backend).

Cost/revenue registry
---------------------

A new cost-bearing feature registers its term with ``register_cost`` /
``register_revenue`` instead of editing the objective-aggregation rules. The objective
aggregation sums the registry, seeded with the built-in terms in their original order,
so existing results are unchanged. Each term has a *kind* -- ``ps`` (per period and
scenario), ``psn`` (also per load level, duration-weighted) or ``psd`` (per
representative day) -- that fixes how it is summed.

Balance and network modes
-------------------------

Two orthogonal axes describe how power conservation is written:

- **Network mode** -- the physics: single node, DC power flow, AC (DistFlow SOCP / polar
  NLP), or unbalanced three-phase (LinDist3Flow). See :doc:`../user-guide/network-analysis`.
- **Balance mode** -- the bookkeeping: ``nodal`` (one balance per node; the default and
  the only in-core form) or ``arc`` (one balance per asset with explicit arc flows, the
  block-angular form). The arc form is the planned modernization for decomposition; it
  reaches the same optimum but is rejected in-core for now with a clear message.

The two are independent -- every balance expresses every network mode.
