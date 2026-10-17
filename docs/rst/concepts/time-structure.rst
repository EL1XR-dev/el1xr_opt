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

Load level length
-----------------

The Parameter ``LoadLevelMinutes`` sets the length of a load level, 60 minutes by default. A
case at quarter hours has ``LoadLevelMinutes = 15`` and four load levels per hour, and every
time series is given per quarter hour. The duration of a level (``pDuration``) stays in hours,
so it is 0.25 at quarter hours, and every cost and energy balance follows.

Every time given in hours is converted to a number of load levels: minimum up and down times
and the time already served at the start, storage and outflow cycles, network switching times
and the demand shift window ``ShiftedSteps``. A minimum up time of 3 h is 12 load levels at
quarter hours.

Two rules are set per clock hour, whatever the level length. The peak of a network tariff is
taken on the hourly mean of the import, as Swedish network tariffs are, and the renewable
matching of an electrolyser compares the energy of each hour. Both are written at the first
level of each hour. With hourly levels they are the rules as before.

A ramp limit is a rate in kW per hour, applied over the duration of each level. An hourly model
lets a unit move by a whole hour of ramp between two levels; at quarter hours the same rate
allows a quarter of that per level. On H2VPP (48 h) the shipped EV ramp limits bind at quarter
hours and not at hourly levels, so the quarter-hour case with the same hourly data costs more:
360.864824 against 360.087456. Without the storage ramp limits the two cases cost the same.

Series at their own resolution
------------------------------

A time series may be given at its own resolution instead of the resolution of the load levels.
An optional table, ``oM_Data_SeriesResolution_<case>.csv``, has one row per data file (its stem)
and a column ``Resolution``:

.. code-block:: text

   ,Resolution
   OperatingReservePrice,uniform 1h
   VarEnergyCost,uniform 15min

The rows of a declared file are the blocks of that resolution, in order, for each period and
scenario; their labels are not read. When the case is read, the file is resampled onto the load
levels. A series coarser than the load levels holds each value over the levels of its block, so
an hourly FCR price in a quarter-hour case is repeated over the four quarters. A series finer
than the load levels is averaged over each level, weighted by duration. Every series the model
reads is a rate (a price, a power or a per-unit profile), so this is the right rule for each of
them. The ``Duration`` file defines the load levels and cannot be declared.

On H2VPP (48 h, ramp limits of the stores off) the case at 192 quarter-hour levels costs
360.087456 whether its 28 time series are repeated four times by hand or kept hourly and
declared ``uniform 1h``, the same as the hourly case.

Declaring a resolution
----------------------

A case declares resolutions in an optional table, ``oM_Data_Resolution_<case>.csv``, one row per
unit, with up to five columns:

.. code-block:: text

   ,Output,Charge,Commitment,Reserve,Inventory
   Solar_01,uniform 2h,,,,
   BESS_01,,uniform 1h,,,uniform 4h
   AEL_01,,uniform 2h,uniform 2h,uniform 1h,

- ``Output``: the total output of the unit.
- ``Charge``: the total charge (the electricity drawn by a store or an electrolyser, the hydrogen
  drawn by a hydrogen store or a fuel cell).
- ``Commitment``: the commitment, and the standby state of an electrolyser. Start-ups and
  shut-downs stay per load level.
- ``Reserve``: the FCR-D up, FCR-D down and FCR-N bids, the market product.
- ``Inventory``: the inventory of an electricity or hydrogen store (see `Inventory per block`_).

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

Inventory per block
-------------------

A declared inventory is the stored energy at the end of each of its blocks. The storage balance
is written once per block, at its last load level: the inventory at the end of the previous
block (or the initial inventory) plus the net charge over every level of the block
(Algorithm 2). The storage limits are those of the last level of the block, whatever
``BlockLimit`` is. Other constraints that read the inventory per load level, such as the energy
behind a reserve bid, read the value at the end of the block.

The inventory is not tracked inside a block, so this one changes results: the store may go above
or below its limits between two block ends. For a store without reserve bids the cost can only
fall. With reserve bids it can also rise, because the energy behind the bid of each level is
read from the inventory at the end of the block. On H2VPP (48 h, battery shrunk to 2 kWh so its
limits bind, no reserve bids):

==================  ===========  ============
Inventory           Cost         Balance rows
==================  ===========  ============
per load level      369.715453   48
``uniform 2h``      369.714675   24
``calendar day``    369.711677   2
==================  ===========  ============

The older ``StorageType`` of a store (Hourly, Daily, Weekly, Monthly, Yearly) writes the balance
every k load levels and leaves the inventory in between free. A calendar-day inventory gives the
same cost as ``StorageType = Weekly`` on hourly levels, with one inventory variable per block in
place of free ones, and with blocks that follow the calendar or have unequal lengths. A store
with a declared inventory needs a cycle of one load level (``StorageType`` Hourly or Daily); a
case that sets both is refused.

Ramps between blocks
--------------------

A ramp limit bounds the change of a rate between two consecutive blocks by the ramp rate times
the time between the two block midpoints, (l1 + l2) / 2 [Gao2025]_. For an output or charge
declared at a resolution, this applies at the first level of each of its blocks, with the
lengths of that block and the one before. Inside a block the declared flow does not change, and
the row bounds the change of the activated reserve over one level. A flow that is not declared
has one block per load level, so with levels of equal length the rule is the ramp over one
level, as before.

On H2VPP (48 h, shipped ramp limits) the case at 192 quarter-hour levels costs 360.864824 when
the EVs and the battery may change their output every quarter hour, as each quarter allows a
quarter of an hour of ramp. With their output and charge declared ``uniform 1h`` it costs
360.087456, the cost of the hourly case: a change between two hourly blocks is allowed the ramp
of one hour. Without the midpoint rule the declared case cost 362.753016, because the change of
an hour had to happen within one quarter.

Minimum up and down times count load levels converted from hours, and start-ups, shut-downs and
the standby transitions of an electrolyser compare a level with the one before. With a declared
commitment the commitment does not change inside a block, so these rules act at block
boundaries, and a minimum up time spans the blocks that cover it.

Status
------

The timeline, the calendar, load levels of any length in minutes, the declarations of output,
charge, commitment, reserve bids and inventory with one variable per block, the storage balance
per block, time series at their own resolution, the removal of repeated rows and ramps between
blocks are in place. Representative periods, where a load level stands for several hours, come
later.

References
----------

.. [Gao2025] Z. Gao, M. Gazzani, D. A. Tejada-Arango, A. Soares Siqueira, N. Wang, M. Gibescu and
   G. Morales-España, "Fully flexible temporal resolution for energy system optimization",
   *Applied Energy*, vol. 396, 126267, 2025. doi:10.1016/j.apenergy.2025.126267

.. [TejadaArango2023] D. A. Tejada-Arango et al., "Tulipa Energy Model: Mathematical Formulation",
   arXiv:2309.07711, 2023.
