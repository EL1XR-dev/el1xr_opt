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

.. graphviz::
   :align: center
   :alt: One period with a weight, two scenarios with probability 0.5 each, and 24 hourly load levels under each scenario.

   digraph hierarchy {
     graph [rankdir=TB, nodesep=0.25, ranksep=0.4, fontname="Helvetica"];
     node  [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=10, fillcolor="#ffffff", color="#888888"];
     edge  [color="#888888", arrowhead=none];
     p   [label="Period period1\nweight 1 (oM_Data_Period)", fillcolor="#e1bee7", color="#6a1b9a"];
     s1  [label="Scenario sc01\nprobability 0.5", fillcolor="#e3f2fd", color="#1565c0"];
     s2  [label="Scenario sc02\nprobability 0.5", fillcolor="#e3f2fd", color="#1565c0"];
     n1  [label="t0001\nduration 1 h"]; n2 [label="t0002\nduration 1 h"]; n3 [label="…"]; n4 [label="t0024\nduration 1 h"];
     m1  [label="t0001"]; m2 [label="t0002"]; m3 [label="…"]; m4 [label="t0024"];
     p -> {s1 s2};
     s1 -> {n1 n2 n3 n4}; s2 -> {m1 m2 m3 m4};
   }

The model solves for the hourly dispatch of that day under both scenarios, weighted by
their probabilities. For a sizing study
the load levels should represent a full year (via durations) so the annualised
investment trades off against a full year of operation.
