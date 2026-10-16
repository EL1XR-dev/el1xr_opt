Time structure
==============

el1xr_opt is moving to a fully flexible temporal resolution, following Gao et al. [Gao2025]_ and
the Tulipa formulation [TejadaArango2023]_. Each asset and each flow may have its own time
resolution, so a one-week case can hold 15-minute day-ahead trades, hourly reserve bids, a
hydrogen store tracked every two hours and daily demand limits at the same time.

.. figure:: /../img/el1xr_opt_time_structure.svg
   :width: 100%
   :align: center
   :alt: One timeline on a 1-minute ruler; day-ahead energy in 15-minute blocks, FCR-N bid and electrolyser output in 1-hour blocks, hydrogen tank level in 2-hour blocks; reserve headroom at the highest common resolution and the tank balance at the lowest; three representative periods with their weights.

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
  (Algorithm 1 of [Gao2025]_). A constraint at a lower resolution would let energy move inside a
  block.
- **Accumulating** constraints (storage, conversion, energy budgets) may use the lowest common
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
- ``finest_common`` and ``coarsest_common`` implement Algorithms 1 and 2 (the highest and the
  lowest common resolution);
- ``resample`` maps a series between resolutions.

``data_processing`` builds the timeline (``model.timeline``) and the resolution of the load levels
(``model.time_res['level']``). The calendar of the model (day, month, clock hour of each level)
is read from them, so merging hours with ``TimeStep`` keeps the dates right.

Declaring a resolution
----------------------

A case declares resolutions in an optional table, ``oM_Data_Resolution_<case>.csv``, one row per
unit, with up to four columns:

.. code-block:: text

   ,Output,Charge,Commitment,Reserve
   Solar_01,uniform 2h,,,
   BESS_01,,uniform 1h,,
   AEL_01,,uniform 2h,uniform 2h,uniform 1h

- ``Output``: the total output of the unit.
- ``Charge``: the total charge (the electricity drawn by a store or an electrolyser, the hydrogen
  drawn by a hydrogen store or a fuel cell).
- ``Commitment``: the commitment, and the standby state of an electrolyser. Start-ups and
  shut-downs stay per load level.
- ``Reserve``: the FCR-D up, FCR-D down and FCR-N bids, the market product.

A blank cell keeps the resolution of the load levels, and a case without the table is unchanged.
Every block of a declared resolution must start on a load level boundary.

A declared flow has one variable per block. Its variable component keeps its name and its index
over every load level, as a reference whose entries all point to the variable of their block, so
every constraint and every result reads it per load level as before. The second-block output
stays per load level, because the total output is the second block plus the activated reserve,
and the activation changes every level.

The limits of a flow declared at a lower resolution than the load levels follow the Parameter
``BlockLimit``:

- ``Level`` (default): the flow stays within its lower and upper limits at every level of the
  block, so a 2-h constant output stays below the lowest availability inside the 2 h. The limits
  are set to the tightest value inside the block. A must-take profile that changes inside a
  block cannot be met, and the case is refused when it is read, naming the unit and the block.
- ``Mean``: both limits are replaced by their duration-weighted mean over the block, as in
  [Gao2025]_. Each block delivers at most its available energy, but spread evenly over the
  block, so energy moves between the hours of a block. On the H2VPP test case, a solar unit
  declared at 2 h costs less under ``Mean`` than at hourly resolution for that reason.

Constraints at their own resolution
-----------------------------------

A constraint is written per load level. For a declared unit, a row whose variables are all
block variables (or have no time index) repeats the row at the start of the block: the same
variables, coefficients, constant and bounds. Such rows are dropped when the model is built, so
the constraint holds once per block, at the highest common resolution of its variables
(Algorithm 1). Rows that also involve a variable per load level, such as the second-block output
or a start-up, differ from level to level and stay. The solution and the cost do not change. The
dual of the row that remains is the shadow price of the whole block; a dropped row has no dual
in the results.

Status
------

The timeline, the calendar, the declarations of output, charge, commitment and reserve bids with
one variable per block, and the removal of repeated rows are in place. Next comes an opt-in
resolution for storage inventories, with the storage balance written per block at the lowest
common resolution (Algorithm 2). That one changes results, as energy may move within a block.
Cases with mixed resolutions, and ramps and unit commitment on blocks of unequal length, follow.

References
----------

.. [Gao2025] Z. Gao, M. Gazzani, D. A. Tejada-Arango, A. Soares Siqueira, N. Wang, M. Gibescu and
   G. Morales-España, "Fully flexible temporal resolution for energy system optimization",
   *Applied Energy*, vol. 396, 126267, 2025. doi:10.1016/j.apenergy.2025.126267

.. [TejadaArango2023] D. A. Tejada-Arango et al., "Tulipa Energy Model: Mathematical Formulation",
   arXiv:2309.07711, 2023.
