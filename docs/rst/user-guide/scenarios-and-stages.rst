Periods, scenarios and load levels
==================================

The model's temporal structure is a three-level hierarchy:

``period → scenario → load level``

Each level plays a distinct role in the simulation's scope and resolution.

Hierarchy levels
----------------

*   **Periods** (``model.p``) -- the longest time frame, such as a year or a step of a
    multi-year planning horizon. Each period carries a discount factor, so investment and
    operation are weighted onto a common discounted footing.

*   **Scenarios** (``model.sc``) -- within each period, the possible futures or operating
    conditions (weather, demand, prices). Each scenario has a probability, so the model
    weighs its contribution to the expected cost. The active ``(period, scenario)`` pairs
    are the set ``model.ps``.

*   **Load levels** (``model.n`` -- the active subset of ``model.nn``) -- the individual
    time steps within a ``(period, scenario)``: hours, or representative periods standing
    in for several hours. Each load level has a **duration** (``pDuration``); a level with
    a blank duration is dropped, which is how a case truncates its horizon. Operating
    decisions -- dispatch, storage, conversion -- are made at this level.

For convenience the model derives groupings of the load levels: representative **days**
(``doy``, used by the depth-of-discharge and daily-peak logic) and **months** (``moy``,
used by the monthly top-N peak-demand charge). These are not separate input levels --
they are mappings over the load levels.

.. note::

   There is no "stage" level in el1xr_opt. (The set ``model.st`` is storage, not stage.)
   The temporal hierarchy is exactly period, scenario and load level.

Configuration
-------------

The structure is configured through the case's CSV (or DuckDB) tables, not hard-coded.
``data_processing`` in ``el1xr_opt.Modules.oM_InputData`` reads them and builds the sets
(``model.p``, ``model.sc``, ``model.ps``, ``model.n``, ...) the Pyomo model uses. The
load-level durations and the period weights / scenario probabilities live in
``oM_Data_Duration``, ``oM_Data_Period`` and ``oM_Data_Scenario``.

Example
-------

A single-year case with two equally likely scenarios and an hourly horizon:

- **Period:** ``period1`` (discount factor 1.0)
- **Scenarios:** ``sc01`` (50%), ``sc02`` (50%)
- **Load levels:** 24 hourly steps, each with duration 1.

The model solves for the optimal hourly dispatch under both scenarios, weighted by
their probabilities, to find the best overall strategy for the year. For a sizing study
the load levels should represent a full year (via durations) so the annualised
investment trades off against a full year of operation.
