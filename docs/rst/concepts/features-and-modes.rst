Features, problem classes and modes
===================================

``oM_Features.py`` is the one place that records the optional features, detects the
model's mathematical class, and keeps the cost/revenue registry. It is the lever for
choosing the solver and (for a future migration) the model-building library.

Option-flag catalogue
---------------------

The ``FEATURES`` catalogue holds twelve ``IndBin*`` option flags, each with a safe
default. ``apply_flag_defaults`` seeds those defaults so a case whose ``oM_Data_Option``
file predates a flag still runs instead of raising a ``KeyError``. The flags cover
unit-commitment binaries, network commitment, minimum up/down time, ramps, generation
investment and retirement, electricity- and hydrogen-network investment, line
commitment, network losses, single-node operation, and the energy community. The same
helper also seeds the balance mode (``pParBalanceMode``); that mode is not a ``Feature``
in the catalogue. Green-hydrogen matching is likewise not an ``oM_Features`` flag -- it
is handled in ``oM_GreenHydrogen.py``.

Problem classes
---------------

From the built model, ``detect_problem_class`` reports the mathematical class -- LP,
MILP, QP, MIQP, SOCP, MISOCP, NLP or MINLP. (SDP is not detected here; it appears only
in the solver and builder capability matrices.) The class drives two choices:

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

Horizon-coupling registry
-------------------------

Most cost terms split cleanly by time window, but a few per-(period, scenario) charges do
not -- they are aggregates over the whole horizon. ``oM_Features`` records these as
descriptors so the temporal Benders decomposition is driven by the descriptors rather than
by hard-coded variable names. Two shapes are supported:

- ``register_horizon_constant`` -- a charge that is constant over the horizon, such as the
  fixed network fee (``fastavgift``). The full-horizon scalar is counted once in the
  master and removed from every window's recourse.
- ``register_horizon_threshold`` -- a "sum of the N largest quantity per subgroup" peak
  charge, written as a threshold LP. Today this is the electricity peak demand charge: the
  N largest grid imports per month per retailer.

A charge the split cannot yet decompose (for example a Daily power tariff) is marked with
``register_horizon_unsupported`` so the decomposition raises a clear error instead of
returning a wrong objective.

``seed_horizon_coupling`` seeds the built-in electricity descriptors from a structure-only
model. The sets ``TEMPORAL_HANDLED_PS_COST`` and ``TEMPORAL_HANDLED_PS_REV`` list the
per-(period, scenario) composite cost and revenue terms the split knows how to handle; a
composite outside these is refused by the split's guard. See :doc:`../user-guide/decomposition`.

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
