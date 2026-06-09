Network analysis (AC OPF and LinDist3Flow)
==========================================

Besides the single-node and DC power-flow representations used in the main solve,
el1xr_opt ships two **decoupled** network-analysis tools that run on a network snapshot
rather than inside the planning model, so they stay tractable.

AC optimal power flow
---------------------

``oM_ACOPF.py`` runs a single-phase AC OPF on a network snapshot (the case's branches
plus nodal injections). Two formulations:

- the **second-order-cone** (branch-flow / DistFlow) relaxation, whose objective is the
  total active loss and which reports a per-branch relaxation gap (``solve_acopf_socp``), and
- the exact **polar NLP** (``solve_acopf_nlp``), warm-started from the SOC voltages.

The module is checked against the IEEE 33-bus feeder (Baran & Wu) in
``tests/test_acopf.py``, using the network and published values in ``tests/_ieee33.py``.
The SOC path is asserted to reproduce the published base-case loss (~202.7 kW) and
minimum voltage (~0.913 pu) with a tight relaxation gap, and the polar NLP is asserted to
agree with that SOC solution. These checks need a cone solver (Gurobi for SOC) and Ipopt
(for the NLP); they skip when the solver is not installed, so the numbers are validated
only when a suitable solver is present.

A multi-snapshot sweep (``run_acopf_sweep``) runs one AC OPF per snapshot and summarises
voltage and loss violations across a horizon. Results can be written to DuckDB.

LinDist3Flow
------------

``oM_LinDist3Flow.py`` is the linearised three-phase branch-flow model: per-phase
squared voltages and flows on a radial feeder with a linear voltage-drop law that keeps
the 3x3 phase coupling to first order. Because it is an **LP**, it is the linear,
in-Python option for unbalanced feeders -- distinct from the exact unbalanced AC OPF.
It reduces phase by phase to the single-phase LinDistFlow on a balanced feeder, and
spreads per-phase voltages under unbalanced loading, as expected.

These tools are analysis modules: they do not change the main optimisation model. The
network mode used *inside* the planning solve (single node / DC / AC / three-phase) is
selected through the feature catalogue -- see :doc:`../concepts/features-and-modes`.
