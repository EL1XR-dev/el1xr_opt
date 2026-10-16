Time structure
==============

el1xr_opt is moving to a fully flexible temporal resolution, following Gao et al. [Gao2025]_ and
the Tulipa formulation [TejadaArango2023]_. Each asset and each flow may have its own time
resolution, so a one-week case can hold 15-minute day-ahead trades, hourly reserve bids, a
hydrogen store tracked every two hours and daily demand limits at the same time.

.. figure:: /../img/el1xr_opt_time_structure.svg
   :width: 100%
   :align: center
   :alt: One timeline on a 1-minute ruler; day-ahead energy in 15-minute blocks, FCR-N bid and electrolyser output in 1-hour blocks, hydrogen tank level in 2-hour blocks; reserve headroom at the finest common resolution and the tank balance at the coarsest; three representative periods with their weights.

   Panel (a): one timeline, a resolution for each asset and flow, and the constraint resolutions
   derived from them. Panel (b): representative periods, each with its own timeline and weight.
   Source: ``docs/img/src/el1xr_opt_time_structure.tex``.

Timeline and base unit
----------------------

Time is counted in base units of 1 minute from the start of each representative period. The base
unit is a ruler only: no variable exists at 1 minute unless a resolution asks for it, so a fine
base unit costs nothing by itself. A case without representative periods has one period of
weight 1 that covers the whole horizon.

Resolutions
-----------

A resolution is an ordered list of time blocks that covers a period. Blocks need not have equal
lengths, and two resolutions need not nest. A decision variable is a rate, constant within its
block. Resolutions are written as short specifications:

- ``uniform 15min`` or ``uniform 1h``: equal blocks;
- ``calendar hour``, ``calendar day``, ``calendar month``: blocks that follow the clock;
- ``explicit 60,60,120``: block lengths in minutes.

Every block is labelled by the start of its period. Load level ``t0001`` is the hour
00:00-01:00 and carries the label 00:00, as day-ahead and balancing market data do.

Constraint resolutions
----------------------

A constraint takes its resolution from the variables it involves.

- **Instantaneous** constraints (power balances, capacity and headroom limits) use the finest
  common resolution: a new block starts whenever a block of any involved variable starts
  (Algorithm 1 of [Gao2025]_). A coarser constraint would let energy move inside a block.
- **Accumulating** constraints (storage, conversion, energy budgets) may use the coarsest common
  resolution: each block runs to the latest end among the variable blocks that hold its start
  (Algorithm 2). Each variable enters weighted by its overlap with the constraint block, in base
  units (Algorithm 3).

Parameters are resampled to the resolution of the constraint that uses them: a rate (price,
power, per-unit profile) by its duration-weighted mean, an amount per block (energy, inflow) by
its share of the overlap.

Implementation
--------------

The time structure lives in :mod:`el1xr_opt.Modules.oM_Time`, which has no Pyomo dependency:

- ``Timeline``, ``RepPeriod`` and ``Resolution`` hold the base unit, the periods and the blocks;
- ``uniform``, ``calendar``, ``from_lengths`` and ``from_spec`` build resolutions;
- ``overlap`` returns the overlap of every pair of blocks of two resolutions;
- ``finest_common`` and ``coarsest_common`` implement Algorithms 1 and 2;
- ``resample`` maps a series between resolutions.

``data_processing`` builds the timeline (``model.timeline``) and the resolution of the load levels
(``model.time_res['level']``). The calendar of the model (day, month, clock hour of each level)
is read from them, so merging hours with ``TimeStep`` keeps the dates right.

Status
------

The timeline and the calendar are in place. Every variable and constraint still lives on the
load levels, so present cases solve as before. The constraint families move onto the overlap form
one group at a time, followed by cases with mixed resolutions and by ramps and unit commitment on
blocks of unequal length.

References
----------

.. [Gao2025] Z. Gao, M. Gazzani, D. A. Tejada-Arango, A. Soares Siqueira, N. Wang, M. Gibescu and
   G. Morales-España, "Fully flexible temporal resolution for energy system optimization",
   *Applied Energy*, vol. 396, 126267, 2025. doi:10.1016/j.apenergy.2025.126267

.. [TejadaArango2023] D. A. Tejada-Arango et al., "Tulipa Energy Model: Mathematical Formulation",
   arXiv:2309.07711, 2023.
